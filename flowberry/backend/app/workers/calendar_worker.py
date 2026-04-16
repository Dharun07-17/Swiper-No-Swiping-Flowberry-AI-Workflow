import asyncio
import json
import re
import time
from datetime import datetime, timedelta, timezone
import httpx
from app.core.db import db_manager
from app.models.integration import Integration
from app.models.workflow import Workflow
from app.services.encryption_service import EncryptionService
from app.workers.consumer_base import WorkerConsumer


class CalendarWorker(WorkerConsumer):
    async def process_task(self, queue_name: str, payload: dict) -> dict:
        if queue_name == "calendar-create":
            await asyncio.sleep(0.2)
            event = self._build_event(payload)
            result = await self._create_google_event(payload, event)
            result["event"] = event
            return result

        if queue_name == "notifications":
            await asyncio.sleep(0.5)
            return {"notification_status": "sent", "channel": "slack"}

        if queue_name == "csv-analysis":
            await asyncio.sleep(1.0)
            return {"rows": 128, "insight": "Top category is Operations"}

        raise ValueError(f"Unsupported queue {queue_name}")

    def _build_event(self, payload: dict) -> dict:
        prompt = (payload.get("prompt") or "").strip()
        tz = self._infer_timezone(prompt)
        start_dt = self._parse_start_datetime(prompt, tz)
        duration_min = self._parse_duration_minutes(prompt) or 30
        end_dt = start_dt + timedelta(minutes=duration_min)
        summary = self._parse_title(prompt) or "Flowberry Calendar Event"
        attendees = self._extract_emails(prompt)

        event = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        }
        if attendees:
            event["attendees"] = [{"email": e} for e in attendees]
        return event

    async def _create_google_event(self, payload: dict, event: dict) -> dict:
        workflow_id = payload.get("workflow_id")
        if not workflow_id:
            raise ValueError("Missing workflow_id for calendar create")

        db = db_manager.get_session()
        try:
            workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
            if not workflow:
                raise ValueError("Workflow not found for calendar create")

            integration = (
                db.query(Integration)
                .filter(Integration.user_id == workflow.user_id, Integration.provider == "Google Calendar")
                .order_by(Integration.updated_at.desc())
                .first()
            )
            if not integration:
                raise ValueError("No Google Calendar integration found for user")

            enc = EncryptionService()
            creds = self._decrypt_credentials(enc, integration)
            access_token = await self._get_access_token(db, integration, creds)

            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers=headers,
                    json=event,
                )
                resp.raise_for_status()
                data = resp.json()

            return {
                "calendar_event_id": data.get("id"),
                "status": "scheduled",
                "html_link": data.get("htmlLink"),
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
            raise ValueError("Google Calendar OAuth tokens missing; connect the integration first")

        try:
            parsed = json.loads(oauth_json)
        except Exception:
            raise ValueError("Google Calendar OAuth JSON invalid")

        config = parsed.get("web") or parsed.get("installed") or {}
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")
        token_uri = config.get("token_uri")
        if not client_id or not client_secret or not token_uri:
            raise ValueError("Google Calendar OAuth JSON missing required fields")

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
            raise ValueError("Failed to refresh Google Calendar access token")
        return tokens["access_token"]

    def _infer_timezone(self, text: str) -> str:
        lower = text.lower()
        if "ist" in lower or "india" in lower or "kolkata" in lower:
            return "Asia/Kolkata"
        if "pst" in lower or "pacific" in lower:
            return "America/Los_Angeles"
        if "est" in lower or "eastern" in lower:
            return "America/New_York"
        return "UTC"

    def _parse_title(self, text: str) -> str | None:
        if not text:
            return None
        for pattern in [
            r'titled\s+"([^"]+)"',
            r'title\s+"([^"]+)"',
            r'called\s+"([^"]+)"',
            r'named\s+"([^"]+)"',
            r'subject\s+"([^"]+)"',
        ]:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return match.group(1).strip()[:120]
        # Fallback: use first sentence if it is short enough
        sentence = re.split(r"[.!?]\s", text.strip(), maxsplit=1)[0]
        return sentence.strip()[:120] if sentence else None

    def _parse_duration_minutes(self, text: str) -> int | None:
        if not text:
            return None
        match = re.search(r"(\d{1,3})\s*(minute|minutes|min|mins)\b", text, flags=re.I)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d{1,2})\s*(hour|hours|hr|hrs)\b", text, flags=re.I)
        if match:
            return int(match.group(1)) * 60
        return None

    def _parse_start_datetime(self, text: str, tz: str) -> datetime:
        now = datetime.now(timezone.utc)
        base = now
        lower = text.lower()
        if "tomorrow" in lower:
            base = now + timedelta(days=1)
        elif "today" in lower:
            base = now

        date_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
        if date_match:
            year, month, day = map(int, date_match.groups())
            base = datetime(year, month, day, tzinfo=timezone.utc)

        time_match = re.search(r"\b(?:at\s*)?(\d{1,2})(?::(\d{2}))\s*(am|pm)\b", text, flags=re.I)
        if not time_match:
            time_match = re.search(r"\b(?:at\s*)?(\d{1,2}):(\d{2})\b", text, flags=re.I)
        if not time_match:
            time_match = re.search(r"\bat\s+(\d{1,2})\s*(am|pm)?\b", text, flags=re.I)

        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridian = time_match.group(3)
            if meridian:
                meridian = meridian.lower()
                if meridian == "pm" and hour < 12:
                    hour += 12
                if meridian == "am" and hour == 12:
                    hour = 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                base = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                base = (now + timedelta(hours=1)).replace(second=0, microsecond=0)
        else:
            base = (now + timedelta(hours=1)).replace(second=0, microsecond=0)

        # Convert UTC base to target timezone by offsetting if needed.
        if tz == "UTC":
            return base.astimezone(timezone.utc)
        # For simplicity, keep naive offset conversions limited; Google accepts tz separately.
        return base.astimezone(timezone.utc)

    def _extract_emails(self, text: str) -> list[str]:
        if not text:
            return []
        emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)
        return list(dict.fromkeys(emails))


async def main() -> None:
    worker = CalendarWorker(worker_name="worker-calendar", queues=["calendar-create", "notifications", "csv-analysis"])
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
