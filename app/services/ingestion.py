"""Ciclo de ingesta: descarga las fuentes que toca y actualiza la tabla tor_ips."""

import logging
import threading
from datetime import timedelta

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models import SourceStatus, TorIP, as_utc, utcnow
from app.services.sources import Source, SourceError

logger = logging.getLogger(__name__)

# Evita que dos ciclos corran a la vez dentro del mismo proceso.
_cycle_lock = threading.Lock()

_CHUNK = 1000


def _insert_for(session: Session):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(f"Base de datos no soportada: {dialect}")
    return insert


def _upsert_ips(session: Session, source: str, ips: set[str]) -> None:
    """Inserta las IPs nuevas y refresca last_seen de las que ya existían."""
    insert = _insert_for(session)
    now = utcnow()
    rows = [
        {"ip": ip, "source": source, "first_seen": now, "last_seen": now}
        for ip in sorted(ips)
    ]
    for start in range(0, len(rows), _CHUNK):
        stmt = insert(TorIP).values(rows[start : start + _CHUNK])
        stmt = stmt.on_conflict_do_update(
            index_elements=[TorIP.ip, TorIP.source],
            set_={"last_seen": stmt.excluded.last_seen},
        )
        session.execute(stmt)


def _is_due(status: SourceStatus, interval_min: int) -> bool:
    last = as_utc(status.last_attempt_at)
    return last is None or utcnow() - last >= timedelta(minutes=interval_min)


def _ingest_source(session: Session, source: Source, client: httpx.Client) -> str:
    status = session.get(SourceStatus, source.name)
    if status is None:
        status = SourceStatus(source=source.name)
        session.add(status)

    if not source.enabled:
        status.last_status = "disabled"
        session.commit()
        return "disabled"

    # El intervalo se mide desde el último intento (no desde el último éxito),
    # para no insistir contra una fuente que está fallando o limitándonos.
    if not _is_due(status, source.interval_min):
        return "skipped"

    # Se guarda el intento antes de descargar: si el proceso se reinicia a
    # mitad de camino, el límite de la fuente se sigue respetando.
    status.last_attempt_at = utcnow()
    session.commit()

    try:
        ips = source.fetch(client)
        if not ips:
            raise SourceError("la fuente no devolvió ninguna IP válida")
        _upsert_ips(session, source.name, ips)
        status.last_status = "ok"
        status.last_error = None
        status.last_success_at = utcnow()
        status.ip_count = len(ips)
        session.commit()
        logger.info("Fuente %s: %d IPs", source.name, len(ips))
        return "ok"
    except SourceError as exc:
        # Los datos anteriores de la fuente se conservan.
        session.rollback()
        status = session.get(SourceStatus, source.name)
        status.last_status = "error"
        status.last_error = str(exc)[:255]
        session.commit()
        logger.warning("Fuente %s falló: %s", source.name, exc)
        return "error"


def _purge_stale(session: Session, stale_after_hours: int) -> int:
    cutoff = utcnow() - timedelta(hours=stale_after_hours)
    result = session.execute(delete(TorIP).where(TorIP.last_seen < cutoff))
    session.commit()
    return result.rowcount or 0


def run_cycle(
    session_factory: sessionmaker,
    sources: list[Source],
    client: httpx.Client,
    stale_after_hours: int,
) -> dict[str, str]:
    """Ejecuta un ciclo de ingesta y devuelve el resultado por fuente."""
    if not _cycle_lock.acquire(blocking=False):
        logger.info("Ya hay un ciclo de ingesta en curso; se omite este")
        return {}
    try:
        results = {}
        with session_factory() as session:
            for source in sources:
                try:
                    results[source.name] = _ingest_source(session, source, client)
                except Exception:
                    session.rollback()
                    logger.exception("Error inesperado en la fuente %s", source.name)
                    results[source.name] = "error"
            purged = _purge_stale(session, stale_after_hours)
            if purged:
                logger.info("Se eliminaron %d IPs obsoletas", purged)
        return results
    finally:
        _cycle_lock.release()
