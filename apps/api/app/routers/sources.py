"""Source ingestion routes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.api import SourcesContextOut, SourcesRefreshOut
from app.schemas.domain import SourceDocumentOut
from app.services.source_service import (
    ensure_sources_seeded,
    get_source_context,
    list_sources,
    refresh_sources,
)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=List[SourceDocumentOut])
def list_sources_route(db: Session = Depends(get_db)) -> List[SourceDocumentOut]:
    docs = list_sources(db)
    return [SourceDocumentOut.model_validate(d) for d in docs]


@router.post("/refresh", response_model=SourcesRefreshOut)
def refresh_sources_route(
    force: bool = Query(False),
    db: Session = Depends(get_db),
) -> SourcesRefreshOut:
    result = refresh_sources(db, force=force)
    db.commit()
    docs = list_sources(db)
    return SourcesRefreshOut(
        refreshed=result["refreshed"],
        failed=result["failed"],
        used_fallback=result["used_fallback"],
        sources=[SourceDocumentOut.model_validate(d) for d in docs],
    )


@router.get("/context", response_model=SourcesContextOut)
def context_route(
    categories: Optional[List[str]] = Query(default=None),
    db: Session = Depends(get_db),
) -> SourcesContextOut:
    ensure_sources_seeded(db)
    db.commit()
    ctx = get_source_context(db, categories)
    return SourcesContextOut(
        last_refreshed_at=ctx["last_refreshed_at"],
        used_fallback=ctx["used_fallback"],
        facts=ctx["facts"],
        sources=ctx["sources"],
    )
