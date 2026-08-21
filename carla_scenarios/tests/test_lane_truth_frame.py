"""Unit tests for ego-frame lane helpers (no CARLA).

CARLA/Unreal: X forward, Y right+. Gold frame: y left+.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
sys.path.insert(0, str(_LIB))

from _lane_truth import (  # noqa: E402
    _dedup_edges,
    world_to_ego_xy,
)


class _Loc:
    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        self.x, self.y, self.z = x, y, z


class _Rot:
    def __init__(self, yaw: float) -> None:
        self.yaw = yaw


class _Tf:
    def __init__(self, x: float, y: float, yaw_deg: float) -> None:
        self.location = _Loc(x, y)
        self.rotation = _Rot(yaw_deg)


def _ego(x: float = 0.0, y: float = 0.0, yaw_deg: float = 0.0):
    return SimpleNamespace(get_transform=lambda: _Tf(x, y, yaw_deg))


def test_world_to_ego_ue_left_is_positive_yaw0():
    """UE left = −Y at yaw=0 → gold y_left > 0."""
    ego = _ego(0.0, 0.0, 0.0)
    xf, yf = world_to_ego_xy(ego, 0.0, -1.0)
    assert abs(xf) < 1e-9
    assert yf == pytest.approx(1.0, abs=1e-9)


def test_world_to_ego_ue_right_is_negative_yaw0():
    ego = _ego(0.0, 0.0, 0.0)
    _xf, yf = world_to_ego_xy(ego, 0.0, 1.0)
    assert yf == pytest.approx(-1.0, abs=1e-9)


def test_world_to_ego_forward_yaw0():
    ego = _ego(0.0, 0.0, 0.0)
    xf, yf = world_to_ego_xy(ego, 5.0, 0.0)
    assert xf == pytest.approx(5.0, abs=1e-9)
    assert abs(yf) < 1e-9


def test_world_to_ego_left_yaw90():
    # Facing +Y (yaw=90): UE left = +X
    ego = _ego(0.0, 0.0, 90.0)
    xf, yf = world_to_ego_xy(ego, 1.0, 0.0)
    assert abs(xf) < 1e-6
    assert yf == pytest.approx(1.0, abs=1e-6)


def test_dedup_merges_shared_edge():
    raw = [
        {"c0": 1.75, "c1": 0.0, "c2": 0.0, "lane_i": 0},
        {"c0": -1.75, "c1": 0.0, "c2": 0.0, "lane_i": 0},
        {"c0": -1.74, "c1": 0.0, "c2": 0.0, "lane_i": 1},
        {"c0": -5.25, "c1": 0.0, "c2": 0.0, "lane_i": 1},
        {"c0": -8.75, "c1": 0.0, "c2": 0.0, "lane_i": 2},
    ]
    edges = _dedup_edges(raw, merge_m=0.35)
    assert len(edges) == 4  # 3 lanes → 4 boundaries
    assert edges[0]["c0"] == pytest.approx(1.75, abs=0.05)
    assert edges[-1]["c0"] == pytest.approx(-8.75, abs=0.05)


def test_fit_straight_c2_near_zero():
    from _lane_truth import _fit_c0_c1_c2

    xs = [0.0, 10.0, 20.0, 40.0, 60.0]
    ys = [1.75, 1.75, 1.75, 1.75, 1.75]
    c0, c1, c2 = _fit_c0_c1_c2(xs, ys)
    assert c0 == pytest.approx(1.75, abs=1e-6)
    assert abs(c1) < 1e-9
    assert abs(c2) < 1e-9


def test_assess_lane_poly_ok():
    from _lane_truth import assess_lane_poly_quality

    q = assess_lane_poly_quality(
        host_left_c0=1.75, host_right_c0=-1.75, host_c1=0.0, host_c2=0.0, lane_width_m=3.5
    )
    assert q["lane_avail"] == 2
    assert q["lane_conf"] > 0.8
    assert q["lane_vr_end_m"] >= 100.0


def test_assess_lane_poly_invalid_large_yaw():
    from _lane_truth import assess_lane_poly_quality

    # C1≈tan(54°) like the blob frame
    q = assess_lane_poly_quality(
        host_left_c0=-2.88,
        host_right_c0=-5.87,
        host_c1=1.37,
        host_c2=-0.05,
        lane_width_m=3.5,
    )
    assert q["lane_avail"] == 0
    assert q["lane_vr_end_m"] < 0.5
    assert q["lane_conf"] < 0.1


def test_assess_lane_poly_lat_offset_soft_not_blackout():
    """Large mid alone → degrade + short VR, still drawable (avail=1)."""
    from _lane_truth import assess_lane_poly_quality

    q = assess_lane_poly_quality(
        host_left_c0=-4.22,
        host_right_c0=-9.97,
        host_c1=-0.28,
        host_c2=0.0,
        lane_width_m=3.5,
    )
    assert q["lane_avail"] == 1
    assert q["lane_vr_end_m"] >= 20.0
    assert q["lane_conf"] >= 0.3
    assert "lat" in q["reason"]


def test_assess_lane_poly_degraded():
    from _lane_truth import assess_lane_poly_quality
    import math

    q = assess_lane_poly_quality(
        host_left_c0=1.75,
        host_right_c0=-1.75,
        host_c1=math.tan(math.radians(28)),
        host_c2=0.0,
        lane_width_m=3.5,
    )
    assert q["lane_avail"] == 1
    assert q["lane_vr_end_m"] <= 35.0
