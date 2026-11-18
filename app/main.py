"""Punto de entrada de la API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app import models  # noqa: F401  (registra las tablas en Base)
from app.audit import audit_middleware
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Role, User
from app.routers import audit, auth, exclusions, health, ips, sources, users
from app.security import hash_password
from app.services.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
# httpx registra a nivel INFO la URL de cada petición; se sube el nivel para
# no llenar los logs y como defensa adicional por si una URL llevara datos sensibles.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

MIN_JWT_SECRET_LENGTH = 32


def _check_config() -> None:
    if len(settings.jwt_secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET debe tener al menos {MIN_JWT_SECRET_LENGTH} caracteres. "
            "Genera uno con: openssl rand -base64 48"
        )


def _ensure_admin() -> None:
    """Crea el administrador inicial si no existe. No cambia la contraseña de
    un administrador que ya exista: el .env solo sirve para el primer arranque."""
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == settings.admin_username)):
            return
        if not settings.admin_password:
            logger.warning(
                "ADMIN_PASSWORD no está definida: no se creó el administrador inicial"
            )
            return
        if len(settings.admin_password) < 12:
            raise RuntimeError("ADMIN_PASSWORD debe tener al menos 12 caracteres")
        db.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role=Role.ADMIN.value,
            )
        )
        db.commit()
        logger.info("Administrador inicial '%s' creado", settings.admin_username)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_config()
    Base.metadata.create_all(bind=engine)
    _ensure_admin()
    scheduler = start_scheduler() if settings.scheduler_enabled else None
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Tor IP API",
    description=(
        "Listado unificado de IPs de Tor con soporte de exclusiones.\n\n"
        "Para probar desde esta página: pulsa **Authorize**, escribe tu usuario "
        "y contraseña, y los endpoints protegidos usarán tu token."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.middleware("http")(audit_middleware)

app.include_router(auth.router)
app.include_router(ips.router)
app.include_router(exclusions.router)
app.include_router(sources.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(health.router)
