"""Unit tests for octave_bridge semantic + protocol (no CARLA)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / "src" / "lib"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_LIB))

from _fake_perc_pack import pack_fake_perc_pod  # noqa: E402
from octave_bridge.plan_ref import plan_tick_ref  # noqa: E402
from octave_bridge.protocol import (  # noqa: E402
    pack_cmd,
    unpack_fake_perc,
    unpack_vehicle_state,
    VS,
    GF_CH_VEHICLE_STATE_MAGIC,
    GF_CH_POD_VERSION,
)
from octave_bridge.semantic_map import (  # noqa: E402
    build_view,
    result_to_cmd_blob,
    view_to_bev_out_dict,
)


def test_unpack_fake_perc_roundtrip() -> None:
    lane = {
        "lane_count": 3,
        "ego_lane_index_from_left": 1,
        "lane_avail": 2,
        "lane_conf": 0.9,
        "lane_vr_end_m": 80.0,
        "lane_width_m": 3.5,
        "host_left_c0": 1.8,
        "host_right_c0": -1.7,
        "host_c1": 0.01,
        "host_c2": 0.0,
        "host_left_c1": 0.01,
        "host_right_c1": 0.01,
        "host_left_c2": 0.0,
        "host_right_c2": 0.0,
        "host_left_type": 1,
        "host_right_type": 1,
        "adj_n": 1,
        "adj0_side": 1,
        "adj0_c0": 5.2,
        "adj0_c1": 0.0,
        "adj0_c2": 0.0,
        "adj0_type": 2,
    }
    dyn = {
        "dyn_n": 1,
        "vd_count": 1,
        "ped_count": 0,
        "cipv_id": 7,
        "obj0_id": 7,
        "obj0_cls": 1,
        "obj0_assign": 3,
        "obj0_is_ped": 0,
        "obj0_long": 25.0,
        "obj0_lat": 0.2,
        "obj0_heading": 0.0,
        "obj0_len": 4.5,
        "obj0_wid": 1.8,
        "obj0_rel_v": -2.0,
        "lead_from_dyn_long": 25.0,
        "lead_from_dyn_lat": 0.2,
        "lead_from_dyn_rel_v": -2.0,
        "lead_from_dyn_heading": 0.0,
        "lead_from_dyn_assign": 3,
    }
    blob = pack_fake_perc_pod(lane=lane, dyn=dyn, seq=3, timestamp_ns=123)
    fp = unpack_fake_perc(blob)
    assert fp is not None
    assert fp["seq"] == 3
    assert fp["lane_avail"] == 2
    assert fp["host_left_c0"] == pytest.approx(1.8)
    assert fp["dyn_n"] == 1
    assert fp["obj"][0]["id"] == 7
    assert fp["obj"][0]["long_m"] == pytest.approx(25.0)
    assert fp["adj_n"] == 1
    assert fp["adj_c0"][0] == pytest.approx(5.2)


def test_build_view_and_plan() -> None:
    import struct
    import time

    vs = struct.pack(
        VS.format,
        GF_CH_VEHICLE_STATE_MAGIC,
        GF_CH_POD_VERSION,
        0,
        time.time_ns(),
        10.0,
        0.0,
        0.0,
        4,
    )
    state = unpack_vehicle_state(vs)
    assert state is not None

    lane = {
        "lane_count": 1,
        "lane_avail": 2,
        "lane_conf": 0.95,
        "lane_vr_end_m": 60.0,
        "lane_width_m": 3.5,
        "host_left_c0": 1.75,
        "host_right_c0": -1.75,
        "host_c1": 0.0,
        "host_c2": 0.0,
        "host_left_type": 1,
        "host_right_type": 1,
        "adj_n": 0,
    }
    dyn = {
        "dyn_n": 0,
        "vd_count": 0,
        "ped_count": 0,
        "cipv_id": 0,
        "lead_from_dyn_long": 0.0,
    }
    fp = unpack_fake_perc(pack_fake_perc_pod(lane=lane, dyn=dyn, seq=1))
    view = build_view(state=state, fake_perc=fp)
    assert view.perc.lane_valid
    assert abs(view.perc.e_y) < 0.05
    result = plan_tick_ref(view, seq=1)
    assert result.ctrl_mode == "cruise"
    assert result.throttle > 0.0
    assert len(result.points_x_m) == 16
    blob = result_to_cmd_blob(result, speed_mps=10.0, seq=1)
    assert len(blob) == 48

    out = view_to_bev_out_dict(view)
    assert out["Perception_LH_Out"]["m_hostline_num"] == 2


def test_bev_feed_imports() -> None:
    from octave_bridge.bev_feed import BevFeed

    feed = BevFeed()
    assert feed is not None
