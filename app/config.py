"""Configuración de la aplicación, leída de variables de entorno o del archivo .env."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./tor.db"

    torproject_url: str = "https://check.torproject.org/torbulkexitlist"
    danme_url: str = "https://www.dan.me.uk/torlist/?exit"
    bigdatacloud_url: str = "https://api-bdc.net/data/tor-exit-nodes-list"
    bigdatacloud_api_key: str = ""

    # Minutos mínimos entre descargas de cada fuente.
    # dan.me.uk bloquea a quien descarga más de una vez cada 30 minutos.
    torproject_interval_min: int = Field(default=60, ge=5)
    danme_interval_min: int = Field(default=60, ge=30)
    bigdatacloud_interval_min: int = Field(default=60, ge=5)

    scheduler_enabled: bool = True
    scheduler_tick_min: int = Field(default=5, ge=1)
    http_timeout_s: float = Field(default=15.0, gt=0)
    stale_after_hours: int = Field(default=48, ge=1)


settings = Settings()
