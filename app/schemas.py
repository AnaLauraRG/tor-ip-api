"""Formatos de entrada y salida de la API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


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
