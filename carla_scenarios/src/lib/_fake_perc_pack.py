"""Pack GfFakePercPod bytes from lane/objects truth dicts (old carla_truth fields).

Layout must stay in lockstep with boundary_pods.h GfFakePercPod (pack 1).
"""

from __future__ import annotations

import struct
import time
from typing import Any, Mapping

GF_CH_FAKE_PERC_MAGIC = 0x47465043
GF_CH_POD_VERSION = 1
GF_CH_FAKE_PERC_VERSION = 2
_MAX_OBJ = 13
_MAX_ADJ = 4
_MAX_TSR = 6
_MAX_STAT = 6

_OBJ = struct.Struct("<BBBB6f")
assert _OBJ.size == 28

_FP_HEAD = struct.Struct(
    "<"
    "IHH"
    "QQ"
    "BBBB"
    "ffff"
    "BBBB"
    "fff"
    "ffffffff"
    "BBBB"
    "B3x"
    "4B"
    "4f4f4f"
    "4B"
)
assert _FP_HEAD.size == 156
_FP_V1_SIZE = _FP_HEAD.size + _MAX_OBJ * _OBJ.size
assert _FP_V1_SIZE == 520
_TSR = struct.Struct("<HBx2f")
assert _TSR.size == 12
_STAT = struct.Struct("<BBBB5f")
assert _STAT.size == 24
_TAIL_HEAD = struct.Struct("<BB2x")
assert _TAIL_HEAD.size == 4
_FP_SIZE = _FP_V1_SIZE + _TAIL_HEAD.size + _MAX_TSR * _TSR.size + _MAX_STAT * _STAT.size
assert _FP_SIZE == 740


def _u8(v: Any, default: int = 0) -> int:
    try:
        return int(v) & 0xFF
    except (TypeError, ValueError):
        return default & 0xFF


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def pack_fake_perc_pod(
    *,
    lane: Mapping[str, Any],
    dyn: Mapping[str, Any],
    tsr: Mapping[str, Any] | None = None,
    seq: int = 0,
    timestamp_ns: int | None = None,
) -> bytes:
    """Build full fake_perc blob from lane + dyn + optional TSR/STATIC (v2)."""
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())

    lead_long = _f(dyn.get("lead_from_dyn_long"), 0.0)
    lead_lat = _f(dyn.get("lead_from_dyn_lat"), 0.0)
    lead_rel = _f(dyn.get("lead_from_dyn_rel_v"), 0.0)
    lead_hdg = _f(dyn.get("lead_from_dyn_heading"), 0.0)
    lead_assign = _u8(dyn.get("lead_from_dyn_assign"), 3)
    has_lead = 1 if lead_long > 0.5 else 0

    lane_count = _u8(lane.get("lane_count"), 0)
    ego_idx = _u8(lane.get("ego_lane_index_from_left"), 0)
    lane_avail = _u8(lane.get("lane_avail"), 0)
    lane_conf = _f(lane.get("lane_conf"), 0.0)
    lane_vr = _f(lane.get("lane_vr_end_m"), 0.0)
    width = _f(lane.get("lane_width_m"), 3.5)
    if width < 0.5:
        width = 3.5

    hl_c0 = _f(lane.get("host_left_c0"), 1.75)
    hr_c0 = _f(lane.get("host_right_c0"), -1.75)
    host_c1 = _f(lane.get("host_c1"), 0.0)
    host_c2 = _f(lane.get("host_c2"), 0.0)
    hl_c1 = _f(lane.get("host_left_c1"), host_c1)
    hr_c1 = _f(lane.get("host_right_c1"), host_c1)
    hl_c2 = _f(lane.get("host_left_c2"), host_c2)
    hr_c2 = _f(lane.get("host_right_c2"), host_c2)
    hl_type = _u8(lane.get("host_left_type"), 1) or 1
    hr_type = _u8(lane.get("host_right_type"), 1) or 1

    adj_n = min(_MAX_ADJ, max(0, _u8(lane.get("adj_n"), 0)))
    adj_side = [0] * _MAX_ADJ
    adj_c0 = [0.0] * _MAX_ADJ
    adj_c1 = [0.0] * _MAX_ADJ
    adj_c2 = [0.0] * _MAX_ADJ
    adj_type = [0] * _MAX_ADJ
    for i in range(adj_n):
        adj_side[i] = _u8(lane.get(f"adj{i}_side"), 0)
        adj_c0[i] = _f(lane.get(f"adj{i}_c0"), 0.0)
        adj_c1[i] = _f(lane.get(f"adj{i}_c1"), 0.0)
        adj_c2[i] = _f(lane.get(f"adj{i}_c2"), 0.0)
        adj_type[i] = _u8(lane.get(f"adj{i}_type"), 2) or 2

    dyn_n = min(_MAX_OBJ, max(0, _u8(dyn.get("dyn_n"), 0)))
    vd_count = _u8(dyn.get("vd_count"), 0)
    ped_count = _u8(dyn.get("ped_count"), 0)
    cipv_id = _u8(dyn.get("cipv_id"), 0)

    head = _FP_HEAD.pack(
        GF_CH_FAKE_PERC_MAGIC,
        GF_CH_FAKE_PERC_VERSION,
        0,
        ts,
        int(seq) & 0xFFFFFFFFFFFFFFFF,
        1,  # valid
        has_lead,
        lane_count,
        ego_idx,
        lead_long,
        lead_rel,
        lead_lat,
        lead_hdg,
        lead_assign,
        lane_avail,
        hl_type,
        hr_type,
        width,
        lane_conf,
        lane_vr,
        hl_c0,
        hr_c0,
        host_c1,
        host_c2,
        hl_c1,
        hr_c1,
        hl_c2,
        hr_c2,
        adj_n,
        dyn_n,
        vd_count,
        ped_count,
        cipv_id,
        adj_side[0],
        adj_side[1],
        adj_side[2],
        adj_side[3],
        adj_c0[0],
        adj_c0[1],
        adj_c0[2],
        adj_c0[3],
        adj_c1[0],
        adj_c1[1],
        adj_c1[2],
        adj_c1[3],
        adj_c2[0],
        adj_c2[1],
        adj_c2[2],
        adj_c2[3],
        adj_type[0],
        adj_type[1],
        adj_type[2],
        adj_type[3],
    )
    buf = bytearray(_FP_SIZE)
    buf[: len(head)] = head

    for i in range(dyn_n):
        p = f"obj{i}_"
        obj = _OBJ.pack(
            _u8(dyn.get(p + "id"), i + 1) or (i + 1),
            _u8(dyn.get(p + "class"), 1) or 1,
            _u8(dyn.get(p + "assign"), 3) or 3,
            _u8(dyn.get(p + "ped"), 0),
            _f(dyn.get(p + "long"), 0.0),
            _f(dyn.get(p + "lat"), 0.0),
            _f(dyn.get(p + "heading"), 0.0),
            _f(dyn.get(p + "len"), 4.5),
            _f(dyn.get(p + "wid"), 1.8),
            _f(dyn.get(p + "rel_v"), 0.0),
        )
        off = _FP_HEAD.size + i * _OBJ.size
        buf[off : off + len(obj)] = obj

    extra = tsr or {}
    tsr_n = min(_MAX_TSR, max(0, _u8(extra.get("tsr_n"), 0)))
    stat_n = min(_MAX_STAT, max(0, _u8(extra.get("stat_n"), 0)))
    tail_off = _FP_V1_SIZE
    buf[tail_off : tail_off + _TAIL_HEAD.size] = _TAIL_HEAD.pack(tsr_n, stat_n)
    tsr_off = tail_off + _TAIL_HEAD.size
    for i in range(tsr_n):
        rec = _TSR.pack(
            int(extra.get(f"tsr{i}_name") or 0) & 0xFFFF,
            _u8(extra.get(f"tsr{i}_rel"), 0),
            _f(extra.get(f"tsr{i}_long"), 0.0),
            _f(extra.get(f"tsr{i}_lat"), 0.0),
        )
        buf[tsr_off + i * _TSR.size : tsr_off + (i + 1) * _TSR.size] = rec
    stat_off = tsr_off + _MAX_TSR * _TSR.size
    for i in range(stat_n):
        rec = _STAT.pack(
            _u8(extra.get(f"stat{i}_id"), i + 1) or (i + 1),
            _u8(extra.get(f"stat{i}_cls"), 1) or 1,
            _u8(extra.get(f"stat{i}_assign"), 3) or 3,
            0,
            _f(extra.get(f"stat{i}_long"), 0.0),
            _f(extra.get(f"stat{i}_lat"), 0.0),
            _f(extra.get(f"stat{i}_heading"), 0.0),
            _f(extra.get(f"stat{i}_len"), 2.0),
            _f(extra.get(f"stat{i}_wid"), 0.6),
        )
        buf[stat_off + i * _STAT.size : stat_off + (i + 1) * _STAT.size] = rec

    return bytes(buf)
