import asyncio
import json
from datetime import datetime
import aio_pika
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import db_manager
from app.models.job import Job
from app.models.workflow_step import WorkflowStep
from app.repositories.job_repository import JobRepository
from app.repositories.log_repository import LogRepository
from app.observability.metrics import FAILED_JOBS_TOTAL, ACTIVE_WORKER_COUNT
from app.utils.sanitization import sanitize_log_message


class WorkerConsumer:
    def __init__(self, worker_name: str, queues: list[str]) -> None:
        self.worker_name = worker_name
        self.queues = queues

    async def run(self) -> None:
        ACTIVE_WORKER_COUNT.labels(worker=self.worker_name).set(1)
        connection = None
        channel = None
        retry = 0
        while connection is None:
            try:
                connection = await aio_pika.connect_robust(settings.rabbitmq_url)
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=1)
            except Exception as exc:
                retry += 1
                wait = min(10, 1 + retry)
                print(f"[{self.worker_name}] RabbitMQ connect failed ({exc}). Retrying in {wait}s")
                await asyncio.sleep(wait)

        for queue_name in self.queues:
            queue = await channel.declare_queue(queue_name, durable=True)
            await queue.consume(lambda msg, q=queue_name: self._on_message(channel, msg, q))

        print(f"[{self.worker_name}] listening on {self.queues}")
        await asyncio.Future()

    async def _on_message(self, channel, message: aio_pika.abc.AbstractIncomingMessage, queue_name: str) -> None:
        async with message.process(requeue=False):
            payload = json.loads(message.body.decode())
            workflow_id = payload["workflow_id"]
            step_id = payload["workflow_step_id"]
            idempotency_key = payload["idempotency_key"]

            db: Session = db_manager.get_session()
            job_repo = JobRepository(db)
            log_repo = LogRepository(db)
            try:
                job = job_repo.get_by_idempotency_key(idempotency_key)
                if not job:
                    return
                if job.status == "completed":
                    log_repo.create(workflow_id=workflow_id, job_id=job.id, step_id=step_id, message="Duplicate job skipped")
                    return

                step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
                if step and step.depends_on_step_id:
                    dep = db.query(WorkflowStep).filter(WorkflowStep.id == step.depends_on_step_id).first()
                    if dep and dep.status != "completed":
                        # Dependency not ready. Requeue without consuming retries.
                        await self._requeue_dependency(channel, queue_name, payload, job, log_repo)
                        return

                job_repo.mark_running(job)
                if step:
                    step.status = "running"
                    step.started_at = datetime.utcnow()
                    db.commit()

                output = await self.process_task(queue_name, payload)

                if step:
                    if isinstance(output, dict) and "_step_status" in output:
                        step.status = output.pop("_step_status")
                    else:
                        step.status = "completed"
                    step.completed_at = datetime.utcnow()
                    step.output_payload = json.dumps(output)
                job_repo.mark_done(job)
                db.commit()
                log_repo.create(workflow_id=workflow_id, job_id=job.id, step_id=step_id, message=f"{queue_name} completed")

            except Exception as exc:
                code = "WORKER_FAILURE"
                clean_message = sanitize_log_message(str(exc))
                FAILED_JOBS_TOTAL.inc()
                if 'job' in locals() and job:
                    await self._retry_or_dlq(channel, queue_name, payload, job, code, log_repo, clean_message)
                else:
                    log_repo.create(workflow_id=workflow_id, step_id=step_id, level="ERROR", message=clean_message)
            finally:
                db.close()

    async def _retry_or_dlq(
        self,
        channel,
        queue_name: str,
        payload: dict,
        job: Job,
        code: str,
        log_repo: LogRepository,
        message: str = "Retry scheduled",
    ) -> None:
        db = log_repo.db
        retries = job.retry_count + 1
        if retries > job.max_retries:
            job.status = "dead_lettered"
            job.error_code = code
            job.error_message_sanitized = message[:500]
            step = db.query(WorkflowStep).filter(WorkflowStep.id == job.workflow_step_id).first()
            if step:
                step.status = "failed"
                step.completed_at = datetime.utcnow()
            db.commit()

            dlq = f"{queue_name}-dlq"
            await channel.declare_queue(dlq, durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(payload).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=dlq,
            )
            log_repo.create(workflow_id=job.workflow_id, job_id=job.id, step_id=job.workflow_step_id, level="ERROR", message=f"Moved to DLQ {dlq}")
            return

        job.retry_count = retries
        job.status = "queued"
        job.error_code = code
        job.error_message_sanitized = message[:500]
        db.commit()

        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(payload).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=queue_name,
        )
        log_repo.create(workflow_id=job.workflow_id, job_id=job.id, step_id=job.workflow_step_id, level="WARNING", message=f"Retry {retries} queued")

    async def process_task(self, queue_name: str, payload: dict) -> dict:
        raise NotImplementedError

    async def _requeue_dependency(
        self,
        channel,
        queue_name: str,
        payload: dict,
        job: Job,
        log_repo: LogRepository,
    ) -> None:
        # Simple backoff to avoid tight loops
        await asyncio.sleep(2)
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(payload).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=queue_name,
        )
        log_repo.create(
            workflow_id=job.workflow_id,
            job_id=job.id,
            step_id=job.workflow_step_id,
            level="INFO",
            message="Dependency not ready, requeued",
        )
