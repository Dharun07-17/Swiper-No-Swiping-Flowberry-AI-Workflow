from uuid import uuid4
from fastapi import APIRouter, Depends
from jose import jwt
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, CurrentUser
from app.auth.tokens import build_tokens, hash_token, decode_refresh
import pyotp
from app.auth.mfa import verify_totp, generate_totp_secret
from app.core.config import settings
from app.core.db import get_db
from app.core.security import verify_password
from app.middleware.exception_middleware import AppException
from app.models.refresh_token import RefreshToken
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, MFARequest, MFACodeRequest
from app.services.encryption_service import EncryptionService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    enc = EncryptionService()
    user_repo = UserRepository(db)
    refresh_repo = RefreshTokenRepository(db)

    user = user_repo.get_by_email_hash(enc.hash_for_lookup(payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise AppException("UNAUTHORIZED", "Invalid credentials", 401)

    if user.mfa_enabled:
        mfa_token = jwt.encode({"sub": user.id, "typ": "mfa"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return {
            "success": True,
            "data": {"requires_mfa": True, "mfa_token": mfa_token},
            "message": "MFA required",
        }

    access, refresh, jti, exp = build_tokens(user.id, user.role)
    refresh_repo.create(
        RefreshToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_token(refresh),
            jti=jti,
            expires_at=exp,
        )
    )
    return {"success": True, "data": {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}, "message": "Login successful"}


@router.post("/mfa/verify")
def mfa_verify(payload: MFARequest, db: Session = Depends(get_db)):
    try:
        mfa_payload = jwt.decode(payload.mfa_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as exc:
        raise AppException("UNAUTHORIZED", "Invalid MFA token", 401) from exc

    user_id = mfa_payload.get("sub")
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise AppException("UNAUTHORIZED", "User not found", 401)
    if not user.mfa_secret_encrypted:
        raise AppException("FORBIDDEN", "MFA not configured", 403)

    enc = EncryptionService()
    secret = enc.decrypt(user.mfa_secret_encrypted)
    if not verify_totp(secret, payload.otp_code):
        raise AppException("UNAUTHORIZED", "Invalid OTP", 401)

    refresh_repo = RefreshTokenRepository(db)
    access, refresh, jti, exp = build_tokens(user.id, user.role)
    refresh_repo.create(
        RefreshToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_token(refresh),
            jti=jti,
            expires_at=exp,
        )
    )

    return {"success": True, "data": {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}, "message": "MFA verified"}


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    decoded = decode_refresh(payload.refresh_token)
    jti = decoded["jti"]
    sub = decoded["sub"]

    refresh_repo = RefreshTokenRepository(db)
    stored = refresh_repo.get_active_by_jti(jti)
    if not stored or stored.token_hash != hash_token(payload.refresh_token):
        raise AppException("UNAUTHORIZED", "Refresh token invalid", 401)

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(sub)
    if not user:
        raise AppException("UNAUTHORIZED", "User not found", 401)

    refresh_repo.revoke(stored)
    access, refresh_token, new_jti, exp = build_tokens(user.id, user.role)
    refresh_repo.create(
        RefreshToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            jti=new_jti,
            expires_at=exp,
        )
    )

    return {
        "success": True,
        "data": {"access_token": access, "refresh_token": refresh_token, "token_type": "bearer"},
        "message": "Token refreshed",
    }


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    row = user_repo.get_by_id(user.user_id)
    return {
        "success": True,
        "data": {"id": user.user_id, "role": user.role, "mfa_enabled": bool(row.mfa_enabled) if row else False},
        "message": "Current user",
    }


@router.post("/mfa/setup")
def mfa_setup(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    row = user_repo.get_by_id(user.user_id)
    if not row:
        raise AppException("UNAUTHORIZED", "User not found", 401)
    if row.mfa_enabled:
        raise AppException("MFA_ALREADY_ENABLED", "MFA is already enabled", 400)

    enc = EncryptionService()
    if row.mfa_secret_encrypted:
        secret = enc.decrypt(row.mfa_secret_encrypted)
    else:
        secret = generate_totp_secret()
        row.mfa_secret_encrypted = enc.encrypt(secret)
        db.commit()

    try:
        email = enc.decrypt(row.email_encrypted)
    except Exception:
        email = "user@flowberry.local"
    issuer = settings.app_name
    otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)

    return {
        "success": True,
        "data": {"secret": secret, "otpauth_url": otpauth_url},
        "message": "MFA setup ready",
    }


@router.post("/mfa/enable")
def mfa_enable(payload: MFACodeRequest, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    row = user_repo.get_by_id(user.user_id)
    if not row:
        raise AppException("UNAUTHORIZED", "User not found", 401)
    if row.mfa_enabled:
        return {"success": True, "data": {"mfa_enabled": True}, "message": "MFA already enabled"}
    if not row.mfa_secret_encrypted:
        raise AppException("MFA_NOT_SETUP", "MFA setup is required first", 400)

    enc = EncryptionService()
    secret = enc.decrypt(row.mfa_secret_encrypted)
    if not verify_totp(secret, payload.otp_code):
        raise AppException("UNAUTHORIZED", "Invalid OTP", 401)

    row.mfa_enabled = True
    db.commit()

    return {"success": True, "data": {"mfa_enabled": True}, "message": "MFA enabled"}
