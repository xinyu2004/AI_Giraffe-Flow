#!/usr/bin/env python3
"""Forward collision warning window"""

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
from layouts.closing import layout_fcw, tick_aeb_handoff  # noqa: E402
from judges.controlled import judge_fcw  # noqa: E402

CASE = AtomCase(
    tag="fcw",
    layout=layout_fcw,
    judge=lambda samples, seen, meta: judge_fcw(samples, seen_control=seen),
    weather_preset=None,
    early_exit_on_collision=True,
    on_tick=tick_aeb_handoff,
    title="AFC fcw",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
