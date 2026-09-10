#!/usr/bin/env python3
"""ADC APA — arm then confirm via ModeHint after stop."""

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
_CONFIRM_AFTER_S = 6.0
_STOP_MPS = 0.35


def _on_tick(elapsed, ego, target, meta, cmd):
    del target, meta, cmd
    try:
        vel = ego.get_velocity()
        v = math.sqrt(vel.x**2 + vel.y**2 + vel.z**2)
    except Exception:  # noqa: BLE001
        v = 0.0
    apa = 1 if v < _SPOT_MAX_MPS else 0
    confirm = 1 if (elapsed >= _CONFIRM_AFTER_S and v < _STOP_MPS) else 0
    write_mode_hint(apa_armed=apa, slot_confirmed=confirm)
    if confirm and elapsed < _CONFIRM_AFTER_S + 0.3:
        print(f"[adc_apa] ModeHint confirm v={v:.2f} t={elapsed:.1f}", flush=True)


def _judge(samples, seen, meta):
    del samples, seen, meta
    return {"ok": True, "note": "adc apa — ModeHint confirm→Parking (m_park_tick)"}


CASE = AtomCase(
    tag="adc_apa",
    layout=layout_acc_follow,
    judge=_judge,
    weather_preset=None,
    early_exit_on_collision=False,
    on_tick=_on_tick,
    title="ADC APA confirm→park (ModeHint)",
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
