"""Endpoints de la base de IPs excluidas."""

import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExcludedIP
from app.schemas import ExclusionCreate, ExclusionResponse
from app.security import require_admin, require_reader

router = APIRouter(prefix="/exclusions", tags=["exclusions"])


@router.get(
    "",
    response_model=list[ExclusionResponse],
    summary="Listar las IPs excluidas",
    dependencies=[Depends(require_reader)],
)
def list_exclusions(db: Session = Depends(get_db)) -> list[ExcludedIP]:
    """Devuelve las IPs excluidas con su motivo y fecha, de la más reciente a la más antigua."""
    return list(
        db.scalars(
            select(ExcludedIP).order_by(ExcludedIP.created_at.desc(), ExcludedIP.ip)
        ).all()
    )


@router.post(
    "",
    response_model=ExclusionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Excluir una IP del listado filtrado",
    dependencies=[Depends(require_admin)],
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


@router.delete(
    "/{ip}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar una IP de las exclusiones",
    dependencies=[Depends(require_admin)],
)
def delete_exclusion(ip: str, db: Session = Depends(get_db)) -> Response:
    """Elimina la exclusión. Responde 404 si la IP no estaba excluida."""
    try:
        canonical = str(ipaddress.ip_address(ip))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No es una IPv4 o IPv6 válida",
        ) from None
    exclusion = db.get(ExcludedIP, canonical)
    if exclusion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="La IP no está excluida"
        )
    db.delete(exclusion)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
