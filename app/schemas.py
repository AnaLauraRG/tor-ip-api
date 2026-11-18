"""Formatos de entrada y salida de la API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, field_validator

from app.models import Role


class IPListResponse(BaseModel):
    count: int
    ips: list[str]


class ExclusionCreate(BaseModel):
    # IPvAnyAddress rechaza con 422 todo lo que no sea una IPv4 o IPv6 válida.
    ip: IPvAnyAddress
    reason: str | None = Field(default=None, max_length=255)


class ExclusionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ip: str
    reason: str | None
    created_at: datetime


class SourceStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    last_status: str
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    ip_count: int


class HealthResponse(BaseModel):
    status: str
    sources: list[SourceStatusResponse]


class RefreshResponse(BaseModel):
    results: dict[str, str]
    sources: list[SourceStatusResponse]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12)
    role: Role = Role.READER

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        # bcrypt solo usa los primeros 72 bytes; se rechaza lo que exceda.
        if len(value.encode()) > 72:
            raise ValueError("La contraseña no puede exceder 72 bytes")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    role: str
    is_active: bool
    created_at: datetime


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    username: str | None
    method: str
    path: str
    status_code: int
    client_ip: str | None
    user_agent: str | None
    duration_ms: int
