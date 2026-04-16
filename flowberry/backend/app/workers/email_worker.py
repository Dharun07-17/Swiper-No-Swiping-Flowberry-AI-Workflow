import asyncio
import base64
import json
import re
import time
from email.message import EmailMessage
import httpx
from app.core.db import db_manager
from app.models.integration import Integration
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.services.encryption_service import EncryptionService
from app.workers.consumer_base import WorkerConsumer
from app.services.ai_client import AIClient


class EmailWorker(WorkerConsumer):
    async def process_task(self, queue_name: str, payload: dict) -> dict:
        if queue_name == "report-generation":
            prompt = payload.get("prompt") or "Generate a concise workflow report."
            ai = AIClient()
            summary = await ai.generate_text(
                "Generate a concise report summary for this request:\n" + prompt
            )
            await asyncio.sleep(0.3)
            return {"report_id": f"report-{payload['workflow_step_id']}", "status": "generated", "summary": summary}

        if queue_name == "email-send":
            if payload.get("approve") is True:
                await asyncio.sleep(0.2)
                draft = payload.get("draft") or self._build_draft(payload)
                result = await self._send_gmail(payload, draft)
                result["draft"] = draft
                return result

            draft = self._build_draft(payload)
            return {"_step_status": "waiting_approval", "draft": draft}

        raise ValueError(f"Unsupported queue {queue_name}")

    def _build_draft(self, payload: dict) -> dict:
        prompt = payload.get("prompt") or ""
        to_email = self._extract_email(prompt) or payload.get("to") or "team@example.com"
        summary_text = self._fetch_dep_summary(payload.get("workflow_step_id"))
        subject, body = self._parse_subject_body(summary_text)
        subject = subject or "Workflow Report"
        body = body or "Draft email body goes here."

        return {
            "to": to_email,
            "subject": subject,
            "body": body,
            "status": "draft",
        }

    def _fetch_dep_summary(self, step_id: str | None) -> str:
        if not step_id:
            return ""
        db = db_manager.get_session()
        try:
            step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
            if not step or not step.depends_on_step_id:
                return ""
            dep = db.query(WorkflowStep).filter(WorkflowStep.id == step.depends_on_step_id).first()
            if not dep or not dep.output_payload:
                return ""
            try:
                parsed = json.loads(dep.output_payload)
                if isinstance(parsed, dict):
                    return str(parsed.get("summary") or parsed.get("report") or parsed)
                return str(parsed)
            except Exception:
                return dep.output_payload
        finally:
            db.close()

    def _parse_subject_body(self, text: str) -> tuple[str | None, str | None]:
        if not text:
            return None, None
        subject = None
        body = text.strip()
        match = re.search(r"^Subject:\s*(.+)$", text, flags=re.M)
        if match:
            subject = match.group(1).strip()
            body = re.sub(r"^Subject:\s*.+$", "", text, flags=re.M).strip()
        return subject, body

    def _extract_email(self, text: str) -> str | None:
        if not text:
            return None
        match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)
        return match.group(0) if match else None

    async def _send_gmail(self, payload: dict, draft: dict) -> dict:
        workflow_id = payload.get("workflow_id")
        if not workflow_id:
            raise ValueError("Missing workflow_id for Gmail send")

        db = db_manager.get_session()
        try:
            workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
            if not workflow:
                raise ValueError("Workflow not found for Gmail send")

            integration = (
                db.query(Integration)
                .filter(Integration.user_id == workflow.user_id, Integration.provider == "Gmail")
                .order_by(Integration.updated_at.desc())
                .first()
            )
            if not integration:
                raise ValueError("No Gmail integration found for user")

            enc = EncryptionService()
            creds = self._decrypt_credentials(enc, integration)
            access_token = await self._get_access_token(db, integration, creds)

            message = EmailMessage()
            message["To"] = draft.get("to") or self._extract_email(payload.get("prompt") or "") or ""
            message["Subject"] = draft.get("subject") or "Workflow Report"
            message.set_content(draft.get("body") or "")
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers=headers,
                    json={"raw": raw},
                )
                resp.raise_for_status()
                data = resp.json()

            return {
                "delivery": "sent",
                "provider": "gmail",
                "status": "ok",
                "message_id": data.get("id"),
                "thread_id": data.get("threadId"),
            }
        finally:
            db.close()

    def _decrypt_credentials(self, enc: EncryptionService, integration: Integration) -> dict:
        try:
            raw = enc.decrypt(integration.credentials_encrypted)
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"oauth_json": "", "api_key": "", "oauth_tokens": {}}

    async def _get_access_token(self, db, integration: Integration, creds: dict) -> str:
        tokens = creds.get("oauth_tokens") or {}
        access_token = tokens.get("access_token")
        expires_in = tokens.get("expires_in")
        created_at = tokens.get("created_at")
        if access_token and expires_in and created_at:
            if time.time() < (created_at + int(expires_in) - 60):
                return access_token

        refresh_token = tokens.get("refresh_token")
        oauth_json = creds.get("oauth_json") or ""
        if not refresh_token or not oauth_json:
            raise ValueError("Gmail OAuth tokens missing; connect the integration first")

        try:
            parsed = json.loads(oauth_json)
        except Exception:
            raise ValueError("Gmail OAuth JSON invalid")

        config = parsed.get("web") or parsed.get("installed") or {}
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")
        token_uri = config.get("token_uri")
        if not client_id or not client_secret or not token_uri:
            raise ValueError("Gmail OAuth JSON missing required fields")

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(token_uri, data=data)
            resp.raise_for_status()
            payload = resp.json()

        tokens.update(
            {
                "access_token": payload.get("access_token"),
                "expires_in": payload.get("expires_in"),
                "scope": payload.get("scope") or tokens.get("scope"),
                "token_type": payload.get("token_type") or tokens.get("token_type"),
                "created_at": int(time.time()),
            }
        )
        creds["oauth_tokens"] = tokens
        integration.credentials_encrypted = EncryptionService().encrypt(json.dumps(creds))
        db.commit()

        if not tokens.get("access_token"):
            raise ValueError("Failed to refresh Gmail access token")
        return tokens["access_token"]


async def main() -> None:
    worker = EmailWorker(worker_name="worker-email", queues=["report-generation", "email-send"])
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
