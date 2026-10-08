"""Host ModeHint: APA arm / confirm / gold P0..P2 via POSIX shm.

Board path remains GfChannel (`gf.channel.mode_hint`). This module only bridges
Carla case processes ↔ giraffe_client on the host.
"""

from __future__ import annotations

import os
import struct
from multiprocessing import shared_memory
from typing import Tuple

_SHM_NAME = "gf_mode_hint"
_SHM_SIZE = 32
_PACK = struct.Struct("<BB6x6f")
assert _PACK.size == _SHM_SIZE


def _attach(create: bool) -> shared_memory.SharedMemory | None:
    try:
        if create:
            try:
                return shared_memory.SharedMemory(name=_SHM_NAME, create=True, size=_SHM_SIZE)
            except FileExistsError:
                existing = shared_memory.SharedMemory(name=_SHM_NAME, create=False)
                if existing.size < _SHM_SIZE:
                    existing.close()
                    existing.unlink()
                    return shared_memory.SharedMemory(
                        name=_SHM_NAME, create=True, size=_SHM_SIZE
                    )
                return existing
        return shared_memory.SharedMemory(name=_SHM_NAME, create=False)
    except FileNotFoundError:
        return None
    except OSError:
        return None


def write_mode_hint(
    *,
    apa_armed: int,
    slot_confirmed: int,
    fParkingSlot_P0X: float = 0.0,
    fParkingSlot_P0Y: float = 0.0,
    fParkingSlot_P1X: float = 0.0,
    fParkingSlot_P1Y: float = 0.0,
    fParkingSlot_P2X: float = 0.0,
    fParkingSlot_P2Y: float = 0.0,
) -> None:
    shm = _attach(create=True)
    if shm is None:
        return
    try:
        shm.buf[:_SHM_SIZE] = _PACK.pack(
            1 if apa_armed else 0,
            1 if slot_confirmed else 0,
            float(fParkingSlot_P0X),
            float(fParkingSlot_P0Y),
            float(fParkingSlot_P1X),
            float(fParkingSlot_P1Y),
            float(fParkingSlot_P2X),
            float(fParkingSlot_P2Y),
        )
    finally:
        shm.close()


def read_mode_hint() -> Tuple[int, int, dict[str, float]]:
    """Return (apa_armed, slot_confirmed, P* dict). Env is base; shm overrides."""
    apa = 1 if (os.environ.get("GF_APA_ARMED") or "").strip() == "1" else 0
    confirm = 1 if (os.environ.get("GF_SLOT_CONFIRMED") or "").strip() == "1" else 0
    corners = {
        "fParkingSlot_P0X": 0.0,
        "fParkingSlot_P0Y": 0.0,
        "fParkingSlot_P1X": 0.0,
        "fParkingSlot_P1Y": 0.0,
        "fParkingSlot_P2X": 0.0,
        "fParkingSlot_P2Y": 0.0,
    }
    shm = _attach(create=False)
    if shm is None:
        return apa, confirm, corners
    try:
        if shm.size >= _SHM_SIZE:
            apa_b, conf_b, *xy = _PACK.unpack(bytes(shm.buf[:_SHM_SIZE]))
            apa = 1 if apa_b else 0
            confirm = 1 if conf_b else 0
            keys = list(corners.keys())
            for i, k in enumerate(keys):
                corners[k] = float(xy[i])
        else:
            apa = 1 if shm.buf[0] else 0
            confirm = 1 if shm.buf[1] else 0
    finally:
        shm.close()
    return apa, confirm, corners
