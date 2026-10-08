#!/usr/bin/env python3
"""Assist LC scene — adjacent-lane car only. CARLA does not steer ego."""

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
from _surround_truth import collect_surround_world  # noqa: E402
from layouts.lateral import layout_assist_lc, tick_lateral_handoff  # noqa: E402


def _on_tick(elapsed, ego, target, meta, cmd):
    tick_lateral_handoff(elapsed, ego, target, meta, cmd)
    try:
        sw = collect_surround_world(ego, ego.get_world())
        side = [
            o
            for o in sw.get("objects") or []
            if abs(float(o.get("lat_dist_m") or 0.0)) > 1.2
        ]
        meta["side_n"] = len(side)
        meta["n_obj"] = int(sw.get("n_obj") or 0)
    except Exception:  # noqa: BLE001
        pass


def _judge(samples, seen, meta):
    del samples, seen
    side_n = int(meta.get("side_n") or 0)
    if side_n < 1:
        return False, "no_adjacent_scene_car", {
            "n_obj": meta.get("n_obj"),
            "side_n": side_n,
        }
    return True, "ok", {
        "note": "adjacent scene car in SurroundWorld; ego LC not judged",
        "side_n": side_n,
    }


CASE = AtomCase(
    tag="assist_lc",
    layout=layout_assist_lc,
    judge=_judge,
    weather_preset=None,
    early_exit_on_collision=False,
    on_tick=_on_tick,
    title="Assist LC scene (adjacent car)",
    default_duration_s=10.0,
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
