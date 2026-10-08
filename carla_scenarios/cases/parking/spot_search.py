#!/usr/bin/env python3
"""SpotSearch — Town04 lot; arm APA only (no P*, no confirm)."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_LIB = _SRC / "lib"
for _p in (_ROOT, _SRC, _LIB, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("GF_CHASE_CAM", "3")

from _case_atom import AtomCase, bind_run_session  # noqa: E402
from _mode_hint import write_mode_hint  # noqa: E402
from layouts.parking_lot import layout_parking_lot  # noqa: E402

_SPOT_MAX_MPS = 15.0 / 3.6


def _on_tick(elapsed, ego, target, meta, cmd):
    del target, cmd
    try:
        vel = ego.get_velocity()
        v = math.sqrt(vel.x**2 + vel.y**2 + vel.z**2)
    except Exception:  # noqa: BLE001
        v = 0.0
    write_mode_hint(apa_armed=1 if v < _SPOT_MAX_MPS else 0, slot_confirmed=0)
    meta["apa_armed"] = 1 if v < _SPOT_MAX_MPS else 0
    if elapsed < 0.2:
        print(f"[spot_search] ModeHint arm v={v:.2f}", flush=True)


def _judge(samples, seen, meta):
    del samples, seen
    if int(meta.get("apa_armed") or 0) != 1:
        return False, "apa_not_armed", {"note": "spot_search must arm only"}
    return True, "ok", {"note": "spot_search armed; no P* / no confirm"}


CASE = AtomCase(
    tag="spot_search",
    layout=layout_parking_lot,
    judge=_judge,
    weather_preset=None,
    early_exit_on_collision=False,
    on_tick=_on_tick,
    title="Parking SpotSearch (Town04 lot, arm only)",
    default_duration_s=12.0,
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
