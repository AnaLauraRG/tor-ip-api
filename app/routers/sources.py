"""Actualización manual de las fuentes (solo administradores)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.models import SourceStatus
from app.schemas import RefreshResponse
from app.security import require_admin
from app.services.scheduler import run_ingestion

router = APIRouter(
    prefix="/sources", tags=["sources"], dependencies=[Depends(require_admin)]
)


@router.post("/refresh", response_model=RefreshResponse, summary="Actualizar las fuentes")
async def refresh_sources(db: Session = Depends(get_db)) -> RefreshResponse:
    """Descarga de inmediato las fuentes, sin esperar su intervalo normal.

    Aun así respeta un mínimo por fuente: dan.me.uk nunca se consulta más de
    una vez cada 30 minutos. Las fuentes que no se pudieron consultar aparecen
    como "skipped".
    """
    results = await run_in_threadpool(run_ingestion, True)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una actualización en curso",
        )
    db.expire_all()
    sources = db.scalars(select(SourceStatus).order_by(SourceStatus.source)).all()
    return RefreshResponse(results=results, sources=list(sources))
