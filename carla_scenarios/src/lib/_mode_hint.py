"""Host ModeHint: APA arm / slot confirm via POSIX shared memory (no runtime files).

Board path remains GfChannel (`gf.channel.mode_hint`). This module only bridges
Carla case processes ↔ giraffe_client on the host.
"""

from __future__ import annotations

import os
from multiprocessing import shared_memory
from typing import Tuple

# Fixed name — no GF_*_PATH archaeology.
_SHM_NAME = "gf_mode_hint"
_SHM_SIZE = 8


def _attach(create: bool) -> shared_memory.SharedMemory | None:
    try:
        if create:
            try:
                return shared_memory.SharedMemory(name=_SHM_NAME, create=True, size=_SHM_SIZE)
            except FileExistsError:
                return shared_memory.SharedMemory(name=_SHM_NAME, create=False)
        return shared_memory.SharedMemory(name=_SHM_NAME, create=False)
    except FileNotFoundError:
        return None
    except OSError:
        return None


def write_mode_hint(*, apa_armed: int, slot_confirmed: int) -> None:
    shm = _attach(create=True)
    if shm is None:
        return
    try:
        shm.buf[0] = 1 if apa_armed else 0
        shm.buf[1] = 1 if slot_confirmed else 0
        for i in range(2, _SHM_SIZE):
            shm.buf[i] = 0
    finally:
        shm.close()


def read_mode_hint() -> Tuple[int, int]:
    """Return (apa_armed, slot_confirmed). Env is base; shm overrides when present."""
    apa = 1 if (os.environ.get("GF_APA_ARMED") or "").strip() == "1" else 0
    confirm = 1 if (os.environ.get("GF_SLOT_CONFIRMED") or "").strip() == "1" else 0
    shm = _attach(create=False)
    if shm is None:
        return apa, confirm
    try:
        apa = 1 if shm.buf[0] else 0
        confirm = 1 if shm.buf[1] else 0
    finally:
        shm.close()
    return apa, confirm
