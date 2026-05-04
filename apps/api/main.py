"""FastAPI entry point for Lunar MineOps AI OS."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import init_db
from app.routers import (
    agent,
    approvals,
    demo,
    health,
    missions,
    planning,
    reports,
    simulation,
    sources,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lunar MineOps AI OS",
        description=(
            "Mission Readiness Agent for Lunar ISRU. Simulation only. "
            "Not flight critical. Validates whether an autonomous "
            "lunar excavation-to-processing concept closes operationally."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(demo.router)
    app.include_router(missions.router)
    app.include_router(planning.router)
    app.include_router(simulation.router)
    app.include_router(approvals.router)
    app.include_router(reports.router)
    app.include_router(agent.router)

    return app


app = create_app()
