"""Host planning: Octave .m is the only engine (oct2py + octave-cli)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from .semantic_map import PlanningResult, PlanningView, lane_code_from_path

K_STEER_RATE = 0.08

_SESSION: Any = None
_LAST_STEER = 0.0


def resolve_octave_planning() -> Optional[Path]:
    """Directory that contains ``afc/m_lon_acc_aeb.m``."""
    env = (os.environ.get("GF_OCTAVE_PLANNING") or "").strip().strip('"').strip("'")
    here = Path(__file__).resolve()
    scenarios = here.parents[1]
    candidates: list[Path] = []
    if env:
        p = Path(env).expanduser()
        p = p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()
        candidates.append(p)
        if (p / "octave_planning").is_dir():
            candidates.append(p / "octave_planning")
    candidates.extend(
        [
            here.parents[2] / "octave_planning",
            scenarios.parent / "octave_planning",
            scenarios / "octave_planning",
        ]
    )
    seen: set[Path] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if (cand / "afc" / "m_lon_acc_aeb.m").is_file():
            return cand
    return None


def _octave_addpath(p: Path) -> str:
    return str(p.resolve()).replace("\\", "/")


def _b01(v: bool) -> float:
    return 1.0 if v else 0.0


def _as_float(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(x[0])  # numpy scalar / 1-vector from oct2py


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, bytes):
        return x.decode("utf-8", "replace")
    s = str(x).strip()
    return s.strip("'\"")


def _session():
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    import oct2py  # type: ignore

    root = resolve_octave_planning()
    if root is None:
        raise FileNotFoundError(
            "octave_planning not found (need afc/m_lon_acc_aeb.m). "
            "Copy repo octave_planning next to carla_scenarios, or set GF_OCTAVE_PLANNING. "
            f"cwd={Path.cwd()} GF_OCTAVE_PLANNING={os.environ.get('GF_OCTAVE_PLANNING')!r}"
        )
    oc = oct2py.Oct2Py()
    oc.addpath(_octave_addpath(root / "common"))
    oc.addpath(_octave_addpath(root / "afc"))
    print(f"[octave_bridge] Octave .m from {root}", flush=True)
    _SESSION = oc
    return oc


def close_octave() -> None:
    global _SESSION
    oc = _SESSION
    _SESSION = None
    if oc is None:
        return
    try:
        oc.exit()
    except Exception:  # noqa: BLE001
        pass


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _apply_shell(
    *,
    thr: float,
    brk: float,
    tgt: float,
    mode: str,
    steer: float,
    lane_valid: bool,
    e_y: float,
    lane_width_m: float,
    speed_mps: float,
) -> tuple[float, float, float, str, float]:
    """Lite shell around .m: AEB freeze steer, slew, invalid-lane brake."""
    global _LAST_STEER
    width = max(2.5, float(lane_width_m) if lane_width_m > 0.5 else 3.5)
    off = abs(float(e_y))
    if not lane_valid:
        thr = min(thr, 0.0)
        brk = max(brk, 0.35)
        tgt = min(tgt, 2.0)
    elif off > 0.6 * width:
        thr = min(thr, 0.08)
        brk = max(brk, 0.22)
        tgt = min(tgt, max(3.0, speed_mps * 0.55))
    if mode == "aeb":
        steer = 0.0
    ds = _clamp(steer - _LAST_STEER, -K_STEER_RATE, K_STEER_RATE)
    steer = _LAST_STEER + ds
    _LAST_STEER = steer
    return thr, brk, tgt, mode, steer


def plan_tick(view: PlanningView, *, seq: int = 0) -> PlanningResult:
    oc = _session()
    perc = view.perc
    ego = view.ego
    ctrl = oc.m_lon_acc_aeb(
        float(ego.speed_mps),
        _b01(perc.lead_valid),
        float(perc.lead_distance_m),
        float(perc.lead_rel_speed_mps),
    )
    steer = _as_float(
        oc.m_lat_lka(
            _b01(perc.lane_valid),
            float(perc.e_y),
            float(perc.c1),
            float(ego.steer_angle_deg),
        )
    )
    mode = _as_str(ctrl.mode)
    thr = _as_float(ctrl.throttle)
    brk = _as_float(ctrl.brake)
    tgt = _as_float(ctrl.target_speed_mps)
    thr, brk, tgt, mode, steer = _apply_shell(
        thr=thr,
        brk=brk,
        tgt=tgt,
        mode=mode,
        steer=steer,
        lane_valid=perc.lane_valid,
        e_y=perc.e_y,
        lane_width_m=perc.lane_width_m,
        speed_mps=ego.speed_mps,
    )

    speed_scale = 1.0
    if mode == "aeb":
        speed_scale = 0.15
    elif mode in ("acc", "pullaway"):
        speed_scale = max(0.3, min(1.2, tgt / max(ego.speed_mps, 1.0)))
    if not perc.lane_valid or abs(perc.e_y) > 0.6 * max(2.5, perc.lane_width_m):
        speed_scale = min(speed_scale, 0.4)

    speed_for_path = ego.speed_mps
    if ego.speed_mps < 1.0 and tgt > 1.0 and mode != "aeb":
        speed_for_path = tgt

    xs, ys, horizon = oc.m_lat_traj(
        float(speed_for_path),
        float(speed_scale),
        _b01(perc.lane_valid),
        float(perc.c0),
        float(perc.c1),
        float(perc.c2),
        float(perc.c3),
        float(perc.x_end),
        nout=3,
    )
    xs = [float(x) for x in list(xs.flatten())]
    ys = [float(y) for y in list(ys.flatten())]
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
        horizon_m=_as_float(horizon),
        lane_code=lane_code_from_path(ys),
    )
