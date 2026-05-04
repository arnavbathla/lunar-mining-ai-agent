"""Source ingestion tests."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.source_service import (
    FACT_CATEGORIES,
    SOURCES,
    ensure_sources_seeded,
    get_source_context,
    list_sources,
    refresh_sources,
)


def _failing_fetcher(url: str) -> str:
    raise RuntimeError("network disabled in tests")


def _stub_html_fetcher(url: str) -> str:
    return (
        "<html><body>"
        "<nav>nav</nav>"
        "<main>"
        "<h1>NASA Source Page</h1>"
        "<p>NASA Moon to Mars architecture spans transportation, habitation, "
        "mobility, autonomy, ISRU, power, and communications. The architecture "
        "supports sustained lunar surface operations with autonomous robotics "
        "performing excavation, hauling, and processing of lunar regolith. "
        "Solar power generation and battery storage form a distribution network "
        "that supports hauler mobility and processor heat budgets. LOLA/LRO data "
        "informs polar topography, slope distributions, and dig site planning. "
        "Logistics and supply chains deliver cargo to lunar surface depots.</p>"
        "</main>"
        "<footer>footer</footer>"
        "</body></html>"
    )


def test_fallback_when_fetch_fails(db: Session) -> None:
    result = refresh_sources(db, fetcher=_failing_fetcher)
    db.commit()

    assert result["used_fallback"] is True
    assert result["failed"] == len(SOURCES)
    docs = list_sources(db)
    assert len(docs) == len(SOURCES)
    assert all(d.is_fallback for d in docs)
    assert all(d.fetched_at is not None for d in docs)


def test_live_fetch_with_stub(db: Session) -> None:
    result = refresh_sources(db, fetcher=_stub_html_fetcher)
    db.commit()

    assert result["used_fallback"] is False
    assert result["refreshed"] == len(SOURCES)
    docs = list_sources(db)
    assert len(docs) == len(SOURCES)
    assert all(not d.is_fallback for d in docs)
    assert all(d.status == "ok" for d in docs)


def test_context_returns_required_categories(db: Session) -> None:
    refresh_sources(db, fetcher=_stub_html_fetcher)
    db.commit()

    ctx = get_source_context(db)
    assert ctx["last_refreshed_at"] is not None
    assert isinstance(ctx["facts"], list)
    seen = {f["category"] for f in ctx["facts"]}
    # The stub HTML should produce facts for at least 3 categories.
    assert len(seen.intersection(FACT_CATEGORIES)) >= 3


def test_ensure_seeded_when_empty(db: Session) -> None:
    out = ensure_sources_seeded(db)
    db.commit()
    assert out["used_fallback"] is True
    docs = list_sources(db)
    assert len(docs) == len(SOURCES)
