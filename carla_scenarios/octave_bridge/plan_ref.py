"""Python reference of octave_planning/afc (1:1 with gf_octave_planning ops).

Used when Octave engine is unavailable; keep semantics aligned with .m / C++.
"""

from __future__ import annotations

import math
from typing import Tuple

from .semantic_map import PlanningResult, PlanningView, lane_code_from_path

K_LAT_TRAJ_POINTS = 16
K_BLEND_LEN_M = 18.0
K_STEER_KY = 0.35
K_STEER_KPSI = 0.80
K_MAX_STEER = 0.55


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def lon_cruise(v: float) -> Tuple[float, float, float, str]:
    target = 12.0
    err = target - v
    if v < 0.8:
        thr = _clamp(0.45 + err * 0.05, 0.40, 0.75)
        brk = 0.0
    else:
        thr = _clamp(0.2 + err * 0.08, 0.0, 0.7)
        brk = _clamp((-err - 2.0) * 0.1, 0.0, 0.4) if err < -2.0 else 0.0
    return thr, brk, target, "cruise"


def lon_aeb(v: float, d: float, ttc: float) -> Tuple[float, float, float, str]:
    del v
    brk = 1.0 if (d < 5.0 or ttc < 1.0) else _clamp(0.55 + (10.0 - d) * 0.05, 0.55, 1.0)
    return 0.0, brk, 0.0, "aeb"


def lon_pullaway(v: float, d: float, rel: float, gap_err: float) -> Tuple[float, float, float, str]:
    del d
    pull = _clamp(8.0 + gap_err * 0.2 + rel * 0.3, 6.0, 12.0)
    thr = _clamp(0.42 + (pull - v) * 0.06, 0.35, 0.75)
    return thr, 0.0, pull, "pullaway"


def lon_acc_follow(v: float, d: float, rel: float) -> Tuple[float, float, float, str]:
    desired_gap = _clamp(max(8.0, v * 1.6), 8.0, 40.0)
    gap_err = d - desired_gap
    target = _clamp(v + gap_err * 0.15 + rel * 0.4, 0.0, 16.0)
    speed_err = target - v
    if speed_err >= 0.0:
        return _clamp(0.15 + speed_err * 0.1, 0.0, 0.65), 0.0, target, "acc"
    return 0.0, _clamp((-speed_err) * 0.12, 0.0, 0.7), target, "acc"


def m_lon_acc_aeb(
    v: float, lead_valid: bool, d: float, rel: float
) -> Tuple[float, float, float, str]:
    v = max(0.0, v)
    if not lead_valid:
        return lon_cruise(v)
    closing = max(0.0, -rel)
    ttc = (d / closing) if closing > 0.5 else 1.0e6
    if d < 5.0 or (v > 1.2 and (d < 10.0 or ttc < 1.4)):
        return lon_aeb(v, d, ttc)
    desired_gap = _clamp(max(8.0, v * 1.6), 8.0, 40.0)
    gap_err = d - desired_gap
    if v < 1.0 and d > 10.0:
        return lon_pullaway(v, d, rel, gap_err)
    return lon_acc_follow(v, d, rel)


def m_lat_lka(lane_valid: bool, e_y: float, c1: float, steer_angle_deg: float) -> float:
    if lane_valid:
        return _clamp(-K_STEER_KY * e_y - K_STEER_KPSI * c1, -K_MAX_STEER, K_MAX_STEER)
    return _clamp(steer_angle_deg / 25.0, -1.0, 1.0)


def m_lat_traj(
    speed_mps: float,
    speed_scale: float,
    lane_valid: bool,
    c0: float,
    c1: float,
    c2: float,
    c3: float,
    x_end: float,
) -> Tuple[list[float], list[float], float]:
    speed = max(speed_mps * speed_scale, 0.2)
    x_cap = x_end if lane_valid else 100.0
    horizon = _clamp(speed * 4.0, 25.0, min(100.0, x_cap))
    ds = horizon / float(K_LAT_TRAJ_POINTS - 1)
    xs: list[float] = []
    ys: list[float] = []
    for i in range(K_LAT_TRAJ_POINTS):
        x = ds * float(i)
        xs.append(x)
        if lane_valid:
            alpha = 1.0 - math.exp(-x / K_BLEND_LEN_M)
            y = c0 + c1 * x + c2 * x * x + c3 * x * x * x
            ys.append(alpha * y)
        else:
            ys.append(0.0)
    return xs, ys, horizon


def plan_tick_ref(view: PlanningView, *, seq: int = 0) -> PlanningResult:
    """Same orchestration as planning/driving main.cpp (lon+lat+traj)."""
    ego = view.ego
    perc = view.perc
    thr, brk, tgt, mode = m_lon_acc_aeb(
        ego.speed_mps, perc.lead_valid, perc.lead_distance_m, perc.lead_rel_speed_mps
    )
    steer = m_lat_lka(perc.lane_valid, perc.e_y, perc.c1, ego.steer_angle_deg)

    speed_scale = 1.0
    if mode == "aeb":
        speed_scale = 0.15
    elif mode in ("acc", "pullaway"):
        speed_scale = _clamp(tgt / max(ego.speed_mps, 1.0), 0.3, 1.2)

    speed_for_path = ego.speed_mps
    if ego.speed_mps < 1.0 and tgt > 1.0 and mode != "aeb":
        speed_for_path = tgt

    xs, ys, horizon = m_lat_traj(
        speed_for_path,
        speed_scale,
        perc.lane_valid,
        perc.c0,
        perc.c1,
        perc.c2,
        perc.c3,
        perc.x_end,
    )
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
        horizon_m=horizon,
        lane_code=lane_code_from_path(ys),
    )
