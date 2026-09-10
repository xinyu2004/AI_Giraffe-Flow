"""Pack GfSurroundWorldPod / GfModeHintPod (lockstep boundary_pods.h)."""

from __future__ import annotations

import struct
import time
from typing import Any, Mapping, Sequence

GF_CH_SURROUND_MAGIC = 0x47535744
GF_CH_MODE_HINT_MAGIC = 0x474D4854
GF_CH_SURROUND_VERSION = 1
GF_CH_MODE_HINT_VERSION = 1
_MAX_OBJ = 16
_MAX_SLOT = 8

_HEAD = struct.Struct("<IHHQQBBBB")
assert _HEAD.size == 28

_OBJ = struct.Struct("<BB2x3f")
assert _OBJ.size == 16

_SLOT = struct.Struct("<BB2x5f")
assert _SLOT.size == 24

_SW_SIZE = _HEAD.size + _MAX_OBJ * _OBJ.size + _MAX_SLOT * _SLOT.size
assert _SW_SIZE == 476

_HINT = struct.Struct("<IHBBQQ")
assert _HINT.size == 24


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


def pack_surround_world_pod(
    *,
    objects: Sequence[Mapping[str, Any]] | None = None,
    slots: Sequence[Mapping[str, Any]] | None = None,
    seq: int = 0,
    timestamp_ns: int | None = None,
    valid: int = 1,
) -> bytes:
    """Build GfSurroundWorldPod blob (ego-frame side/rear objects + parking slots)."""
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    objs = list(objects or ())[:_MAX_OBJ]
    sls = list(slots or ())[:_MAX_SLOT]
    n_obj = len(objs)
    n_slot = len(sls)
    buf = bytearray(_SW_SIZE)
    _HEAD.pack_into(
        buf,
        0,
        GF_CH_SURROUND_MAGIC,
        GF_CH_SURROUND_VERSION,
        0,
        ts & 0xFFFFFFFFFFFFFFFF,
        int(seq) & 0xFFFFFFFFFFFFFFFF,
        1 if valid else 0,
        n_obj,
        n_slot,
        0,  # pad0
    )
    off = _HEAD.size
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
            )
        off += _OBJ.size
    for i in range(_MAX_SLOT):
        if i < n_slot:
            s = sls[i]
            _SLOT.pack_into(
                buf,
                off,
                _u8(s.get("slot_id", s.get("id")), i + 1) or (i + 1),
                1 if int(s.get("free", 1)) else 0,
                _f(s.get("center_x_m"), 6.0),
                _f(s.get("center_y_m"), -3.2),
                _f(s.get("yaw_rad")),
                _f(s.get("length_m"), 5.0),
                _f(s.get("width_m"), 2.4),
            )
        off += _SLOT.size
    return bytes(buf)


def pack_mode_hint_pod(
    *,
    apa_armed: int = 0,
    slot_confirmed: int = 0,
    seq: int = 0,
    timestamp_ns: int | None = None,
) -> bytes:
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    return _HINT.pack(
        GF_CH_MODE_HINT_MAGIC,
        GF_CH_MODE_HINT_VERSION,
        1 if apa_armed else 0,
        1 if slot_confirmed else 0,
        ts & 0xFFFFFFFFFFFFFFFF,
        int(seq) & 0xFFFFFFFFFFFFFFFF,
    )
