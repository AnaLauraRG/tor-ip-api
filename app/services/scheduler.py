"""Planificador que ejecuta el ciclo de ingesta en segundo plano."""

import logging
from datetime import UTC, datetime

import httpx
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.services.ingestion import run_cycle
from app.services.sources import build_sources

logger = logging.getLogger(__name__)


def run_ingestion(force: bool = False) -> dict[str, str]:
    """Ejecuta un ciclo de ingesta con un cliente HTTP configurado."""
    transport = httpx.HTTPTransport(retries=1)
    headers = {"User-Agent": "tor-ip-api/1.0"}
    with httpx.Client(
        timeout=settings.http_timeout_s,
        transport=transport,
        headers=headers,
        follow_redirects=True,
    ) as client:
        return run_cycle(
            SessionLocal,
            build_sources(settings),
            client,
            settings.stale_after_hours,
            force=force,
        )


def start_scheduler() -> BackgroundScheduler:
    """Arranca el planificador. El primer ciclo corre de inmediato; los
    siguientes, cada scheduler_tick_min minutos. Cada ciclo solo descarga las
    fuentes cuyo intervalo ya venció."""
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_ingestion,
        "interval",
        minutes=settings.scheduler_tick_min,
        next_run_time=datetime.now(UTC),
        max_instances=1,
        coalesce=True,
        id="ingestion",
    )
    scheduler.start()
    logger.info("Planificador de ingesta iniciado")
    return scheduler
