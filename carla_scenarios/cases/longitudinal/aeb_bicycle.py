#!/usr/bin/env python3
"""AEB — bicycle cross or slow same-direction"""

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
from layouts.vru import layout_aeb_bicycle, tick_vru_handoff  # noqa: E402
from judges.controlled import judge_aeb_like  # noqa: E402

CASE = AtomCase(
    tag="aeb_bicycle",
    layout=layout_aeb_bicycle,
    judge=lambda samples, seen, meta: judge_aeb_like(samples, seen_control=seen),
    weather_preset=None,
    early_exit_on_collision=True,
    on_tick=tick_vru_handoff,
    title="AFC aeb_bicycle",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
