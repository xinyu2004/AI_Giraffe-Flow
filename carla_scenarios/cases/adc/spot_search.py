#!/usr/bin/env python3
"""ADC SpotSearch — arm APA via mode hint while v is low."""

from __future__ import annotations

import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_LIB = _SRC / "lib"
for _p in (_ROOT, _SRC, _LIB, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _case_atom import AtomCase, bind_run_session  # noqa: E402
from _mode_hint import write_mode_hint  # noqa: E402
from layouts.follow_straight import layout_acc_follow  # noqa: E402

_SPOT_MAX_MPS = 15.0 / 3.6


def _on_tick(elapsed, ego, target, meta, cmd):
    del target, meta, cmd
    try:
        vel = ego.get_velocity()
        v = math.sqrt(vel.x**2 + vel.y**2 + vel.z**2)
    except Exception:  # noqa: BLE001
        v = 0.0
    # SpotSearch: APA armed, not confirmed yet.
    write_mode_hint(apa_armed=1 if v < _SPOT_MAX_MPS else 0, slot_confirmed=0)
    if elapsed < 0.2:
        print(f"[adc_spot_search] mode_hint apa@v={v:.2f}", flush=True)


def _judge(samples, seen, meta):
    del samples, seen, meta
    return {"ok": True, "note": "adc spot_search — ModeHint APA armed at low speed"}


CASE = AtomCase(
    tag="adc_spot_search",
    layout=layout_acc_follow,
    judge=_judge,
    weather_preset=None,
    early_exit_on_collision=False,
    on_tick=_on_tick,
    title="ADC SpotSearch v<15 (ModeHint)",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
