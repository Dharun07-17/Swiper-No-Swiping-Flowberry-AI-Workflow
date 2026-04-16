import json
import base64
import hashlib
import hmac
import time
from urllib.parse import urlencode
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, CurrentUser
from app.core.config import settings
from app.core.db import get_db
from app.core.security import verify_password
from app.middleware.exception_middleware import AppException
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.integration import (
    IntegrationCreateRequest,
    IntegrationDeleteRequest,
    IntegrationCheckRequest,
)
from app.services.encryption_service import EncryptionService
import httpx

router = APIRouter(prefix="/integrations", tags=["integrations"])

GOOGLE_SCOPES = {
    "Google Drive": ["https://www.googleapis.com/auth/drive.readonly"],
    "Gmail": ["https://www.googleapis.com/auth/gmail.send"],
    "Google Calendar": ["https://www.googleapis.com/auth/calendar.events"],
}


def _decrypt_credentials(enc: EncryptionService, integration: Integration) -> dict:
    try:
        raw = enc.decrypt(integration.credentials_encrypted)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"oauth_json": "", "api_key": "", "oauth_tokens": {}}


def _sign_state(integration_id: str, user_id: str) -> str:
    payload = json.dumps({"integration_id": integration_id, "user_id": user_id, "ts": int(time.time())}).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    sig = hmac.new(settings.jwt_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"


def _verify_state(state: str) -> dict | None:
    try:
        encoded, sig = state.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(settings.jwt_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(padded.encode()).decode()
        return json.loads(payload)
    except Exception:
        return None


@router.get("")
def list_integrations(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = IntegrationRepository(db)
    rows = repo.list_for_user(user.user_id)
    items = []
    enc = EncryptionService()
    for row in rows:
        creds = _decrypt_credentials(enc, row)
        has_oauth_json = bool(creds.get("oauth_json"))
        has_api_key = bool(creds.get("api_key"))
        has_oauth_token = bool(creds.get("oauth_tokens"))
        items.append(
            {
                "id": row.id,
                "provider": row.provider,
                "display_name": row.display_name,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "has_oauth_json": has_oauth_json,
                "has_api_key": has_api_key,
                "has_oauth_token": has_oauth_token,
            }
        )

    return {"success": True, "data": items, "message": "Integrations fetched"}


@router.post("")
def create_integration(
    payload: IntegrationCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.display_name.strip():
        raise AppException("INVALID_NAME", "Display name is required", 400)

    enc = EncryptionService()
    secret_payload = {
        "oauth_json": payload.oauth_json or "",
        "api_key": payload.api_key or "",
        "oauth_tokens": {},
    }
    encrypted = enc.encrypt(json.dumps(secret_payload))

    repo = IntegrationRepository(db)
    integration = repo.create(
        Integration(
            id=str(uuid4()),
            user_id=user.user_id,
            provider=payload.provider,
            display_name=payload.display_name,
            credentials_encrypted=encrypted,
        )
    )

    return {
        "success": True,
        "data": {
            "id": integration.id,
            "provider": integration.provider,
            "display_name": integration.display_name,
            "created_at": integration.created_at,
            "updated_at": integration.updated_at,
            "has_oauth_json": bool(payload.oauth_json),
            "has_api_key": bool(payload.api_key),
            "has_oauth_token": False,
        },
        "message": "Integration created",
    }


@router.post("/check")
def check_integration(
    payload: IntegrationCheckRequest,
    user: CurrentUser = Depends(get_current_user),
):
    provider = payload.provider.strip()
    errors: list[str] = []

    oauth_required = provider in {"Google Drive", "Gmail", "Google Calendar"}
    api_required = provider in {"NewsAPI", "Notion", "SERP API"}

    if oauth_required:
        if not payload.oauth_json:
            errors.append("OAuth JSON is required for this provider.")
        else:
            try:
                parsed = json.loads(payload.oauth_json)
                if not isinstance(parsed, dict):
                    errors.append("OAuth JSON must be an object.")
            except Exception:
                errors.append("OAuth JSON must be valid JSON.")

    if api_required:
        if not payload.api_key or len(payload.api_key.strip()) < 8:
            errors.append("API key looks too short for this provider.")

    if not oauth_required and not api_required:
        # Generic validation if custom provider
        if not payload.oauth_json and not payload.api_key:
            errors.append("Provide OAuth JSON or API key.")

    return {"success": len(errors) == 0, "errors": errors}


@router.post("/{integration_id}/oauth/start")
def start_oauth(
    integration_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = IntegrationRepository(db)
    integration = repo.get(integration_id)
    if not integration or integration.user_id != user.user_id:
        raise AppException("INTEGRATION_NOT_FOUND", "Integration not found", 404)

    enc = EncryptionService()
    creds = _decrypt_credentials(enc, integration)
    oauth_json = creds.get("oauth_json") or ""
    if not oauth_json:
        raise AppException("OAUTH_JSON_MISSING", "OAuth JSON not configured for this integration", 400)

    try:
        parsed = json.loads(oauth_json)
    except Exception as exc:
        raise AppException("OAUTH_JSON_INVALID", "OAuth JSON is invalid", 400) from exc

    config = parsed.get("web") or parsed.get("installed") or {}
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    auth_uri = config.get("auth_uri")
    token_uri = config.get("token_uri")
    if not client_id or not client_secret or not auth_uri or not token_uri:
        raise AppException("OAUTH_JSON_INVALID", "OAuth JSON missing required fields", 400)

    scopes = GOOGLE_SCOPES.get(integration.provider)
    if not scopes:
        raise AppException("OAUTH_UNSUPPORTED", "OAuth flow not supported for this provider", 400)

    redirect_uri = f"{settings.public_base_url}{settings.api_prefix}/integrations/oauth/callback"
    state = _sign_state(integration.id, user.user_id)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{auth_uri}?{urlencode(params)}"
    return {"success": True, "data": {"auth_url": auth_url}, "message": "OAuth URL generated"}


@router.get("/oauth/callback")
def oauth_callback(request: Request, db: Session = Depends(get_db)):
    error = request.query_params.get("error")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if error:
        return RedirectResponse(f"{settings.frontend_public_url}/integrations?oauth=error")
    if not code or not state:
        raise AppException("OAUTH_FAILED", "Missing code/state", 400)

    payload = _verify_state(state)
    if not payload:
        raise AppException("OAUTH_FAILED", "Invalid state", 400)

    integration_id = payload.get("integration_id")
    user_id = payload.get("user_id")
    repo = IntegrationRepository(db)
    integration = repo.get(integration_id)
    if not integration or integration.user_id != user_id:
        raise AppException("INTEGRATION_NOT_FOUND", "Integration not found", 404)

    enc = EncryptionService()
    creds = _decrypt_credentials(enc, integration)
    try:
        parsed = json.loads(creds.get("oauth_json") or "{}")
    except Exception:
        raise AppException("OAUTH_JSON_INVALID", "OAuth JSON invalid", 400)

    config = parsed.get("web") or parsed.get("installed") or {}
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    token_uri = config.get("token_uri")
    if not client_id or not client_secret or not token_uri:
        raise AppException("OAUTH_JSON_INVALID", "OAuth JSON missing required fields", 400)

    redirect_uri = f"{settings.public_base_url}{settings.api_prefix}/integrations/oauth/callback"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=15) as client:
        resp = client.post(token_uri, data=data)
        resp.raise_for_status()
        token_payload = resp.json()

    creds["oauth_tokens"] = {
        "access_token": token_payload.get("access_token"),
        "refresh_token": token_payload.get("refresh_token"),
        "expires_in": token_payload.get("expires_in"),
        "scope": token_payload.get("scope"),
        "token_type": token_payload.get("token_type"),
        "created_at": int(time.time()),
    }
    integration.credentials_encrypted = enc.encrypt(json.dumps(creds))
    db.commit()

    return RedirectResponse(f"{settings.frontend_public_url}/integrations?oauth=success")


@router.delete("/{integration_id}")
def delete_integration(
    integration_id: str,
    payload: IntegrationDeleteRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = IntegrationRepository(db)
    integration = repo.get(integration_id)
    if not integration or integration.user_id != user.user_id:
        raise AppException("INTEGRATION_NOT_FOUND", "Integration not found", 404)

    user_repo = UserRepository(db)
    current_user = user_repo.get_by_id(user.user_id)
    if not current_user or not verify_password(payload.password, current_user.password_hash):
        raise AppException("UNAUTHORIZED", "Password incorrect", 401)

    repo.delete(integration)
    return {"success": True, "data": {"deleted": integration_id}, "message": "Integration deleted"}
