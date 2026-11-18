"""Configuración de la aplicación, leída de variables de entorno o del archivo .env."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./tor.db"

    # --- Fuentes externas ---
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

    # --- Autenticación ---
    # Clave para firmar los JWT. Obligatoria; la aplicación no arranca sin ella.
    jwt_secret: str = ""
    jwt_expire_min: int = Field(default=30, ge=1, le=1440)
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    # Administrador inicial: se crea al arrancar si todavía no existe.
    admin_username: str = "admin"
    admin_password: str = ""

    # Límite de intentos fallidos de login por IP de origen.
    login_max_attempts: int = Field(default=5, ge=1)
    login_window_min: int = Field(default=15, ge=1)


settings = Settings()
