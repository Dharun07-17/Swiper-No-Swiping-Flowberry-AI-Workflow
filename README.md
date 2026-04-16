# Flowberry

Flowberry is an event‑driven AI workflow automation platform where **Fizz** turns a natural‑language request into a multi‑step workflow (search → summarize → email → calendar, etc.). Steps run on dedicated workers via RabbitMQ with retries, DLQ handling, and full execution traceability.
---
## Highlights

- Prompt‑to‑workflow planning
- Human‑in‑the‑loop approval for outbound actions
- Pluggable integrations (Gmail, Google Calendar, Notion, etc.)
- Execution logs, retries, and DLQ
- Email‑OTP MFA for login
---
## Project Structure

```text
flowberry/
  backend/
    app/
      auth/
      controllers/
      core/
      events/
      middleware/
      models/
      observability/
      repositories/
      schemas/
      services/
      utils/
      workers/
    alembic/
  frontend/
    src/
      components/
      hooks/
      layouts/
      pages/
      services/
      store/
      types/
  infra/
    grafana/
    loki/
    otel/
    prometheus/
  docs/diagrams/
  docker-compose.yml
  .env.example
  run.ps1
```
---
## Architecture

- **Style**: Event‑driven, worker‑based execution
- **API role**: create plan, persist workflow, publish jobs
- **Patterns**: MVC, Repository, Service, Observer
- **Workers**: isolated queues with retry + DLQ, idempotent processing
---
## Services

`docker-compose.yml` includes:
- `frontend`
- `api`
- `worker-email`
- `worker-calendar`
- `postgres`
- `rabbitmq`
- `prometheus`
- `loki`
- `grafana`
- `otel-collector`
---
## Setup

1. Copy env:
```bash
cp .env.example .env
```
---
2. Set secrets in `.env`:
- `JWT_SECRET`
- `FERNET_KEY`
---
3. Run the stack (detached):
```powershell
.\run.ps1
```

By default, `run.ps1` builds the images, starts all services in the background, and seeds the database.
---
## Access

- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- RabbitMQ UI: `http://localhost:15672`
- Grafana: `http://localhost:3000`
---
## Auth + MFA (Email OTP)

Flowberry uses JWT access + refresh tokens and optional **email‑OTP MFA** on login.
---
Flow:
1. `POST /api/v1/auth/login`
2. If MFA is enabled → returns `mfa_token`
3. `POST /api/v1/auth/mfa/request` (send OTP to chosen email via Gmail integration)
4. `POST /api/v1/auth/mfa/verify`

You can enable/disable MFA in the **Security** page.
---
## Integrations

Integrations are stored encrypted and never returned to the UI. OAuth is supported for Gmail and Google Calendar.

- Gmail: used to send email drafts and MFA OTP
- Google Calendar: create events
---
## Observability

- Prometheus metrics at `/metrics`
- Loki for logs
- OpenTelemetry export to `otel-collector`
---
## Notes

This repo is production‑oriented but still a starter. Replace mock report generation with real sources and extend integration logic as needed.
