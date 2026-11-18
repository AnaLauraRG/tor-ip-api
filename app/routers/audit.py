"""Consulta del registro de auditoría (solo administradores)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog
from app.schemas import AuditEntry
from app.security import require_admin

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[AuditEntry], summary="Registro de auditoría")
def list_audit(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    username: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    """Devuelve las peticiones registradas, de la más reciente a la más antigua."""
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit).offset(offset)
    if username:
        query = query.where(AuditLog.username == username)
    return list(db.scalars(query).all())
