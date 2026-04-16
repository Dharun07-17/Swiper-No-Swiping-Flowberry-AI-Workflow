from datetime import datetime
from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class MFARequest(BaseModel):
    mfa_token: str
    otp_code: str = Field(min_length=6, max_length=6)


class MFACodeRequest(BaseModel):
    otp_code: str = Field(min_length=6, max_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    success: bool = True
    data: TokenPair | dict
    message: str


class UserSummary(BaseModel):
    id: str
    role: str
    mfa_enabled: bool
    created_at: datetime
