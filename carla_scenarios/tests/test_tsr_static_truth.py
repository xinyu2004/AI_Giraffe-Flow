"""Unit tests for ME-style TSR id / Relevancy (no CARLA)."""

from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from _tsr_static_truth import (  # noqa: E402
    E_STOP_AHEAD,
    REL_FAR_IRRELEVANT,
    REL_OTHER_LANE,
    REL_RELEVANT,
    _tsr_sort_key,
    stable_tsr_id,
    tsr_relevancy,
)


def test_stable_tsr_id_range_and_fallback() -> None:
    assert stable_tsr_id(42) == 42
    assert stable_tsr_id(127) == 1  # 127 % 127 == 0 → fallback_slot 0 → 1
    assert stable_tsr_id(0, fallback_slot=3) == 4  # (3 % 127) + 1
    a = stable_tsr_id(1001)
    b = stable_tsr_id(1001)
    assert a == b and 1 <= a <= 127


def test_tsr_relevancy_host_other_far() -> None:
    # Speed / other signs: tight corridor.
    assert tsr_relevancy(0.5, 30.0, name=5) == REL_RELEVANT
    assert tsr_relevancy(2.0, 30.0, name=5) == REL_RELEVANT
    assert tsr_relevancy(3.5, 30.0, name=5) == REL_OTHER_LANE
    assert tsr_relevancy(8.0, 30.0, name=5) == REL_OTHER_LANE
    assert tsr_relevancy(9.0, 30.0, name=5) == REL_FAR_IRRELEVANT
    assert tsr_relevancy(0.5, -9.0, name=5) == REL_FAR_IRRELEVANT
    # Lights: roadside poles (Foxglove |lat|≈7.5) stay Relevant.
    assert tsr_relevancy(7.5, 6.0, name=E_STOP_AHEAD) == REL_RELEVANT
    assert tsr_relevancy(10.0, 6.0, name=196) == REL_RELEVANT
    assert tsr_relevancy(12.0, 6.0, name=164) == REL_OTHER_LANE
    assert tsr_relevancy(0.5, -3.0, name=196) == REL_RELEVANT  # within behind hold


def test_tsr_sort_relevant_stop_before_speed() -> None:
    speed = {"name": 5, "rel": REL_RELEVANT, "long": 10.0}
    far_red = {"name": E_STOP_AHEAD, "rel": REL_OTHER_LANE, "long": 40.0}
    host_red = {"name": E_STOP_AHEAD, "rel": REL_RELEVANT, "long": 50.0}
    ordered = sorted([speed, far_red, host_red], key=_tsr_sort_key)
    assert ordered[0] is host_red
    assert ordered[1]["name"] == 5 or ordered[1] is far_red
