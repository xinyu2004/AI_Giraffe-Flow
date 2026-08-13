"""Put carla_scenarios root + src + src/lib on sys.path."""

from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent  # .../src/lib
_SRC = _LIB.parent  # .../src
_ROOT = _SRC.parent  # .../carla_scenarios


def ensure_afc_path() -> Path:
    for p in (_ROOT, _SRC, _LIB):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    return _ROOT


def afc_root() -> Path:
    return _ROOT


def src_root() -> Path:
    return _SRC
