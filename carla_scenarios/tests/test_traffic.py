"""Unit tests for ambient traffic mix (no CARLA world)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_SRC = Path(__file__).resolve().parents[1] / "src"
_LIB = _SRC / "lib"
for _p in (_SRC, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _traffic import (  # noqa: E402
    allow_ambient_peds,
    ambient_bp_allowed,
    ambient_bp_kind,
    classify_live,
    classify_spawn,
    ego_cell,
    exam_window_end_m,
    in_exam_tube,
    in_see_cone,
    live_stock_cap,
    prune_seen5,
    seen5_count,
    should_cull_live,
    slot_caps_for_target,
    spawn_band_ok,
    traffic_number,
)
from _tsr_static_truth import hud_light_label  # noqa: E402


def test_ambient_bp_kind_mix() -> None:
    assert ambient_bp_kind("vehicle.tesla.model3") == "car"
    assert ambient_bp_kind("vehicle.carlamotors.carlacola") == "truck"
    assert ambient_bp_kind("vehicle.tesla.cybertruck") == "truck"
    assert ambient_bp_kind("vehicle.harley-davidson.low_rider") == "motorcycle"
    assert ambient_bp_kind("vehicle.kawasaki.ninja") == "motorcycle"
    assert ambient_bp_kind("vehicle.yamaha.yzf") == "motorcycle"
    assert ambient_bp_kind("vehicle.bh.crossbike") == "bicycle"
    assert ambient_bp_kind("vehicle.diamondback.century") == "bicycle"


def _tf(x: float, y: float, yaw: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(
        location=SimpleNamespace(x=x, y=y, z=0.0),
        rotation=SimpleNamespace(yaw=yaw),
    )


def test_classify_spawn_host_tube_vs_left_overtake() -> None:
    ego = _tf(0.0, 0.0, 0.0)
    assert classify_spawn(ego, _tf(40.0, 0.0, 0.0)) == "host"
    assert classify_spawn(ego, _tf(50.0, 3.5, 0.0)) == "left_ahead"
    assert classify_spawn(ego, _tf(-40.0, 3.5, 0.0)) == "left_behind"
    assert classify_spawn(ego, _tf(50.0, -3.5, 0.0)) == "right_ahead"
    assert classify_spawn(ego, _tf(80.0, 0.0, 180.0)) == "oncoming"
    assert classify_spawn(ego, _tf(80.0, 22.0, 0.0)) == "oncoming"


def test_exam_window_and_tube() -> None:
    assert exam_window_end_m(None) == 70.0
    assert exam_window_end_m(32.0) == 70.0
    assert exam_window_end_m(60.0) == 85.0
    assert in_exam_tube(40.0, 0.0, 70.0)
    assert not in_exam_tube(85.0, 0.0, 70.0)
    assert not in_exam_tube(40.0, 3.5, 70.0)


def test_classify_live_bubble_and_crossing() -> None:
    ego = _tf(0.0, 0.0, 0.0)
    assert classify_live(ego, _tf(40.0, 0.0, 0.0), exam_end_m=70.0) == "host"
    assert classify_live(ego, _tf(85.0, 0.0, 0.0), exam_end_m=70.0) == "host_far"
    assert classify_live(ego, _tf(130.0, 0.0, 0.0), exam_end_m=70.0) == "far"
    assert classify_live(ego, _tf(40.0, 12.0, 90.0), exam_end_m=70.0) == "crossing"
    assert classify_live(ego, _tf(-40.0, 3.5, 0.0), exam_end_m=70.0) == "left_behind"
    assert classify_live(ego, _tf(50.0, -3.5, 0.0), exam_end_m=70.0) == "right_ahead"


def test_spawn_band_no_windshield_pop() -> None:
    assert not spawn_band_ok("right_ahead", 10.0)
    assert spawn_band_ok("right_ahead", 40.0)
    assert spawn_band_ok("left_behind", -30.0)
    assert not spawn_band_ok("left_behind", -8.0)
    assert spawn_band_ok("crossing", 45.0)
    assert spawn_band_ok("host_far", 80.0, exam_end_m=70.0)
    assert not spawn_band_ok("host_far", 40.0, exam_end_m=70.0)


def test_slot_caps_sum_to_target() -> None:
    for n in (8, 18, 32):
        caps = slot_caps_for_target(n)
        assert sum(caps.values()) == n
        assert caps["right_ahead"] >= 1
        assert caps["left_behind"] >= 1
    assert slot_caps_for_target(0)["right_ahead"] == 0


def test_allow_ambient_peds_skips_aeb_vru() -> None:
    assert allow_ambient_peds("acc_follow")
    assert not allow_ambient_peds("aeb_pedestrian")
    assert not allow_ambient_peds("aeb_bicycle")
    assert not allow_ambient_peds("acc_follow", {"layout": "aeb_pedestrian"})
    assert not allow_ambient_peds("keep", {"vru_kind": "walker"})
    assert allow_ambient_peds("aeb_pedestrian", keep_ego=True)


def test_see_cone_and_soft_cull() -> None:
    assert in_see_cone(40.0, 3.5)
    assert in_see_cone(40.0, -8.0)
    assert not in_see_cone(5.0, 0.0)
    assert not in_see_cone(40.0, 20.0)
    assert should_cull_live("host", 0.3)
    assert should_cull_live("far", 0.3)
    assert should_cull_live("crossing", -2.0)
    assert not should_cull_live("crossing", 0.3)
    assert not should_cull_live("right_ahead", 0.3)


def test_ambient_bp_skips_bus() -> None:
    assert ambient_bp_allowed("vehicle.tesla.model3")
    assert ambient_bp_allowed("vehicle.carlamotors.carlacola")
    assert not ambient_bp_allowed("vehicle.ford.ambulance")
    assert not ambient_bp_allowed("vehicle.carlamotors.firetruck")
    assert not ambient_bp_allowed("vehicle.volkswagen.bus")


def test_traffic_number_and_live_cap(monkeypatch) -> None:
    monkeypatch.delenv("GF_TRAFFIC_NUMBER", raising=False)
    assert traffic_number() == 18
    assert live_stock_cap(18) == 9
    assert live_stock_cap(0) == 0
    monkeypatch.setenv("GF_TRAFFIC_NUMBER", "0")
    assert traffic_number() == 0
    monkeypatch.setenv("GF_TRAFFIC_NUMBER", "12")
    assert traffic_number() == 12
    assert live_stock_cap(12) == 6


def test_keep_ego_flood_is_ring_not_full_scan() -> None:
    """keep_ego must not walk hundreds of hops or scan a junction table."""
    import inspect
    from _traffic import _flood_ring, _xing_candidates, flood_candidates

    src = inspect.getsource(flood_candidates)
    assert "ring_only=light" in src
    assert "if not light" in src
    ring = inspect.getsource(_flood_ring)
    assert "_FLOOD_RING_N" in ring
    xing = inspect.getsource(_xing_candidates)
    assert "_XING_PAIR_CAP" in xing


def test_ego_cell_and_seen5() -> None:
    assert ego_cell(0.0, 0.0) == (0, 0)
    assert ego_cell(19.9, -0.1) == (0, -1)
    assert ego_cell(20.0, 41.0) == (1, 2)
    events = [(1.0, 10), (2.0, 11), (4.0, 10), (7.0, 12)]
    assert seen5_count(events, 6.5) == 3
    pruned = prune_seen5(7.0, events)
    assert [aid for _, aid in pruned] == [11, 10, 12]


def test_hud_light_label() -> None:
    assert hud_light_label("Red") == "RED"
    assert hud_light_label("Yellow") == "YEL"
    assert hud_light_label("Green") == "GRN"
    assert hud_light_label("Off") is None
    assert hud_light_label(SimpleNamespace(name="Red")) == "RED"


def test_topup_budget_stops_when_near_full() -> None:
    from _traffic import _topup_budget

    # near already at live stock → no add even if seen5 starved
    assert (
        _topup_budget(seen5=0, number=18, near_n=9, live=9, evicted=2) == 0
    )
    # room + starved seen5 → up to 2
    assert (
        _topup_budget(seen5=0, number=18, near_n=5, live=9, evicted=0) == 2
    )
    # seen5 ok → only replace evicted
    assert (
        _topup_budget(seen5=18, number=18, near_n=5, live=9, evicted=1) == 1
    )
