"""Endpoint para registrar IPs excluidas."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExcludedIP
from app.schemas import ExclusionCreate, ExclusionResponse

router = APIRouter(prefix="/exclusions", tags=["exclusions"])


@router.post(
    "",
    response_model=ExclusionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Excluir una IP del listado filtrado",
)
def add_exclusion(payload: ExclusionCreate, db: Session = Depends(get_db)) -> ExcludedIP:
    """Agrega una IP a la base de exclusiones. Responde 409 si ya estaba registrada."""
    # str() sobre la IP ya validada da su forma canónica, la misma que usa la ingesta.
    exclusion = ExcludedIP(ip=str(payload.ip), reason=payload.reason)
    db.add(exclusion)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="La IP ya está excluida"
        ) from None
    return exclusion
