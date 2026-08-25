"""Call planning: default Python ref; optional Octave via GF_OCTAVE_BRIDGE_ENGINE=octave."""

from __future__ import annotations

import os
from typing import Literal

from .plan_ref import plan_tick_ref
from .semantic_map import PlanningResult, PlanningView

Engine = Literal["ref", "octave"]


def resolve_engine() -> Engine:
    v = (os.environ.get("GF_OCTAVE_BRIDGE_ENGINE") or "ref").strip().lower()
    if v in ("octave", "m", ".m"):
        return "octave"
    return "ref"


def plan_tick(view: PlanningView, *, seq: int = 0, engine: Engine | None = None) -> PlanningResult:
    eng = engine or resolve_engine()
    if eng == "octave":
        try:
            return _plan_tick_octave(view, seq=seq)
        except Exception as exc:  # noqa: BLE001 — fall back with log-worthy message
            print(f"[octave_bridge] octave engine failed ({exc}); using ref", flush=True)
    return plan_tick_ref(view, seq=seq)


def _plan_tick_octave(view: PlanningView, *, seq: int) -> PlanningResult:
    """Best-effort: run .m helpers via oct2py if installed.

    Full path still under construction; contract is plan_tick(view)->result.
    """
    import oct2py  # type: ignore

    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "octave_planning"
    oc = oct2py.Oct2Py()
    try:
        oc.addpath(str(root / "common"))
        oc.addpath(str(root / "afc"))
        perc = view.perc
        ego = view.ego
        ctrl = oc.m_lon_acc_aeb(
            float(ego.speed_mps),
            bool(perc.lead_valid),
            float(perc.lead_distance_m),
            float(perc.lead_rel_speed_mps),
        )
        steer = float(
            oc.m_lat_lka(
                bool(perc.lane_valid),
                float(perc.e_y),
                float(perc.c1),
                float(ego.steer_angle_deg),
            )
        )
        mode = str(ctrl.mode)
        thr = float(ctrl.throttle)
        brk = float(ctrl.brake)
        tgt = float(ctrl.target_speed_mps)
        speed_scale = 1.0
        if mode == "aeb":
            speed_scale = 0.15
        elif mode in ("acc", "pullaway"):
            speed_scale = max(0.3, min(1.2, tgt / max(ego.speed_mps, 1.0)))
        speed_for_path = ego.speed_mps
        if ego.speed_mps < 1.0 and tgt > 1.0 and mode != "aeb":
            speed_for_path = tgt
        xs, ys, horizon = oc.m_lat_traj(
            float(speed_for_path),
            float(speed_scale),
            bool(perc.lane_valid),
            float(perc.c0),
            float(perc.c1),
            float(perc.c2),
            float(perc.c3),
            float(perc.x_end),
            nout=3,
        )
        xs = [float(x) for x in list(xs.flatten())]
        ys = [float(y) for y in list(ys.flatten())]
        from .semantic_map import PlanningResult, lane_code_from_path

        return PlanningResult(
            stamp_ns=view.stamp_ns,
            seq=seq,
            throttle=thr,
            brake=brk,
            steer=steer,
            target_speed_mps=tgt,
            ctrl_mode=mode,
            points_x_m=xs,
            points_y_m=ys,
            horizon_m=float(horizon),
            lane_code=lane_code_from_path(ys),
        )
    finally:
        oc.exit()
