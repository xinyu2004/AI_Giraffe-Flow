"""Pack GfRcmTruthPod (lockstep boundary_pods.h)."""

from __future__ import annotations

import struct
import time
from typing import Any, Mapping, Sequence

GF_CH_RCM_MAGIC = 0x4752434D  # 'GRCM'
GF_CH_RCM_VERSION = 1
_MAX_LANE = 8
_MAX_OBJ = 16

_HEAD = struct.Struct("<IHHQQBBBB")
assert _HEAD.size == 28

_LANE = struct.Struct("<5fBB2x")
assert _LANE.size == 24

_OBJ = struct.Struct("<BB2x5f")
assert _OBJ.size == 24

_RCM_SIZE = _HEAD.size + _MAX_LANE * _LANE.size + _MAX_OBJ * _OBJ.size
assert _RCM_SIZE == 604


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


def pack_rcm_truth_pod(
    *,
    lanes: Sequence[Mapping[str, Any]] | None = None,
    objects: Sequence[Mapping[str, Any]] | None = None,
    seq: int = 0,
    timestamp_ns: int | None = None,
    valid: int = 1,
) -> bytes:
    """Build GfRcmTruthPod — rear FOV lanes + objects for perception.rcm."""
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    lns = list(lanes or ())[:_MAX_LANE]
    objs = list(objects or ())[:_MAX_OBJ]
    n_lane = len(lns)
    n_obj = len(objs)
    buf = bytearray(_RCM_SIZE)
    _HEAD.pack_into(
        buf,
        0,
        GF_CH_RCM_MAGIC,
        GF_CH_RCM_VERSION,
        0,
        ts & 0xFFFFFFFFFFFFFFFF,
        int(seq) & 0xFFFFFFFFFFFFFFFF,
        1 if valid else 0,
        n_lane,
        n_obj,
        0,
    )
    off = _HEAD.size
    for i in range(_MAX_LANE):
        if i < n_lane:
            ln = lns[i]
            _LANE.pack_into(
                buf,
                off,
                _f(ln.get("c0_m", ln.get("c0"))),
                _f(ln.get("c1_rad", ln.get("c1"))),
                _f(ln.get("c2")),
                _f(ln.get("c3")),
                _f(ln.get("view_range_m"), 35.0),
                _u8(ln.get("quality"), 2),
                _u8(ln.get("side"), i if i < 2 else i),
            )
        off += _LANE.size
    for i in range(_MAX_OBJ):
        if i < n_obj:
            o = objs[i]
            _OBJ.pack_into(
                buf,
                off,
                _u8(o.get("object_id", o.get("id")), i + 1) or (i + 1),
                _u8(o.get("object_class", o.get("class")), 1) or 1,
                _f(o.get("long_dist_m", o.get("long_m"))),
                _f(o.get("lat_dist_m", o.get("lat_m"))),
                _f(o.get("rel_vel_long_mps", o.get("rel_v"))),
                _f(o.get("rel_vel_lat_mps", o.get("rel_v_lat"))),
                _f(o.get("abs_vel_mps", o.get("abs_v"))),
            )
        off += _OBJ.size
    return bytes(buf)
