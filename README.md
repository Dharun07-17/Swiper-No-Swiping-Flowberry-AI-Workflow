

# Flowberry
---
Flowberry is an **event-driven AI workflow automation platform** where natural language requests are converted into structured, multi-step workflows (e.g., search → summarize → email → calendar). Execution is handled asynchronously via a **queue-based worker system** with full observability, retries, and idempotent processing.

---
<img width="572" height="428" alt="Screenshot 2026-04-17 035752" src="https://github.com/user-attachments/assets/0c451aa4-c1f2-47ab-84bf-63d693652357" />
<img width="857" height="846" alt="Screenshot 2026-04-17 035715" src="https://github.com/user-attachments/assets/fb1f5ffb-8f0a-469e-a45d-6b5829da18ab" />
<img width="525" height="733" alt="Screenshot 2026-04-17 035619" src="https://github.com/user-attachments/assets/50c5e035-f772-461d-b01f-9f81effe475f" />
<img width="1919" height="851" alt="Screenshot 2026-04-17 035258" src="https://github.com/user-attachments/assets/cc6b86b2-8db2-4c82-ab21-edb9efe9c9f5" />
<img width="1650" height="846" alt="Screenshot 2026-04-17 035010" src="https://github.com/user-attachments/assets/0dc76ca8-b4fc-4093-a723-55a8eb9f64e2" />





## Problem Statement

Modern automation tools tightly couple request execution with backend APIs, leading to:

* Poor scalability under concurrent workloads
* Blocking operations inside APIs
* Lack of fault tolerance and retry control
* No clear execution traceability
* Security risks with sensitive data exposure

---

## Solution

Flowberry solves this using an **event-driven distributed architecture**:

* API only creates and publishes workflow events
* Workers process tasks asynchronously via queue
* Tasks are executed atomically and independently
* System supports retries, DLQ, and idempotency
* Full observability across API + workers

---

## Tech Stack

**Backend**

* Python / FastAPI (or Node equivalent)
* PostgreSQL
* RabbitMQ (or Redis Queue alternative)
* SQLAlchemy ORM

**Frontend**

* React + Vite

**Infra**

* Docker + Docker Compose
* Prometheus + Grafana
* Loki + FluentBit (logging)
* OpenTelemetry (tracing)

---

## Architecture

### System Style

* Event-driven architecture (EDA)
* Worker-based asynchronous processing
* Message queue backbone (RabbitMQ / Redis Streams)

---

### Design Patterns Used

* **MVC Pattern**

  * Controllers → API layer
  * Services → business logic
  * Models → DB schema

* **Singleton Pattern**

  * Database connection pool (single shared instance per service)

* **Observer Pattern**

  * Event publishing → queue triggers workers

* **Repository Pattern**

  * DB abstraction layer for clean separation

---

## Workflow Execution Flow

1. User submits prompt via API
2. API converts it into workflow graph
3. Workflow is persisted in DB
4. Events are published to queue
5. Workers consume tasks atomically
6. Each step updates execution state
7. Results aggregated and returned

---

## Queue & Worker System

* Queue: RabbitMQ / Redis Streams
* Minimum **2 workers per service** for parallelism
* Each task:

  * Locked atomically
  * Processed once (idempotent key enforced)
  * Retries on failure
  * Sent to DLQ after max retries

---

## Idempotency Strategy

* Every task has a unique `execution_id`
* Worker checks DB before processing:

  * If already processed → skip
* Prevents duplicate execution in retries or crashes

---

## Security

### Authentication

* JWT Access Token (short-lived)
* Refresh Token (long-lived)
* Optional Email OTP MFA

### RBAC

* Roles:

  * `admin`
  * `user`

### Data Protection

* PII encrypted at rest (AES/Fernet)
* Sensitive data never exposed to frontend APIs
* Only masked or tokenized outputs returned

---

## Error Handling

* Centralized API error middleware
* Worker retry mechanism with exponential backoff
* Dead Letter Queue (DLQ) for failed jobs
* Structured error logs with trace IDs

---

## Observability

### Logging

* Structured logs (JSON)
* FluentBit → Loki pipeline

### Metrics

* Prometheus scraping `/metrics`

### Tracing

* OpenTelemetry instrumentation
* Distributed trace across:

  * API
  * Workers
  * Queue events

### Visualization

* Grafana dashboards:

  * API latency
  * Queue depth
  * Worker throughput
  * Failure rates

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
  frontend/
    src/
      components/
      pages/
      services/
      store/
  infra/
    grafana/
    loki/
    prometheus/
    otel/
  docker-compose.yml
  run.ps1
  .env.example
```

---

## Dockerized Setup

All services run inside a **single Docker network** using Docker Compose.

### Services

* frontend
* api
* worker-email
* worker-calendar
* worker-core (minimum 2 replicas)
* postgres
* rabbitmq
* redis (optional fallback queue)
* prometheus
* grafana
* loki
* otel-collector

---

## Run Instructions

### 1. Clone & setup env

```bash
cp .env.example .env
```

---

### 2. Start full stack

```powershell
.\run.ps1
```

This will:

* Build all images
* Start all services in a single network
* Run DB migrations
* Start workers (minimum 2 instances)

---

## Access Points

* Frontend → `http://localhost:5173`
* API Docs → `http://localhost:8000/docs`
* RabbitMQ → `http://localhost:15672`
* Grafana → `http://localhost:3000`

---

## Event Driven Architecture Notes

* API never performs long-running tasks
* All execution is async via queue
* Workers are stateless and horizontally scalable
* System supports horizontal scaling easily (add more workers)
---
## Notes

This system is designed to be **production-grade scalable architecture**:

* Fully decoupled services
* Queue-based execution
* Strong observability
* Secure by design
* Horizontally scalable workers


