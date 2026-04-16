import json
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.models.job import Job
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.log_repository import LogRepository
from app.services.queue_publisher_service import QueuePublisherService
from app.events.workflow_observer import WorkflowObserver

QUEUE_MAP = {
    "csv-analysis": "csv-analysis",
    "report-generation": "report-generation",
    "email-send": "email-send",
    "calendar-create": "calendar-create",
    "notifications": "notifications",
}


class WorkflowExecutionService:
    def __init__(self, db: Session, publisher: QueuePublisherService, observer: WorkflowObserver) -> None:
        self.db = db
        self.workflow_repo = WorkflowRepository(db)
        self.log_repo = LogRepository(db)
        self.publisher = publisher
        self.observer = observer

    async def create_and_dispatch(self, user_id: str, prompt: str, plan: dict) -> dict:
        workflow = Workflow(
            id=str(uuid4()),
            user_id=user_id,
            original_prompt=prompt,
            intent_summary=plan.get("intent_summary"),
            status="queued",
        )
        self.workflow_repo.create_workflow(workflow)

        steps = [
            WorkflowStep(
                id=step["id"],
                workflow_id=workflow.id,
                step_order=step["step_order"],
                step_name=step["name"],
                step_type=step["type"],
                depends_on_step_id=step.get("depends_on_step_id"),
                status="queued",
                input_payload=json.dumps(
                    {
                        "prompt": prompt,
                        "tool": step.get("tool"),
                        "input": step.get("input"),
                    }
                ),
            )
            for step in plan["steps"]
        ]
        self.workflow_repo.bulk_create_steps(steps)

        jobs = []
        for step in steps:
            queue_name = QUEUE_MAP[step.step_type]
            jobs.append(
                Job(
                    id=str(uuid4()),
                    workflow_id=workflow.id,
                    workflow_step_id=step.id,
                    queue_name=queue_name,
                    worker_type=queue_name,
                    idempotency_key=f"{workflow.id}:{step.id}",
                    status="queued",
                )
            )
        self.workflow_repo.create_jobs(jobs)

        for job in jobs:
            step = next((s for s in steps if s.id == job.workflow_step_id), None)
            step_input = None
            step_tool = None
            if step and step.input_payload:
                try:
                    parsed_input = json.loads(step.input_payload)
                    if isinstance(parsed_input, dict):
                        step_input = parsed_input.get("input")
                        step_tool = parsed_input.get("tool")
                except Exception:
                    step_input = None
                    step_tool = None

            await self.publisher.publish_job(
                queue_name=job.queue_name,
                payload={
                    "job_id": job.id,
                    "workflow_id": workflow.id,
                    "workflow_step_id": job.workflow_step_id,
                    "idempotency_key": job.idempotency_key,
                    "prompt": prompt,
                    "tool": step_tool,
                    "input": step_input,
                },
                idempotency_key=job.idempotency_key,
            )

        self.log_repo.create(workflow_id=workflow.id, message="Workflow queued and jobs published")
        self.observer.notify("workflow.created", {"workflow_id": workflow.id, "jobs": len(jobs)})

        return {
            "workflow_id": workflow.id,
            "status": workflow.status,
            "intent_summary": workflow.intent_summary,
        }
