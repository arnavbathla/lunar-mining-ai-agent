"""Synthetic site generator tests."""
from __future__ import annotations

from app.simulation.site_generator import GRID_H, GRID_W, generate_site


REQUIRED_FIELDS = {
    "x",
    "y",
    "elevation_m",
    "slope_deg",
    "illumination_pct",
    "resource_score",
    "hazard_score",
    "comms_quality",
    "temperature_c",
    "mineability_score",
}


def test_generates_30x30() -> None:
    cells = generate_site(seed=42)
    assert len(cells) == GRID_W * GRID_H


def test_all_cells_have_required_fields() -> None:
    cells = generate_site(seed=42)
    for cell in cells:
        assert REQUIRED_FIELDS.issubset(cell.keys())


def test_values_in_valid_ranges() -> None:
    cells = generate_site(seed=42)
    for cell in cells:
        assert 0.0 <= cell["mineability_score"] <= 1.0
        assert 0.0 <= cell["resource_score"] <= 1.05  # tiny noise tolerance
        assert 0.0 <= cell["hazard_score"] <= 1.05
        assert 0.0 <= cell["comms_quality"] <= 1.05
        assert 0.0 <= cell["illumination_pct"] <= 100.0
        assert 0.0 <= cell["slope_deg"] <= 30.0


def test_deterministic_with_seed() -> None:
    a = generate_site(seed=42)
    b = generate_site(seed=42)
    assert a == b
    c = generate_site(seed=43)
    assert a != c
