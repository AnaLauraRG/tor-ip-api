"""Punto de entrada de la API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registra las tablas en Base)
from app.config import settings
from app.database import Base, engine
from app.routers import exclusions, health, ips
from app.services.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
# httpx registra a nivel INFO la URL completa de cada petición, y la de
# bigdatacloud lleva la API key; se sube el nivel para que no llegue a los logs.
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler = start_scheduler() if settings.scheduler_enabled else None
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Tor IP API",
    description="Listado unificado de IPs de Tor con soporte de exclusiones.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ips.router)
app.include_router(exclusions.router)
app.include_router(health.router)
