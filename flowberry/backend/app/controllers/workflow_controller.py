import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, CurrentUser
from app.core.db import get_db
from app.middleware.exception_middleware import AppException
from app.repositories.log_repository import LogRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.workflow import WorkflowCreateRequest, WorkflowCsvCreateRequest
from app.services.fizz_planning_service import FizzPlanningService
from app.services.queue_publisher_service import QueuePublisherService
from app.services.workflow_execution_service import WorkflowExecutionService
from app.events.listeners import observer_singleton
from app.models.job import Job
from uuid import uuid4

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("")
async def create_workflow(
    payload: WorkflowCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.prompt.strip():
        raise AppException("INVALID_PROMPT", "Prompt cannot be empty", 400)

    planner = FizzPlanningService()
    plan = await planner.create_plan(payload.prompt)

    publisher = QueuePublisherService()
    executor = WorkflowExecutionService(db=db, publisher=publisher, observer=observer_singleton)
    data = await executor.create_and_dispatch(user.user_id, payload.prompt, plan)
    await publisher.close()

    return {"success": True, "data": data, "message": "Workflow created"}


@router.post("/csv")
async def create_csv_workflow(
    payload: WorkflowCsvCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.prompt.strip():
        raise AppException("INVALID_PROMPT", "Prompt cannot be empty", 400)
    if not payload.csv_text.strip():
        raise AppException("INVALID_CSV", "CSV text cannot be empty", 400)
    if len(payload.csv_text) > 1_000_000:
        raise AppException("CSV_TOO_LARGE", "CSV text is too large (max 1MB)", 400)

    planner = FizzPlanningService()
    steps = planner._tools_to_steps(["csv"], payload.prompt)
    if steps:
        steps[0]["input"] = {"csv_text": payload.csv_text}

    plan = {"intent_summary": payload.prompt.strip()[:160], "steps": steps}

    publisher = QueuePublisherService()
    executor = WorkflowExecutionService(db=db, publisher=publisher, observer=observer_singleton)
    data = await executor.create_and_dispatch(user.user_id, payload.prompt, plan)
    await publisher.close()

    return {"success": True, "data": data, "message": "CSV workflow created"}


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WorkflowRepository(db)
    workflow = repo.get_workflow(workflow_id, None if user.role == "admin" else user.user_id)
    if not workflow:
        raise AppException("WORKFLOW_NOT_FOUND", "Workflow does not exist", 404)

    return {
        "success": True,
        "data": {
            "id": workflow.id,
            "status": workflow.status,
            "intent_summary": workflow.intent_summary,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        },
        "message": "Workflow fetched",
    }


@router.get("/{workflow_id}/steps")
def get_steps(
    workflow_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WorkflowRepository(db)
    workflow = repo.get_workflow(workflow_id, None if user.role == "admin" else user.user_id)
    if not workflow:
        raise AppException("WORKFLOW_NOT_FOUND", "Workflow does not exist", 404)
    steps = repo.list_steps(workflow_id)
    return {
        "success": True,
        "data": [
            {
                "id": s.id,
                "step_order": s.step_order,
                "step_name": s.step_name,
                "step_type": s.step_type,
                "status": s.status,
                "depends_on_step_id": s.depends_on_step_id,
                "output_payload": s.output_payload,
            }
            for s in steps
        ],
        "message": "Workflow steps fetched",
    }


@router.get("/{workflow_id}/logs")
def get_logs(
    workflow_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow_repo = WorkflowRepository(db)
    workflow = workflow_repo.get_workflow(workflow_id, None if user.role == "admin" else user.user_id)
    if not workflow:
        raise AppException("WORKFLOW_NOT_FOUND", "Workflow does not exist", 404)

    logs = LogRepository(db).list_for_workflow(workflow_id)
    return {
        "success": True,
        "data": [
            {
                "id": l.id,
                "job_id": l.job_id,
                "level": l.level,
                "message": l.message_sanitized,
                "trace_id": l.trace_id,
                "created_at": l.created_at,
            }
            for l in logs
        ],
        "message": "Logs fetched",
    }


@router.post("/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WorkflowRepository(db)
    workflow = repo.get_workflow(workflow_id, None if user.role == "admin" else user.user_id)
    if not workflow:
        raise AppException("WORKFLOW_NOT_FOUND", "Workflow does not exist", 404)

    steps = [s for s in repo.list_steps(workflow_id) if s.status in {"failed", "queued"}]
    publisher = QueuePublisherService()
    for step in steps:
        await publisher.publish_job(
            queue_name=step.step_type,
            payload={
                "workflow_id": workflow_id,
                "workflow_step_id": step.id,
                "idempotency_key": f"{workflow_id}:{step.id}",
                "retry": True,
            },
            idempotency_key=f"{workflow_id}:{step.id}",
        )
    await publisher.close()

    return {"success": True, "data": {"queued_steps": len(steps)}, "message": "Retry queued"}


@router.post("/{workflow_id}/steps/{step_id}/approve-email")
async def approve_email_step(
    workflow_id: str,
    step_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WorkflowRepository(db)
    workflow = repo.get_workflow(workflow_id, None if user.role == "admin" else user.user_id)
    if not workflow:
        raise AppException("WORKFLOW_NOT_FOUND", "Workflow does not exist", 404)

    step = next((s for s in repo.list_steps(workflow_id) if s.id == step_id), None)
    if not step or step.step_type != "email-send":
        raise AppException("STEP_NOT_FOUND", "Email step not found", 404)

    job = Job(
        id=str(uuid4()),
        workflow_id=workflow_id,
        workflow_step_id=step_id,
        queue_name="email-send",
        worker_type="email-send",
        idempotency_key=f"{workflow_id}:{step_id}:approve:{uuid4()}",
        status="queued",
    )
    repo.create_jobs([job])
    step.status = "queued"
    db.commit()

    draft_payload = None
    if step.output_payload:
        try:
            parsed_output = json.loads(step.output_payload)
            if isinstance(parsed_output, dict) and "draft" in parsed_output:
                draft_payload = parsed_output.get("draft")
        except Exception:
            draft_payload = None

    publisher = QueuePublisherService()
    await publisher.publish_job(
        queue_name="email-send",
        payload={
            "job_id": job.id,
            "workflow_id": workflow_id,
            "workflow_step_id": step_id,
            "idempotency_key": job.idempotency_key,
            "approve": True,
            "draft": draft_payload,
        },
        idempotency_key=job.idempotency_key,
    )
    await publisher.close()

    return {"success": True, "data": {"approved": step_id}, "message": "Email send approved"}
