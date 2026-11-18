"""Estado del servicio y de las fuentes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SourceStatus
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        sources = db.scalars(select(SourceStatus).order_by(SourceStatus.source)).all()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible",
        ) from None
    return HealthResponse(status="ok", sources=list(sources))
