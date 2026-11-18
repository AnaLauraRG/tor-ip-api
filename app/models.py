"""Tablas de la base de datos."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona horaria; aquí se normalizan a UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


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
