"""Shared pytest fixtures for the Lunar MineOps backend."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure tests use an isolated SQLite file under tests/.tmp
_TEST_DIR = Path(__file__).parent / ".tmp"
_TEST_DIR.mkdir(exist_ok=True)


@pytest.fixture()
def db(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "lunar_test.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    from app.db.database import Base
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
