"""Unit tests for fake_perc POD pack (no CARLA)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
sys.path.insert(0, str(_LIB))

from _fake_perc_pack import _FP_HEAD, _FP_SIZE, _OBJ, pack_fake_perc_pod  # noqa: E402


def test_pack_size_and_magic() -> None:
    lane = {
        "lane_count": 3,
        "ego_lane_index_from_left": 1,
        "lane_width_m": 3.6,
        "host_left_c0": 1.8,
        "host_right_c0": -1.8,
        "host_c1": 0.01,
        "host_c2": 0.0,
        "host_left_c1": 0.01,
        "host_right_c1": 0.01,
        "host_left_c2": 0.0,
        "host_right_c2": 0.0,
        "host_left_type": 1,
        "host_right_type": 2,
        "adj_n": 2,
        "adj0_side": 1,
        "adj0_c0": 5.2,
        "adj0_c1": 0.0,
        "adj0_c2": 0.0,
        "adj0_type": 2,
        "adj1_side": 4,
        "adj1_c0": -5.1,
        "adj1_c1": 0.0,
        "adj1_c2": 0.0,
        "adj1_type": 2,
        "lane_avail": 2,
        "lane_conf": 0.9,
        "lane_vr_end_m": 80.0,
    }
    dyn = {
        "dyn_n": 2,
        "vd_count": 2,
        "ped_count": 0,
        "cipv_id": 1,
        "lead_from_dyn_long": 28.0,
        "lead_from_dyn_lat": 0.2,
        "lead_from_dyn_rel_v": -1.0,
        "lead_from_dyn_heading": 0.0,
        "lead_from_dyn_assign": 3,
        "obj0_id": 1,
        "obj0_class": 1,
        "obj0_long": 28.0,
        "obj0_lat": 0.2,
        "obj0_heading": 0.0,
        "obj0_len": 4.5,
        "obj0_wid": 1.8,
        "obj0_rel_v": -1.0,
        "obj0_assign": 3,
        "obj0_ped": 0,
        "obj1_id": 2,
        "obj1_class": 1,
        "obj1_long": 40.0,
        "obj1_lat": -3.5,
        "obj1_heading": 0.0,
        "obj1_len": 4.5,
        "obj1_wid": 1.8,
        "obj1_rel_v": 0.0,
        "obj1_assign": 4,
        "obj1_ped": 0,
    }
    blob = pack_fake_perc_pod(lane=lane, dyn=dyn, seq=7, timestamp_ns=123)
    assert len(blob) == _FP_SIZE
    magic, ver, _res, ts, seq = struct.unpack_from("<IHHQQ", blob, 0)
    assert magic == 0x47465043
    assert ver == 2
    assert ts == 123
    assert seq == 7
    # lane_count @ offset after header QQ + start of BBBB valid,lead,lane,ego
    # offset: 4+2+2+8+8 = 24 → BBBB
    valid, lead_v, lane_n, ego_i = struct.unpack_from("<BBBB", blob, 24)
    assert valid == 1 and lead_v == 1 and lane_n == 3 and ego_i == 1
    # adj_n sits after 8 host floats block — unpack head and check adj_n field via full head
    fields = _FP_HEAD.unpack_from(blob)
    # indices: see pack order — adj_n after 8 floats following fff width/conf/vr
    # 0 magic 1 ver 2 res 3 ts 4 seq 5 valid 6 lead 7 lane 8 ego
    # 9-12 lead floats 13-16 types/avail 17-19 width/conf/vr 20-27 host 28 adj_n
    assert fields[28] == 2
    assert fields[29] == 2  # dyn_n
    obj0 = _OBJ.unpack_from(blob, _FP_HEAD.size)
    assert obj0[0] == 1 and abs(obj0[4] - 28.0) < 1e-3


def test_pack_empty_lane() -> None:
    blob = pack_fake_perc_pod(lane={"lane_count": 0, "adj_n": 0}, dyn={"dyn_n": 0})
    assert len(blob) == _FP_SIZE
    fields = _FP_HEAD.unpack_from(blob)
    assert fields[5] == 1  # valid
    assert fields[7] == 0  # lane_count
    assert fields[28] == 0  # adj_n


def test_pack_tsr_static_tail() -> None:
    from _fake_perc_pack import _FP_V1_SIZE, _STAT, _TAIL_HEAD, _TSR

    tsr = {
        "tsr_n": 1,
        "tsr0_name": 196,
        "tsr0_long": 32.0,
        "tsr0_lat": 1.2,
        "tsr0_rel": 0,
        "stat_n": 1,
        "stat0_id": 7,
        "stat0_cls": 1,
        "stat0_assign": 3,
        "stat0_long": 18.0,
        "stat0_lat": 0.1,
        "stat0_heading": 0.0,
        "stat0_len": 2.0,
        "stat0_wid": 0.5,
    }
    blob = pack_fake_perc_pod(lane={"lane_count": 1, "adj_n": 0}, dyn={"dyn_n": 0}, tsr=tsr)
    assert len(blob) == _FP_SIZE
    tsr_n, stat_n = _TAIL_HEAD.unpack_from(blob, _FP_V1_SIZE)
    assert tsr_n == 1 and stat_n == 1
    name, _rel, lon, _lat = _TSR.unpack_from(blob, _FP_V1_SIZE + _TAIL_HEAD.size)
    assert name == 196 and abs(lon - 32.0) < 1e-3
    sid, _cls, _assign, _p, slon, _slat, _h, _ln, _wd = _STAT.unpack_from(
        blob, _FP_V1_SIZE + _TAIL_HEAD.size + 6 * _TSR.size
    )
    assert sid == 7 and abs(slon - 18.0) < 1e-3
