"""Unit tests for SurroundWorld / ModeHint POD pack (no CARLA)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
sys.path.insert(0, str(_LIB))

from _surround_pack import (  # noqa: E402
    GF_CH_MODE_HINT_MAGIC,
    GF_CH_SURROUND_MAGIC,
    _HINT,
    _SW_SIZE,
    pack_mode_hint_pod,
    pack_surround_world_pod,
)


def test_pack_surround_world_size_and_magic() -> None:
    blob = pack_surround_world_pod(
        objects=[
            {
                "object_id": 7,
                "object_class": 1,
                "long_dist_m": -8.0,
                "lat_dist_m": -3.5,
                "rel_vel_long_mps": 0.1,
            }
        ],
        slots=[
            {
                "slot_id": 1,
                "free": 1,
                "center_x_m": 6.0,
                "center_y_m": -3.2,
                "yaw_rad": 0.0,
                "length_m": 5.0,
                "width_m": 2.4,
            }
        ],
        seq=3,
        timestamp_ns=99,
    )
    assert len(blob) == _SW_SIZE
    magic, ver, _res, ts, seq, valid, n_obj, n_slot, _pad = struct.unpack_from(
        "<IHHQQBBBB", blob, 0
    )
    assert magic == GF_CH_SURROUND_MAGIC
    assert ver == 1
    assert ts == 99
    assert seq == 3
    assert valid == 1
    assert n_obj == 1
    assert n_slot == 1
    oid, ocls, long_m, lat_m, rel = struct.unpack_from("<BB2x3f", blob, 28)
    assert oid == 7 and ocls == 1
    assert abs(long_m + 8.0) < 1e-5
    assert abs(lat_m + 3.5) < 1e-5


def test_pack_mode_hint() -> None:
    blob = pack_mode_hint_pod(apa_armed=1, slot_confirmed=1, seq=2, timestamp_ns=5)
    assert len(blob) == _HINT.size
    magic, ver, apa, conf, ts, seq = _HINT.unpack(blob)
    assert magic == GF_CH_MODE_HINT_MAGIC
    assert ver == 1 and apa == 1 and conf == 1
    assert ts == 5 and seq == 2
