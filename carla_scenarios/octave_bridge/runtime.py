"""Host planning: Octave .m only (oct2py). No post-plan shell — cal in gf_plan_cal.m."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from .semantic_map import PlanningResult, PlanningView, lane_code_from_path

_SESSION: Any = None
_LAST_PLAN_LOG = 0.0
_CAL: Any = None
_D_SEE_PREV = 0.0
_T_PLAN_PREV = 0.0


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


def plan_log_enabled() -> bool:
    v = (os.environ.get("GF_OCTAVE_PLAN_LOG") or "").strip().lower()
    return v in ("1", "on", "true", "yes")


def _octave_addpath(p: Path) -> str:
    return str(p.resolve()).replace("\\", "/")


def _b01(v: bool) -> float:
    return 1.0 if v else 0.0


def _as_vec(x: Any) -> list[float]:
    if x is None:
        return []
    if hasattr(x, "flatten"):
        return [float(v) for v in list(x.flatten())]
    if isinstance(x, (list, tuple)):
        out: list[float] = []
        for v in x:
            if isinstance(v, (list, tuple)):
                out.extend(float(u) for u in v)
            else:
                out.append(float(v))
        return out
    return [float(x)]


def _as_float(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(x[0])


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, bytes):
        return x.decode("utf-8", "replace")
    s = str(x).strip()
    return s.strip("'\"")


def _session():
    global _SESSION, _CAL
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
    _CAL = oc.gf_plan_cal()
    print(f"[octave_bridge] Octave .m from {root}", flush=True)
    print(
        f"[octave_bridge] cal T_base={_as_float(_CAL.t_base_s):.1f}s "
        f"D_fov={_as_float(_CAL.d_fov_conf_m):.0f}m "
        f"a={_as_float(_CAL.aeb_decel_mps2):.1f}m/s2 "
        f"cruise={_as_float(_CAL.cruise_v_mps):.1f}m/s "
        f"obj_n={_as_float(_CAL.obj_n_max):.0f} "
        f"ky={_as_float(_CAL.lat_ky):.2f} "
        f"plan_log={'on' if plan_log_enabled() else 'off'}",
        flush=True,
    )
    _SESSION = oc
    return oc


def close_octave() -> None:
    global _SESSION, _CAL, _D_SEE_PREV, _T_PLAN_PREV
    oc = _SESSION
    _SESSION = None
    _CAL = None
    _D_SEE_PREV = 0.0
    _T_PLAN_PREV = 0.0
    if oc is None:
        return
    try:
        oc.exit()
    except Exception:  # noqa: BLE001
        pass
    # Best-effort: oct2py sometimes leaves octave-cli after Ctrl+C.
    try:
        from _proc_util import kill_matching

        kill_matching("octave-cli")
        if __import__("sys").platform == "win32":
            kill_matching("octave.exe")
    except Exception:  # noqa: BLE001
        pass


def _lane_ok(perc: Any) -> bool:
    p = _CAL
    if p is None:
        return bool(perc.lane_valid)
    return (
        bool(perc.lane_valid)
        and abs(float(perc.e_y)) <= _as_float(p.lat_ey_invalid_m)
        and abs(float(perc.c1)) <= _as_float(p.lat_c1_invalid)
        and abs(float(perc.e_y)) <= _as_float(p.lat_ey_slow_m)
    )


def _pack_obj(perc: Any) -> list[list[float]]:
    """n×7: d, rel, lat, len, cls, heading, is_ped. Cap obj_n_max."""
    n_max = 8
    if _CAL is not None:
        n_max = max(1, int(_as_float(_CAL.obj_n_max)))
    rows: list[list[float]] = []
    lead_d = float(perc.lead_distance_m)
    lead_lat = float(perc.lead_lat_m)
    if perc.lead_valid:
        rows.append(
            [
                lead_d,
                float(perc.lead_rel_speed_mps),
                lead_lat,
                4.5,
                1.0,
                0.0,
                0.0,
            ]
        )
    for o in perc.objects:
        rec = [
            float(o.long_m),
            float(o.rel_v_mps),
            float(o.lat_m),
            float(o.len_m or 4.5),
            float(o.obj_class or 1),
            float(o.heading_rad or 0.0),
            float(o.is_ped or 0),
        ]
        if perc.lead_valid and abs(rec[0] - lead_d) < 1.5 and abs(rec[2] - lead_lat) < 0.8:
            rows[0] = rec
            continue
        if len(rows) >= n_max:
            break
        rows.append(rec)
    if not rows:
        # oct2py-safe dummy: out of lon_max / lat weight
        return [[999.0, 0.0, 99.0, 4.5, 1.0, 0.0, 0.0]]
    return rows[:n_max]


def plan_tick(view: PlanningView, *, seq: int = 0) -> PlanningResult:
    global _LAST_PLAN_LOG, _D_SEE_PREV, _T_PLAN_PREV
    oc = _session()
    perc = view.perc
    ego = view.ego
    out = oc.m_plan_tick(
        float(ego.speed_mps),
        float(ego.steer_angle_deg),
        _b01(perc.lane_valid),
        float(perc.e_y),
        float(perc.c0),
        float(perc.c1),
        float(perc.c2),
        float(perc.c3),
        float(perc.x_end),
        float(perc.lane_conf),
        float(perc.lane_count),
        _pack_obj(perc),
        float(_D_SEE_PREV),
        float(_T_PLAN_PREV),
    )
    mode = _as_str(out.mode)
    thr = _as_float(out.throttle)
    brk = _as_float(out.brake)
    tgt = _as_float(out.target_speed_mps)
    steer = _as_float(out.steer)
    D_see = _as_float(out.D_see)
    T_plan = _as_float(out.T_plan)
    _D_SEE_PREV = D_see
    _T_PLAN_PREV = T_plan
    xs = _as_vec(out.x_m)
    ys = _as_vec(out.y_m)
    vs = _as_vec(out.v_mps)

    now = time.monotonic()
    if plan_log_enabled() and (now - _LAST_PLAN_LOG) >= 0.5:
        _LAST_PLAN_LOG = now
        print(
            f"[octave_bridge] .m {mode} thr={thr:.2f} brk={brk:.2f} "
            f"v_plan={tgt:.1f} a_req={_as_float(out.a_req):.2f} "
            f"Dsee={D_see:.0f} T={T_plan:.1f} Docc={_as_float(out.D_occ):.0f} "
            f"lc={int(_as_float(out.allow_lc))} steer={steer:.2f} "
            f"v={ego.speed_mps:.1f} ey={perc.e_y:.2f} "
            f"lane={int(perc.lane_valid)} use={int(_lane_ok(perc))} "
            f"nobj={len(perc.objects)} lead={int(perc.lead_valid)} "
            f"d={perc.lead_distance_m:.1f} lat={perc.lead_lat_m:.1f}",
            flush=True,
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
        points_v_mps=vs,
        horizon_m=_as_float(out.horizon_m),
        D_see_m=D_see,
        T_plan_s=T_plan,
        allow_lc=int(_as_float(out.allow_lc)),
        lane_code=lane_code_from_path(ys),
    )
