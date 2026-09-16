"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SAS_", extra="ignore")

    # --- Core ---
    app_name: str = "Solar Array Simulator Control Platform"
    environment: str = "development"
    debug: bool = True

    # --- SAFETY: master switch for real hardware. Disabled by default. ---
    # When False, every device uses MockE4360Driver regardless of its profile.
    hardware_enabled: bool = False
    simulation_banner: bool = True

    # --- Database ---
    database_url: str = "postgresql+asyncpg://sas:sas@db:5432/sas"
    # sync URL used by Alembic / seed scripts
    database_url_sync: str = "postgresql+psycopg://sas:sas@db:5432/sas"

    # --- Redis (optional event bus / cache) ---
    redis_url: str = "redis://redis:6379/0"
    redis_enabled: bool = True

    # --- Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 720
    # Dev-only: trust an X-Dev-User header to impersonate a seeded user.
    dev_auth_enabled: bool = True

    # --- Telemetry simulation ---
    telemetry_interval_seconds: float = 1.0
    measurement_retention_days: int = 30

    # --- Safety soft limits (hardware limits remain ultimate authority) ---
    max_voltage_v: float = 130.0
    max_current_a: float = 20.0
    command_timeout_seconds: float = 10.0

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
