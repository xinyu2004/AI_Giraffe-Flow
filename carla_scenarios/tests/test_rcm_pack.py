"""Pack roundtrip for GfRcmTruthPod."""

from __future__ import annotations

from _rcm_pack import (
    GF_CH_RCM_MAGIC,
    _HEAD,
    _LANE,
    _OBJ,
    _RCM_SIZE,
    pack_rcm_truth_pod,
)
from _rcm_truth import optic_in_rear_wedge


def test_pack_rcm_size_and_magic() -> None:
    blob = pack_rcm_truth_pod(
        lanes=[
            {"c0_m": 1.7, "c1_rad": 0.01, "c2": 0.0, "c3": 0.0, "view_range_m": 35.0, "quality": 2, "side": 0},
            {"c0_m": -1.7, "c1_rad": 0.01, "c2": 0.0, "side": 1},
        ],
        objects=[
            {
                "object_id": 7,
                "object_class": 1,
                "long_dist_m": -12.0,
                "lat_dist_m": 0.5,
                "rel_vel_long_mps": -2.0,
                "rel_vel_lat_mps": 0.1,
                "abs_vel_mps": 10.0,
            }
        ],
        seq=3,
        timestamp_ns=99,
    )
    assert len(blob) == _RCM_SIZE
    magic, ver, _res, ts, seq, valid, n_lane, n_obj, _pad = _HEAD.unpack_from(blob, 0)
    assert magic == GF_CH_RCM_MAGIC
    assert ver == 1
    assert ts == 99
    assert seq == 3
    assert valid == 1
    assert n_lane == 2
    assert n_obj == 1
    c0, c1, c2, c3, vr, q, side = _LANE.unpack_from(blob, _HEAD.size)
    assert abs(c0 - 1.7) < 1e-5
    assert side == 0
    oid, cls, long_m, lat_m, rv_l, rv_lat, abs_v = _OBJ.unpack_from(
        blob, _HEAD.size + 8 * _LANE.size
    )
    assert oid == 7
    assert abs(long_m + 12.0) < 1e-5
    assert abs(abs_v - 10.0) < 1e-5


def test_optic_rear_wedge() -> None:
    assert optic_in_rear_wedge(-10.0, 0.0)
    assert not optic_in_rear_wedge(10.0, 0.0)
    assert not optic_in_rear_wedge(-40.0, 0.0)
    # 60° from rear axis at 10 m — outside 120° FOV half=60 → edge ok
    assert optic_in_rear_wedge(-5.0, 5.0 * 0.99)
    assert not optic_in_rear_wedge(-5.0, 20.0)
