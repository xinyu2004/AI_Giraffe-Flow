#!/usr/bin/env python3
"""LKA — straight into curve entry"""

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
from layouts.lateral import layout_lka_curve_entry, tick_lateral_handoff  # noqa: E402
from judges.controlled import judge_lateral  # noqa: E402

CASE = AtomCase(
    tag="lka_curve_entry",
    layout=layout_lka_curve_entry,
    judge=lambda samples, seen, meta: judge_lateral(samples, seen_control=seen),
    weather_preset="clear",
    early_exit_on_collision=False,
    on_tick=tick_lateral_handoff,
    title="AFC lka_curve_entry",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
