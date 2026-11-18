"""Tablas de la base de datos."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona horaria; aquí se normalizan a UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class Role(StrEnum):
    ADMIN = "admin"
    READER = "reader"


class TorIP(Base):
    """IP de Tor reportada por una fuente. Una misma IP puede venir de varias fuentes."""

    __tablename__ = "tor_ips"
    __table_args__ = (Index("ix_tor_ips_last_seen", "last_seen"),)

    # 45 caracteres alcanzan para la IPv6 más larga en texto.
    ip: Mapped[str] = mapped_column(String(45), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExcludedIP(Base):
    """IP que no debe aparecer en el listado filtrado."""

    __tablename__ = "excluded_ips"

    ip: Mapped[str] = mapped_column(String(45), primary_key=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceStatus(Base):
    """Estado de la última descarga de cada fuente. Persiste entre reinicios
    para respetar los límites de descarga de las fuentes."""

    __tablename__ = "source_status"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str] = mapped_column(String(16), default="pending")
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_count: Mapped[int] = mapped_column(Integer, default=0)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    # Hash bcrypt; la contraseña en claro nunca se guarda.
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Registro de cada petición a la API, incluidas las rechazadas."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_timestamp", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Usuario autenticado, o el usuario que se intentó en un login.
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(255))
    status_code: Mapped[int] = mapped_column(Integer)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
