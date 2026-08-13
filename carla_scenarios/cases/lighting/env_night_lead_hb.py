#!/usr/bin/env python3
"""Night — lead vehicle high beam"""

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
from layouts.lighting import layout_night_lead_hb, tick_light_handoff  # noqa: E402
from judges.controlled import judge_env  # noqa: E402

CASE = AtomCase(
    tag="env_night_lead_hb",
    layout=layout_night_lead_hb,
    judge=lambda samples, seen, meta: judge_env(samples, seen_control=seen),
    weather_preset="night",
    early_exit_on_collision=False,
    on_tick=tick_light_handoff,
    title="AFC env_night_lead_hb",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
