from datetime import datetime
from pydantic import BaseModel


class WorkflowCreateRequest(BaseModel):
    prompt: str


class WorkflowCsvCreateRequest(BaseModel):
    prompt: str
    csv_text: str


class WorkflowStepPayload(BaseModel):
    id: str
    step_order: int
    step_name: str
    step_type: str
    status: str
    depends_on_step_id: str | None = None


class WorkflowSummaryPayload(BaseModel):
    id: str
    status: str
    intent_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowCreateResponse(BaseModel):
    success: bool = True
    data: dict
    message: str = "Workflow created"


class LogsResponse(BaseModel):
    success: bool = True
    data: list[dict]
    message: str = "Logs fetched"
