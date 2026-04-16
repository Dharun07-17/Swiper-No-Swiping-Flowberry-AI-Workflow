from datetime import datetime
from pydantic import BaseModel


class IntegrationCreateRequest(BaseModel):
    provider: str
    display_name: str
    oauth_json: str | None = None
    api_key: str | None = None


class IntegrationCheckRequest(BaseModel):
    provider: str
    oauth_json: str | None = None
    api_key: str | None = None


class IntegrationCheckResponse(BaseModel):
    success: bool
    errors: list[str]


class IntegrationSummary(BaseModel):
    id: str
    provider: str
    display_name: str
    created_at: datetime
    updated_at: datetime
    has_oauth_json: bool
    has_api_key: bool
    has_oauth_token: bool


class IntegrationDeleteRequest(BaseModel):
    password: str
