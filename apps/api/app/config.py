"""Application configuration."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime settings loaded from environment variables.

    The backend boots even if ANTHROPIC_API_KEY is missing; deterministic
    endpoints still function and only the agent endpoints will refuse.
    """

    def __init__(self) -> None:
        self.ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.ANTHROPIC_MODEL: str = os.getenv(
            "ANTHROPIC_MODEL", "claude-sonnet-4-6"
        ).strip()
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL", "sqlite:///./lunar_mineops.db"
        ).strip()
        cors = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        self.CORS_ORIGINS: List[str] = [
            origin.strip() for origin in cors.split(",") if origin.strip()
        ]
        self.SOURCE_REFRESH_MODE: str = os.getenv(
            "SOURCE_REFRESH_MODE", "live"
        ).strip()

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
