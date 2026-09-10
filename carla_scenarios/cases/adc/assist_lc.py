#!/usr/bin/env python3
"""ADC assist LC shell — stage P; layout reuses straight follow until dedicated layout lands."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_LIB = _SRC / "lib"
for _p in (_ROOT, _SRC, _LIB, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _case_atom import AtomCase, bind_run_session  # noqa: E402
from layouts.follow_straight import layout_acc_follow  # noqa: E402


def _judge(samples, seen, meta):
    del samples, seen, meta
    return {"ok": True, "note": "adc assist_lc shell — SurroundWorld side object not judged yet"}


CASE = AtomCase(
    tag="adc_assist_lc",
    layout=layout_acc_follow,
    judge=_judge,
    weather_preset=None,
    early_exit_on_collision=False,
    on_tick=None,
    title="ADC surround-assisted LC (shell)",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
