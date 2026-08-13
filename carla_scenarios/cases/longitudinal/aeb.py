#!/usr/bin/env python3
"""AFC AEB — scheme-1: closing layout + closing_toward_lead IC; Giraffe brakes."""

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
from layouts.closing import layout_aeb_stopped, tick_aeb_handoff  # noqa: E402
from judges.controlled import judge_aeb_like  # noqa: E402


CASE = AtomCase(
    tag="aeb",
    layout=layout_aeb_stopped,
    judge=lambda samples, seen, meta: judge_aeb_like(samples, seen_control=seen),
    weather_preset=None,
    early_exit_on_collision=True,
    on_tick=tick_aeb_handoff,
    title="AFC AEB — closing; Giraffe must brake",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
