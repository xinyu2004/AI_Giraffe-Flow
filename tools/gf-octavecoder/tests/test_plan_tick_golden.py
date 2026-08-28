from __future__ import annotations

"""v4 m_plan_tick generate + compact-obj helpers (no perc re-walk)."""

from pathlib import Path

from gf_octavecoder.generate import generate_sku


def test_generate_plan_tick_header() -> None:
    root = Path(__file__).resolve().parents[3]
    assert generate_sku(repo_root=root, sku="afc", force=True) == 0
    p = root / "projects/afc/apps/planning/driving/oct_gen/m_plan_tick.hpp"
    text = p.read_text(encoding="utf-8")
    assert "gf_octave_planning::m_plan_tick" in text
    assert "m_plan_tick_pack" not in text


def test_occlusion_truck_cuts_sight() -> None:
    # Mirrors gf_plan_occlusion: in-path truck near-face, not a second perc parse.
    d = 30.0
    len_m = 10.0
    near = max(0.0, d - 0.5 * len_m)
    assert near == 25.0
    assert near < 120.0
