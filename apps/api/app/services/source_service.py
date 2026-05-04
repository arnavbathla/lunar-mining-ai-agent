"""Public NASA/PDS source ingestion service.

Fetches official source pages, extracts deterministic facts via keyword
matching, and persists them as ``SourceDocument`` rows. Falls back to
hard-coded facts when the network is unavailable so the rest of the
product remains functional offline.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SourceDocument

SOURCES: List[Dict[str, str]] = [
    {
        "key": "moon_to_mars_architecture",
        "url": "https://www.nasa.gov/moontomarsarchitecture/",
        "title": "NASA Moon to Mars Architecture",
        "category": "moon_to_mars_architecture",
    },
    {
        "key": "moon_to_mars_components",
        "url": "https://www.nasa.gov/moontomarsarchitecture-components/",
        "title": "NASA Moon to Mars Architecture Components",
        "category": "subarchitecture",
    },
    {
        "key": "isru_overview",
        "url": "https://www.nasa.gov/overview-in-situ-resource-utilization/",
        "title": "NASA ISRU Overview",
        "category": "isru",
    },
    {
        "key": "jsc_isru",
        "url": "https://www.nasa.gov/reference/jsc-in-situ-resource-utilization/",
        "title": "NASA JSC ISRU Capabilities",
        "category": "isru",
    },
    {
        "key": "pds_lola",
        "url": "https://pds-geosciences.wustl.edu/missions/lro/lola.htm",
        "title": "PDS Geosciences LRO LOLA",
        "category": "topography_data",
    },
    {
        "key": "lola_mission",
        "url": "https://science.nasa.gov/mission/lro/lola/",
        "title": "NASA LOLA Mission Page",
        "category": "topography_data",
    },
]

# 9 categories used to classify extracted facts.
FACT_CATEGORIES: Tuple[str, ...] = (
    "moon_to_mars_architecture",
    "subarchitecture",
    "isru",
    "topography_data",
    "power",
    "mobility",
    "autonomy",
    "logistics",
    "infrastructure",
)

CATEGORY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "moon_to_mars_architecture": (
        "moon to mars",
        "architecture",
        "campaign",
        "exploration",
    ),
    "subarchitecture": (
        "transportation",
        "habitation",
        "communications",
        "lunar surface",
        "mars surface",
        "operations",
    ),
    "isru": (
        "in-situ resource",
        "in situ resource",
        "isru",
        "regolith",
        "water",
        "oxygen",
        "fuel",
        "extraction",
    ),
    "topography_data": (
        "lola",
        "lro",
        "topograph",
        "elevation",
        "altimeter",
        "dem",
        "polar",
        "slope",
    ),
    "power": (
        "power",
        "solar",
        "fission",
        "battery",
        "energy",
        "watt",
    ),
    "mobility": (
        "mobility",
        "rover",
        "traverse",
        "drive",
        "wheel",
        "navigation",
    ),
    "autonomy": (
        "autonom",
        "robot",
        "ai",
        "machine learning",
        "decision",
        "planning",
    ),
    "logistics": (
        "logistics",
        "supply",
        "cargo",
        "delivery",
        "manifest",
    ),
    "infrastructure": (
        "infrastructure",
        "habitat",
        "facility",
        "depot",
        "communication",
        "network",
    ),
}


# ---------------------------------------------------------------------------
# Fallback content (used when fetch fails or live mode disabled)
# ---------------------------------------------------------------------------

FALLBACK_FACTS: Dict[str, List[str]] = {
    "moon_to_mars_architecture": [
        "NASA Moon-to-Mars architecture context is relevant to sustained lunar operations.",
    ],
    "subarchitecture": [
        "Relevant components include Autonomous Systems and Robotics, ISRU, Data Systems, Infrastructure Support, Logistics, Mobility, and Power Systems.",
    ],
    "isru": [
        "ISRU involves using lunar resources to produce useful supplies such as water, fuel, oxygen, construction materials, and other mission resources.",
        "Lunar surface operations depend on excavation, resource handling, processing, mobility, power, communications, and autonomy.",
    ],
    "topography_data": [
        "LOLA/LRO data is relevant for lunar topography, slopes, terrain, and site planning.",
        "The MVP uses synthetic terrain and does not ingest raw LOLA DEM products.",
    ],
    "power": [
        "Lunar surface operations depend on power generation, storage, and distribution including solar arrays and batteries.",
    ],
    "mobility": [
        "Mobility systems support traverse to dig zones and processing facilities; haulers and rovers are typical asset classes.",
    ],
    "autonomy": [
        "Autonomy and robotics handle excavation, hauling, processing, and inspection with minimal human teleoperation.",
    ],
    "logistics": [
        "Logistics span surface delivery, payload handling, and supply chains supporting sustained operations.",
    ],
    "infrastructure": [
        "Infrastructure includes habitats, communications relays, depots, and processing facilities.",
    ],
}


@dataclass
class FetchResult:
    key: str
    url: str
    title: str
    primary_category: str
    status: str  # ok | failed | fallback
    raw_text: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _default_fetcher(url: str) -> str:
    """Fetch a URL and return its text. Raises on non-200."""
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        response = client.get(
            url,
            headers={
                "User-Agent": (
                    "LunarMineOpsAIOS/0.1 (Mission Readiness MVP; +local-dev)"
                ),
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()
        return response.text


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["nav", "footer", "script", "style", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Collapse whitespace.
    return " ".join(text.split())


def _classify_sentence(sentence: str) -> List[str]:
    s = sentence.lower()
    matches: List[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in s for kw in keywords):
            matches.append(category)
    return matches


def _split_sentences(text: str, limit: int = 200) -> List[str]:
    # Crude but deterministic sentence splitter.
    raw = text.replace("\n", " ").replace("\r", " ")
    chunks: List[str] = []
    buf = ""
    for ch in raw:
        buf += ch
        if ch in ".!?" and len(buf.strip()) > 30:
            chunks.append(buf.strip())
            buf = ""
            if len(chunks) >= limit:
                break
    if buf.strip() and len(chunks) < limit:
        chunks.append(buf.strip())
    return chunks


def _extract_facts(
    text: str, primary_category: str
) -> Dict[str, List[str]]:
    """Categorise sentences from cleaned page text."""
    facts: Dict[str, List[str]] = {cat: [] for cat in FACT_CATEGORIES}
    sentences = _split_sentences(text, limit=400)

    for sentence in sentences:
        if len(sentence) < 40 or len(sentence) > 360:
            continue
        cats = _classify_sentence(sentence)
        if not cats and primary_category:
            cats = [primary_category]
        for cat in cats:
            if cat not in facts:
                continue
            if len(facts[cat]) >= 4:
                continue
            if sentence not in facts[cat]:
                facts[cat].append(sentence)

    # Always seed primary category with at least the title-derived hint.
    if primary_category and not facts[primary_category]:
        facts[primary_category].append(
            f"Source page primarily covers {primary_category.replace('_', ' ')}."
        )
    return facts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:32]


def _store_fallback_doc(
    db: Session, source_meta: Dict[str, str]
) -> SourceDocument:
    """Insert (or overwrite) a fallback SourceDocument for a single source."""
    facts: Dict[str, List[str]] = {cat: [] for cat in FACT_CATEGORIES}
    primary = source_meta.get("category", "")
    if primary in FALLBACK_FACTS:
        facts[primary] = list(FALLBACK_FACTS[primary])

    # Attach generic fallback facts to other categories so /sources/context is
    # populated for downstream prompts.
    for cat, lines in FALLBACK_FACTS.items():
        if cat != primary and not facts[cat]:
            facts[cat] = list(lines)

    raw_excerpt = (
        f"[FALLBACK] Cached snapshot of {source_meta['title']} "
        f"({source_meta['url']}). Live fetch unavailable; "
        "deterministic facts loaded from local fallback set."
    )

    existing = (
        db.execute(
            select(SourceDocument).where(SourceDocument.url == source_meta["url"])
        )
        .scalars()
        .first()
    )
    if existing:
        existing.title = source_meta["title"]
        existing.fetched_at = datetime.now(timezone.utc)
        existing.status = "fallback"
        existing.content_hash = _hash_text(raw_excerpt)
        existing.raw_excerpt = raw_excerpt
        existing.extracted_facts_json = facts
        existing.is_fallback = True
        db.flush()
        return existing

    doc = SourceDocument(
        id=str(uuid.uuid4()),
        url=source_meta["url"],
        title=source_meta["title"],
        fetched_at=datetime.now(timezone.utc),
        status="fallback",
        content_hash=_hash_text(raw_excerpt),
        raw_excerpt=raw_excerpt,
        extracted_facts_json=facts,
        is_fallback=True,
    )
    db.add(doc)
    db.flush()
    return doc


def _store_live_doc(
    db: Session, source_meta: Dict[str, str], result: FetchResult
) -> SourceDocument:
    facts = _extract_facts(result.raw_text, result.primary_category)
    excerpt = result.raw_text[:2000]

    existing = (
        db.execute(
            select(SourceDocument).where(SourceDocument.url == source_meta["url"])
        )
        .scalars()
        .first()
    )
    if existing:
        existing.title = source_meta["title"]
        existing.fetched_at = datetime.now(timezone.utc)
        existing.status = "ok"
        existing.content_hash = _hash_text(result.raw_text)
        existing.raw_excerpt = excerpt
        existing.extracted_facts_json = facts
        existing.is_fallback = False
        db.flush()
        return existing

    doc = SourceDocument(
        id=str(uuid.uuid4()),
        url=source_meta["url"],
        title=source_meta["title"],
        fetched_at=datetime.now(timezone.utc),
        status="ok",
        content_hash=_hash_text(result.raw_text),
        raw_excerpt=excerpt,
        extracted_facts_json=facts,
        is_fallback=False,
    )
    db.add(doc)
    db.flush()
    return doc


def refresh_sources(
    db: Session,
    *,
    fetcher: Optional[Callable[[str], str]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Refresh all NASA/PDS source documents.

    Arguments:
        db: SQLAlchemy session (caller commits).
        fetcher: Override the URL fetcher (used by tests).
        force: Currently informational; refresh always re-fetches.
    """
    fetcher = fetcher or _default_fetcher
    refreshed = 0
    failed = 0
    used_fallback = False

    for meta in SOURCES:
        try:
            html = fetcher(meta["url"])
            text = _strip_html(html)
            if len(text) < 200:
                raise ValueError("page content too short")
            result = FetchResult(
                key=meta["key"],
                url=meta["url"],
                title=meta["title"],
                primary_category=meta["category"],
                status="ok",
                raw_text=text,
            )
            _store_live_doc(db, meta, result)
            refreshed += 1
        except Exception as exc:  # noqa: BLE001 - defensive: any failure -> fallback
            _store_fallback_doc(db, meta)
            failed += 1
            used_fallback = True
            _ = exc  # silence linter

    db.flush()

    docs = (
        db.execute(select(SourceDocument).order_by(SourceDocument.title))
        .scalars()
        .all()
    )

    return {
        "refreshed": refreshed,
        "failed": failed,
        "used_fallback": used_fallback,
        "sources": [
            {
                "id": d.id,
                "url": d.url,
                "title": d.title,
                "fetched_at": d.fetched_at.isoformat(),
                "status": d.status,
                "is_fallback": bool(d.is_fallback),
            }
            for d in docs
        ],
    }


def list_sources(db: Session) -> List[SourceDocument]:
    return (
        db.execute(select(SourceDocument).order_by(SourceDocument.title))
        .scalars()
        .all()
    )


def get_source_context(
    db: Session, categories: Optional[List[str]] = None
) -> Dict[str, Any]:
    docs = list_sources(db)
    if not docs:
        return {
            "last_refreshed_at": None,
            "used_fallback": False,
            "facts": [],
            "sources": [],
        }

    selected = categories or list(FACT_CATEGORIES)
    facts: List[Dict[str, Any]] = []
    for doc in docs:
        doc_facts: Dict[str, List[str]] = doc.extracted_facts_json or {}
        for cat in selected:
            for line in doc_facts.get(cat, []):
                facts.append(
                    {
                        "category": cat,
                        "fact": line,
                        "source_title": doc.title,
                        "source_url": doc.url,
                        "is_fallback": bool(doc.is_fallback),
                    }
                )

    last_refreshed = max(d.fetched_at for d in docs).isoformat()
    used_fallback = any(d.is_fallback for d in docs)

    return {
        "last_refreshed_at": last_refreshed,
        "used_fallback": used_fallback,
        "facts": facts,
        "sources": [
            {
                "id": d.id,
                "url": d.url,
                "title": d.title,
                "fetched_at": d.fetched_at.isoformat(),
                "status": d.status,
                "is_fallback": bool(d.is_fallback),
            }
            for d in docs
        ],
    }


def ensure_sources_seeded(db: Session) -> Dict[str, Any]:
    """If no source documents exist yet, populate fallback rows."""
    existing = list_sources(db)
    if existing:
        return {
            "refreshed": 0,
            "failed": 0,
            "used_fallback": any(d.is_fallback for d in existing),
            "sources": [
                {
                    "id": d.id,
                    "url": d.url,
                    "title": d.title,
                    "fetched_at": d.fetched_at.isoformat(),
                    "status": d.status,
                    "is_fallback": bool(d.is_fallback),
                }
                for d in existing
            ],
        }

    for meta in SOURCES:
        _store_fallback_doc(db, meta)
    db.flush()

    return refresh_sources_from_existing(db)


def refresh_sources_from_existing(db: Session) -> Dict[str, Any]:
    docs = list_sources(db)
    return {
        "refreshed": 0,
        "failed": 0,
        "used_fallback": any(d.is_fallback for d in docs),
        "sources": [
            {
                "id": d.id,
                "url": d.url,
                "title": d.title,
                "fetched_at": d.fetched_at.isoformat(),
                "status": d.status,
                "is_fallback": bool(d.is_fallback),
            }
            for d in docs
        ],
    }
