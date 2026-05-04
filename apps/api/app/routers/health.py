"""Health check router."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.schemas.api import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(
        status="ok",
        anthropic_configured=settings.anthropic_configured,
    )
