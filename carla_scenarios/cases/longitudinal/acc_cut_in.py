#!/usr/bin/env python3
"""ACC cut-in from adjacent lane"""

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
from layouts.cut_in import layout_acc_cut_in, tick_cut_in_handoff  # noqa: E402
from judges.acc_headway import judge_acc  # noqa: E402

CASE = AtomCase(
    tag="acc_cut_in",
    layout=layout_acc_cut_in,
    judge=lambda samples, seen, meta: judge_acc(samples, seen_control=seen),
    weather_preset=None,
    early_exit_on_collision=False,
    on_tick=tick_cut_in_handoff,
    title="AFC acc_cut_in",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
