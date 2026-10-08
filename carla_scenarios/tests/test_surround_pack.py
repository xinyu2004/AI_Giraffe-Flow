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
    GF_CH_SURROUND_VERSION,
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
                "length_m": 4.6,
                "width_m": 1.9,
                "heading_rad": 0.35,
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
    assert _SW_SIZE == 668
    magic, ver, _res, ts, seq, valid, n_obj, n_slot, _pad = struct.unpack_from(
        "<IHHQQBBBB", blob, 0
    )
    assert magic == GF_CH_SURROUND_MAGIC
    assert ver == GF_CH_SURROUND_VERSION == 2
    assert ts == 99
    assert seq == 3
    assert valid == 1
    assert n_obj == 1
    assert n_slot == 1
    oid, ocls, long_m, lat_m, rel, length_m, width_m, hdg = struct.unpack_from(
        "<BB2x6f", blob, 28
    )
    assert oid == 7 and ocls == 1
    assert abs(long_m + 8.0) < 1e-5
    assert abs(lat_m + 3.5) < 1e-5
    assert abs(length_m - 4.6) < 1e-5
    assert abs(width_m - 1.9) < 1e-5
    assert abs(hdg - 0.35) < 1e-5


def test_pack_mode_hint() -> None:
    blob = pack_mode_hint_pod(
        apa_armed=1,
        slot_confirmed=1,
        seq=2,
        timestamp_ns=5,
        fParkingSlot_P0X=1.0,
        fParkingSlot_P0Y=2.0,
        fParkingSlot_P1X=3.0,
        fParkingSlot_P1Y=4.0,
        fParkingSlot_P2X=5.0,
        fParkingSlot_P2Y=6.0,
    )
    assert len(blob) == _HINT.size
    magic, ver, apa, conf, ts, seq, *xy = _HINT.unpack(blob)
    assert magic == GF_CH_MODE_HINT_MAGIC
    assert ver == 2 and apa == 1 and conf == 1
    assert ts == 5 and seq == 2
    assert [round(float(v), 1) for v in xy] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_parking_bays_roundtrip() -> None:
    from _surround_truth import clear_parking_bays, read_parking_bays, write_parking_bays

    write_parking_bays(
        [
            {
                "id": 2,
                "free": 1,
                "center_x_m": 272.5,
                "center_y_m": -200.5,
                "yaw_rad": -1.57,
                "length_m": 5.0,
                "width_m": 2.4,
            }
        ]
    )
    got = read_parking_bays()
    clear_parking_bays()
    assert len(got) == 1
    assert int(got[0]["id"]) == 2
    assert int(got[0]["free"]) == 1
    assert abs(float(got[0]["center_x_m"]) - 272.5) < 1e-4
