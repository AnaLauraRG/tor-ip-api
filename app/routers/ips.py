"""Endpoints de consulta de IPs de Tor."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExcludedIP, TorIP
from app.schemas import IPListResponse

router = APIRouter(prefix="/ips", tags=["ips"])


@router.get("", response_model=IPListResponse, summary="Todas las IPs de Tor")
def list_ips(db: Session = Depends(get_db)) -> IPListResponse:
    """Devuelve todas las IPs de Tor obtenidas de las fuentes externas, sin duplicados."""
    ips = db.scalars(select(TorIP.ip).distinct().order_by(TorIP.ip)).all()
    return IPListResponse(count=len(ips), ips=list(ips))


@router.get(
    "/filtered", response_model=IPListResponse, summary="IPs de Tor sin las excluidas"
)
def list_filtered_ips(db: Session = Depends(get_db)) -> IPListResponse:
    """Devuelve las IPs de Tor exceptuando las que están en la tabla de exclusiones."""
    ips = db.scalars(
        select(TorIP.ip)
        .where(TorIP.ip.not_in(select(ExcludedIP.ip)))
        .distinct()
        .order_by(TorIP.ip)
    ).all()
    return IPListResponse(count=len(ips), ips=list(ips))
