#!/usr/bin/env python3
"""Lane departure warning — slow drift"""

from __future__ import annotations

import sys
from pathlib import Path

_AFC = Path(__file__).resolve().parents[2]
_SRC = _AFC / "src"
_LIB = _SRC / "lib"
for _p in (_AFC, _SRC, _LIB, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _case_atom import AtomCase, bind_run_session  # noqa: E402
from layouts.lateral import layout_ldw_drift, tick_lateral_handoff  # noqa: E402
from judges.controlled import judge_lateral  # noqa: E402

CASE = AtomCase(
    tag="ldw_drift",
    layout=layout_ldw_drift,
    judge=lambda samples, seen, meta: judge_lateral(samples, seen_control=seen),
    weather_preset="clear",
    early_exit_on_collision=False,
    on_tick=tick_lateral_handoff,
    title="AFC ldw_drift",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
