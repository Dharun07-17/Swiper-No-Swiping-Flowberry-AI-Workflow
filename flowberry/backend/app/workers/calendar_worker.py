import asyncio
import csv
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
import httpx
from app.core.db import db_manager
from app.models.integration import Integration
from app.models.workflow import Workflow
from app.services.encryption_service import EncryptionService
from app.services.ai_client import AIClient
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
            await asyncio.sleep(0.2)
            csv_text = ""
            input_payload = payload.get("input") or {}
            if isinstance(input_payload, dict):
                csv_text = input_payload.get("csv_text") or ""
            if not csv_text:
                csv_text = payload.get("csv_text") or ""
            if not csv_text.strip():
                raise ValueError("CSV text is empty")

            analysis = self._analyze_csv(csv_text)
            gemini_summary = await self._explain_csv_with_gemini(csv_text, analysis)
            report_text = self._format_csv_report(csv_text, analysis, gemini_summary)
            report_file = self._write_csv_report(payload, report_text)
            try:
                drive_info = await self._upload_report_to_drive(payload, report_text)
            except Exception as exc:
                drive_info = {"error": str(exc)}

            return {
                **analysis,
                "gemini_summary": gemini_summary,
                "report_file": report_file,
                "drive": drive_info,
            }

        raise ValueError(f"Unsupported queue {queue_name}")

    def _analyze_csv(self, csv_text: str) -> dict:
        if len(csv_text) > 1_000_000:
            raise ValueError("CSV text is too large (max 1MB)")

        reader = csv.reader(csv_text.splitlines())
        rows = list(reader)
        if not rows:
            raise ValueError("CSV has no rows")

        header = rows[0]
        data_rows = rows[1:]
        sample_rows = data_rows[:5]

        return {
            "row_count": len(data_rows),
            "column_count": len(header),
            "columns": header,
            "sample_rows": sample_rows,
        }

    async def _explain_csv_with_gemini(self, csv_text: str, analysis: dict) -> str:
        max_chars = 20000
        excerpt = csv_text.strip()
        truncated = False
        if len(excerpt) > max_chars:
            excerpt = excerpt[:max_chars]
            truncated = True

        prompt = (
            "You are a data analyst. Explain this CSV in plain English. "
            "Summarize what it contains, potential insights, and any data quality issues. "
            "Use short paragraphs and bullet points.\n\n"
            f"Metadata:\nRows: {analysis.get('row_count')}\n"
            f"Columns: {analysis.get('column_count')}\n"
            f"Headers: {', '.join(analysis.get('columns') or [])}\n\n"
            "CSV (text):\n"
            f"{excerpt}\n\n"
        )
        if truncated:
            prompt += "\nNote: CSV content was truncated for length.\n"

        ai = AIClient()
        return await ai.generate_text(prompt)

    def _format_csv_report(self, csv_text: str, analysis: dict, gemini_summary: str) -> str:
        lines = [
            "Flowberry CSV Report",
            "",
            f"Row count: {analysis.get('row_count')}",
            f"Column count: {analysis.get('column_count')}",
            f"Columns: {', '.join(analysis.get('columns') or [])}",
            "",
            "Gemini Summary:",
            gemini_summary.strip() if gemini_summary else "No summary available.",
            "",
            "Sample rows:",
        ]
        for row in analysis.get("sample_rows") or []:
            lines.append(", ".join(row))
        lines.append("")
        lines.append("Raw CSV:")
        lines.append(csv_text.strip())
        return "\n".join(lines)

    def _write_csv_report(self, payload: dict, report_text: str) -> dict:
        step_id = payload.get("workflow_step_id") or "unknown"
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        reports_dir = os.path.join(os.path.dirname(__file__), "..", "report_outputs")
        reports_dir = os.path.normpath(reports_dir)
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"csv_report_{step_id}_{ts}.txt"
        path = os.path.join(reports_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report_text)
        size_bytes = os.path.getsize(path)
        return {"path": path, "size_bytes": size_bytes}

    async def _upload_report_to_drive(self, payload: dict, report_text: str) -> dict:
        workflow_id = payload.get("workflow_id")
        if not workflow_id:
            raise ValueError("Missing workflow_id for Drive upload")

        db = db_manager.get_session()
        try:
            workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
            if not workflow:
                raise ValueError("Workflow not found for Drive upload")

            integration = (
                db.query(Integration)
                .filter(Integration.user_id == workflow.user_id, Integration.provider == "Google Drive")
                .order_by(Integration.updated_at.desc())
                .first()
            )
            if not integration:
                raise ValueError("No Google Drive integration found for user")

            enc = EncryptionService()
            creds = self._decrypt_credentials(enc, integration)
            access_token = await self._get_access_token(db, integration, creds, "Google Drive")

            step_id = payload.get("workflow_step_id") or "unknown"
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            metadata = {"name": f"flowberry_csv_report_{step_id}_{ts}.txt", "mimeType": "text/plain"}
            boundary = "flowberry_boundary"
            body = (
                f"--{boundary}\r\n"
                "Content-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{json.dumps(metadata)}\r\n"
                f"--{boundary}\r\n"
                "Content-Type: text/plain\r\n\r\n"
                f"{report_text}\r\n"
                f"--{boundary}--"
            )

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink",
                    headers=headers,
                    content=body.encode("utf-8"),
                )
                resp.raise_for_status()
                data = resp.json()

            return {"file_id": data.get("id"), "web_view_link": data.get("webViewLink")}
        finally:
            db.close()

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
            access_token = await self._get_access_token(db, integration, creds, "Google Calendar")

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

    async def _get_access_token(self, db, integration: Integration, creds: dict, provider_label: str) -> str:
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
            raise ValueError(f"{provider_label} OAuth tokens missing; connect the integration first")

        try:
            parsed = json.loads(oauth_json)
        except Exception:
            raise ValueError(f"{provider_label} OAuth JSON invalid")

        config = parsed.get("web") or parsed.get("installed") or {}
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")
        token_uri = config.get("token_uri")
        if not client_id or not client_secret or not token_uri:
            raise ValueError(f"{provider_label} OAuth JSON missing required fields")

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
            raise ValueError(f"Failed to refresh {provider_label} access token")
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
