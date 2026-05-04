"""SQLAlchemy engine and session management."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def init_db() -> None:
    """Create all tables. Idempotent."""
    from app.db import models  # noqa: F401  (ensures models register)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for ad-hoc sessions outside FastAPI request scope."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
