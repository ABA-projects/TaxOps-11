"""Configuración centralizada con pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = ""

    # ── JWT ───────────────────────────────────────────────────────────────────
    SECRET_KEY: str = "CAMBIA_ESTO_EN_PRODUCCION_MIN_32_CHARS_AQUI_ABC"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # ── AI Keys ───────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # ── Google OAuth ──────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    API_BASE_URL: str = "http://localhost:8000"   # URL pública de la API (para redirect_uri de Google)
    FRONTEND_URL: str = "http://localhost:3000"  # URL pública del frontend (para redirect final post-login)

    # ── Superadmin ────────────────────────────────────────────────────────────
    TAXOPS_SUPERADMIN_EMAILS: str = ""

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
