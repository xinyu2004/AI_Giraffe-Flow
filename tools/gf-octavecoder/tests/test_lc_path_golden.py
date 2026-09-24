"""Committed S then new-host: mirrors m_lc_path.m / lc_path.hpp."""

from __future__ import annotations

import math

CAL = {
    "lane_width_m": 3.50,
    "d_lc_min_m": 40.0,
    "d_cal_cap_m": 120.0,
    "t_lc_min_s": 6.0,
    "d_lc_rear_min_m": 2.0,
    "d_lc_host_min_m": 8.0,
    "lc_cool_n": 20,
    "lc_ttc_margin_s": 1.0,
    "lc_hdg_same": 0.50,
    "closing_min_mps": 0.3,
    "wheelbase_m": 2.70,
    "traj_n": 16,
    "traj_speed_floor_mps": 0.2,
    "plan_dt_s": 0.05,
    "lc_dt_min_s": 0.01,
    "lc_dt_max_s": 0.20,
    "lc_done_eps_m": 0.50,
    "lc_settle_ey_m": 0.80,
    "lc_settle_steer_deg": 5.0,
    "lc_remap_ey_m": 1.20,
    "lc_done_hold_n": 8,
    "lc_reg_k": 1.0,
    "lc_commit_s": 0.25,
    "acc_time_gap_s": 1.7,
    "acc_gap_min_m": 8.0,
    "lat_e_sat_m": 1.8,
    "lat_c1_sat": 0.40,
    "lat_max_steer": 0.42,
    "lat_dsteer_max": 0.055,
    "traj_horizon_floor_m": 8.0,
    "traj_blend_m": 14.0,
    "lat_kpsi": 0.65,
    "lat_ey_invalid_m": 1.6,
}


def gf_clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def gf_lc_L_need() -> float:
    return CAL["d_lc_min_m"]


def gf_lc_T_need(v: float) -> float:
    p = CAL
    return gf_lc_L_need() / max(v, p["traj_speed_floor_mps"])


def gf_lc_t_need(v: float) -> float:
    return gf_lc_T_need(v)


def gf_lc_same_way(hdg: float) -> bool:
    return abs(hdg) <= CAL["lc_hdg_same"]


def gf_lc_time_ok(d: float, close_mps: float, opening: bool, v: float, T: float) -> bool:
    p = CAL
    if d < p["d_lc_rear_min_m"]:
        return False
    if close_mps > p["closing_min_mps"]:
        ttc = d / max(close_mps, 0.05)
        if ttc < T + p["lc_ttc_margin_s"]:
            return False
    elif not opening:
        if d + 0.5 < max(p["acc_gap_min_m"], max(0.0, v) * p["acc_time_gap_s"]):
            return False
    return True


def gf_lc_can(
    have: bool,
    d_f: float,
    d_r: float,
    rel_r: float,
    v: float,
    D_see: float,
    d_hard: float = 1.0e6,
    rel_f: float = 0.0,
    hdg_f: float = 0.0,
) -> bool:
    if not have:
        return False
    T = gf_lc_T_need(v)
    if T > CAL["t_lc_min_s"]:
        return False
    if d_f < 100.0 and not gf_lc_same_way(hdg_f):
        return False
    if not gf_lc_time_ok(d_f, max(0.0, -rel_f), rel_f > 0.3, v, T):
        return False
    if not gf_lc_time_ok(d_r, max(0.0, rel_r), rel_r < -0.3, v, T):
        return False
    if not gf_lc_time_ok(d_hard, max(0.0, v), False, v, T):
        return False
    if D_see < 0.0:
        return False
    return True


def gf_lc_hold_ok(
    d_f: float,
    d_r: float,
    rel_r: float,
    v: float,
    d_hard: float = 1.0e6,
    rel_f: float = 0.0,
    hdg_f: float = 0.0,
) -> bool:
    T = gf_lc_T_need(v)
    if d_f < 100.0 and not gf_lc_same_way(hdg_f):
        return False
    if not gf_lc_time_ok(d_f, max(0.0, -rel_f), rel_f > 0.3, v, T):
        return False
    if not gf_lc_time_ok(d_r, max(0.0, rel_r), rel_r < -0.3, v, T):
        return False
    if not gf_lc_time_ok(d_hard, max(0.0, v), False, v, T):
        return False
    return True


def lc_sigma(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5


def lc_geom(s: float, L: float, W: float, wb: float) -> tuple[float, float, float]:
    L = max(L, 1.0e-3)
    u = min(1.0, max(0.0, s / L))
    sigp = 30.0 * u**2 * (1.0 - u) ** 2
    sigpp = 60.0 * u * (1.0 - u) * (1.0 - 2.0 * u)
    yp = (W / L) * sigp
    ypp = (W / (L * L)) * sigpp
    psi = math.atan(yp)
    kappa = ypp / ((1.0 + yp * yp) ** 1.5)
    delta = -math.atan(wb * kappa)
    return psi, kappa, delta


def lc_sigma_inv(s: float) -> float:
    s = min(1.0, max(0.0, s))
    lo = 0.0
    hi = 1.0
    for _ in range(20):
        mid = 0.5 * (lo + hi)
        if lc_sigma(mid) < s:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def lc_corridor(W: float, lw: float) -> tuple[float, float]:
    half = 0.5 * max(lw, 1.0)
    if W >= 0.0:
        return -half, W + half
    return W - half, half


def lc_in_target(y: float, W: float, lw: float, ylo: float, yhi: float) -> bool:
    pad = 0.30
    line = 0.5 * max(lw, 1.0)
    if W >= 0.0:
        return y >= line - 0.20 and y <= yhi - pad
    return y <= -line + 0.20 and y >= ylo + pad


def gf_lat_host_delta(
    lane_valid: bool, e_y: float, c1: float, c2: float = 0.0, c3: float = 0.0, v: float = 0.0
) -> float:
    del c3
    p = CAL
    if not (lane_valid and abs(e_y) <= p["lat_ey_invalid_m"]):
        return 0.0
    e = gf_clamp(e_y, -p["lat_e_sat_m"], p["lat_e_sat_m"])
    c1c = gf_clamp(c1, -p["lat_c1_sat"], p["lat_c1_sat"])
    v_e = max(v, p["traj_speed_floor_mps"])
    yp = c1c
    ypp = 2.0 * c2
    kappa = ypp / ((1.0 + yp * yp) ** 1.5)
    d = -p["lat_kpsi"] * c1c - math.atan(p["lc_reg_k"] * e / v_e) - math.atan(
        p["wheelbase_m"] * kappa
    )
    return gf_clamp(d, -p["lat_max_steer"], p["lat_max_steer"])


def lc_delta_in_band(
    d_s: float, y: float, W: float, lw: float, ylo: float, yhi: float, across: int = 0
) -> float:
    pad = 0.30
    line = 0.5 * max(lw, 1.0)
    d = d_s
    if across == 0:
        if W >= 0.0:
            if y < line + pad:
                d = min(d, 0.0)
        elif y > -line - pad:
            d = max(d, 0.0)
    if y > yhi - pad:
        d = max(d, 0.04 * (y - (yhi - pad)))
    elif y < ylo + pad:
        d = min(d, -0.04 * ((ylo + pad) - y))
    return d


def lc_progress_s(x: float, y: float, L: float, W: float, lw: float) -> float:
    L = max(L, 1.0e-3)
    u_x = min(1.0, max(0.0, x / L))
    if abs(W) < 1.0e-3:
        return min(max(0.0, x), L)
    lat = min(1.0, max(0.0, y / W))
    u_y = lc_sigma_inv(lat)
    line = 0.5 * max(lw, 1.0)
    if abs(y) < line + 0.30:
        u = min(u_x, max(0.25, u_y), 0.5)
    elif u_y < 0.5:
        u = min(u_x, max(0.25, u_y))
    else:
        u = min(u_x, u_y)
    return u * L


_POSE = {
    "have": 0,
    "remapped": 0,
    "paint_ok": 0,
    "y": 0.0,
    "psi": 0.0,
    "e_y": 0.0,
    "y_dr": 0.0,
    "psi_dr": 0.0,
}

_ST = {
    "active": 0,
    "side": 0,
    "L": 0.0,
    "W": 0.0,
    "s": 0.0,
    "x": 0.0,
    "y": 0.0,
    "psi": 0.0,
    "plant_n": 0,
    "reg": 0,
    "reg_d": 0.0,
}


def _pose_zero() -> dict:
    return {
        "have": 0,
        "remapped": 0,
        "paint_ok": 0,
        "y": 0.0,
        "psi": 0.0,
        "e_y": 0.0,
        "y_dr": 0.0,
        "psi_dr": 0.0,
    }


def gf_lc_pose(
    pose: dict,
    e_y: float,
    c1: float,
    paint_ok: bool,
    W: float,
    y_dr: float,
    psi_dr: float,
) -> dict:
    p = CAL
    out = dict(pose)
    y_pre = -e_y
    y_post = W - e_y
    if paint_ok:
        if out["remapped"] == 0 and out["have"] != 0:
            closer_post = abs(y_post - out["y"]) + 0.40 < abs(y_pre - out["y"])
            jumped = abs(e_y - out["e_y"]) > p["lc_remap_ey_m"]
            if closer_post or jumped:
                out["remapped"] = 1
        out["y"] = y_post if out["remapped"] else y_pre
        out["psi"] = -c1
        out["e_y"] = e_y
    elif out["have"] != 0:
        out["y"] = out["y"] + (y_dr - out["y_dr"])
        out["psi"] = out["psi"] + (psi_dr - out["psi_dr"])
    else:
        out["y"] = y_dr
        out["psi"] = psi_dr
    out["y_dr"] = y_dr
    out["psi_dr"] = psi_dr
    out["have"] = 1
    out["paint_ok"] = 1 if paint_ok else 0
    return out


def m_lc_path_reset() -> None:
    _ST.update(
        active=0, side=0, L=0.0, W=0.0, s=0.0, x=0.0, y=0.0, psi=0.0, plant_n=0, reg=0, reg_d=0.0
    )
    _POSE.update(_pose_zero())


def m_lc_path(
    lc_side: int,
    v: float,
    d_f: float,
    d_r: float,
    rel_r: float = 0.0,
    dt: float = 0.0,
    steer_deg: float = 0.0,
    d_hard: float = 1.0e6,
    rel_f: float = 0.0,
    hdg_f: float = 0.0,
    e_y: float = 0.0,
    c1: float = 0.0,
    paint_ok: bool = False,
    c2: float = 0.0,
    c3: float = 0.0,
    land_ok: bool = True,
) -> tuple[list[float], list[float], float, dict]:
    p = CAL
    if dt <= 0.0:
        dt = p["plan_dt_s"]
    dt = gf_clamp(dt, p["lc_dt_min_s"], p["lc_dt_max_s"])
    v = max(0.0, v)
    side = 1 if lc_side > 0 else (-1 if lc_side < 0 else 0)
    n = p["traj_n"]
    xs = [0.0] * n
    ys = [0.0] * n
    horizon = 0.0
    hold = {
        "active": 0,
        "done": 0,
        "aborted": 0,
        "s_done": _ST["s"],
        "L": _ST["L"],
        "side": _ST["side"],
        "delta_ff": 0.0,
        "psi": 0.0,
        "kappa": 0.0,
        "e": 0.0,
        "epsi": 0.0,
        "y": 0.0,
        "y_s": 0.0,
        "y_road": 0.0,
        "remapped": 0,
        "paint_ok": 0,
        "reg": 0,
        "plant_n": 0,
    }
    if side == 0:
        m_lc_path_reset()
        return xs, ys, horizon, hold
    if _ST["active"] != 0:
        side = _ST["side"]
    if _ST["active"] == 0:
        L = gf_lc_L_need()
        if not gf_lc_can(True, d_f, d_r, rel_r, v, 0.0, d_hard, rel_f, hdg_f):
            return xs, ys, horizon, hold
        _ST["active"] = 1
        _ST["side"] = side
        _ST["L"] = L
        _ST["W"] = side * p["lane_width_m"]
        _ST["s"] = 0.0
        _ST["x"] = 0.0
        _ST["y"] = 0.0
        _ST["psi"] = 0.0
        _ST["plant_n"] = 0
        _ST["reg"] = 0
        _ST["reg_d"] = 0.0
        _POSE.update(_pose_zero())
    wb = p["wheelbase_m"]
    delta = steer_deg * math.pi / 180.0
    kap = -math.tan(delta) / max(wb, 0.5)
    _ST["psi"] = _ST["psi"] + v * kap * dt
    _ST["x"] = _ST["x"] + v * math.cos(_ST["psi"]) * dt
    _ST["y"] = _ST["y"] + v * math.sin(_ST["psi"]) * dt
    _POSE.update(gf_lc_pose(_POSE, e_y, c1, paint_ok, _ST["W"], _ST["y"], _ST["psi"]))
    y_use = _POSE["y"]
    psi_use = _POSE["psi"]
    if _ST["reg"] == 0:
        if (not land_ok) or (not gf_lc_hold_ok(d_f, d_r, rel_r, v, d_hard, rel_f, hdg_f)):
            hold["aborted"] = 1
            hold["active"] = 0
            hold["s_done"] = _ST["s"]
            hold["L"] = _ST["L"]
            hold["side"] = _ST["side"]
            m_lc_path_reset()
            return xs, ys, horizon, hold
    ylo, yhi = lc_corridor(_ST["W"], p["lane_width_m"])
    if _ST["reg"]:
        s_raw = _ST["s"]
    else:
        s_raw = lc_progress_s(_ST["x"], y_use, _ST["L"], _ST["W"], p["lane_width_m"])
    _ST["s"] = max(_ST["s"], s_raw)
    psi_s, k_s, d_s = lc_geom(_ST["s"], _ST["L"], _ST["W"], wb)
    if _ST["reg"] == 0 and _POSE["remapped"]:
        in_band = abs(e_y) < p["lc_settle_ey_m"]
        if (not in_band) and _ST["s"] + 1.0e-3 >= _ST["L"]:
            in_band = lc_in_target(y_use, _ST["W"], p["lane_width_m"], ylo, yhi)
        if in_band:
            _ST["reg_d"] = d_s
            _ST["reg"] = 1
    if _ST["reg"]:
        if paint_ok:
            d_s = gf_lat_host_delta(True, e_y, c1, c2, c3, v)
        else:
            d_s = _ST["reg_d"]
        d_s = lc_delta_in_band(d_s, y_use, _ST["W"], p["lane_width_m"], ylo, yhi, 1)
        _ST["reg_d"] = d_s
        psi_s = 0.0
        k_s = 0.0
        y_s = _ST["W"]
        hold["e"] = e_y
        hold["epsi"] = psi_use
    else:
        d_s = lc_delta_in_band(d_s, y_use, _ST["W"], p["lane_width_m"], ylo, yhi, 0)
        y_s = gf_clamp(_ST["W"] * lc_sigma(_ST["s"] / max(_ST["L"], 1.0e-3)), ylo, yhi)
        dx = _ST["x"] - _ST["s"]
        dy = y_use - y_s
        hold["e"] = -dx * math.sin(psi_s) + dy * math.cos(psi_s)
        hold["epsi"] = psi_use - psi_s
    hold["s_done"] = _ST["s"]
    hold["L"] = _ST["L"]
    hold["side"] = _ST["side"]
    hold["psi"] = psi_s
    hold["kappa"] = k_s
    hold["delta_ff"] = d_s
    hold["y"] = _ST["y"]
    hold["y_s"] = y_s
    hold["y_road"] = y_use
    hold["remapped"] = _POSE["remapped"]
    hold["paint_ok"] = _POSE["paint_ok"]
    hold["reg"] = _ST["reg"]
    psi_lim = p["lc_settle_steer_deg"] * math.pi / 180.0
    if paint_ok:
        psi_done = psi_use
        if _POSE["remapped"]:
            in_tgt = abs(e_y) < p["lc_settle_ey_m"]
        else:
            in_tgt = lc_in_target(y_use, _ST["W"], p["lane_width_m"], ylo, yhi)
    else:
        psi_done = _ST["psi"]
        in_tgt = lc_in_target(_ST["y"], _ST["W"], p["lane_width_m"], ylo, yhi)
    d_deg = d_s * 180.0 / math.pi
    d_lim = abs(d_deg) < p["lc_settle_steer_deg"]
    trk_lim = abs(steer_deg - d_deg) < p["lc_settle_steer_deg"]
    planted = (
        in_tgt
        and abs(psi_done) < psi_lim
        and abs(steer_deg) < p["lc_settle_steer_deg"]
        and d_lim
        and trk_lim
    )
    if planted:
        _ST["plant_n"] += 1
    else:
        _ST["plant_n"] = 0
    hold["plant_n"] = _ST["plant_n"]
    if planted and _ST["plant_n"] >= p["lc_done_hold_n"]:
        hold["done"] = 1
        hold["active"] = 0
        m_lc_path_reset()
        return xs, ys, horizon, hold
    hold["active"] = 1
    if _ST["reg"]:
        D = max(p["traj_horizon_floor_m"], v * 2.0)
        T = D / max(v, p["traj_speed_floor_mps"])
        D_plan = max(p["traj_horizon_floor_m"], min(D, v * T if T > 0.0 else D))
        horizon = D_plan
        blend = p["traj_blend_m"]
        for i in range(n):
            x = (D_plan / max(n - 1, 1)) * i
            xs[i] = x
            alpha = 1.0 - math.exp(-x / blend)
            ys[i] = alpha * (e_y + c1 * x + c2 * x * x + c3 * x * x * x)
        return xs, ys, horizon, hold
    remain = max(0.0, _ST["L"] - _ST["s"])
    horizon = remain
    xs[0] = 0.0
    ys[0] = 0.0
    c0 = math.cos(psi_use)
    s0 = math.sin(psi_use)
    ds = remain / (n - 1)
    for i in range(1, n):
        t = _ST["s"] + ds * i
        ys_c = gf_clamp(_ST["W"] * lc_sigma(t / max(_ST["L"], 1.0e-3)), ylo, yhi)
        rx = t - _ST["x"]
        ry = ys_c - y_use
        xs[i] = rx * c0 + ry * s0
        ys[i] = -rx * s0 + ry * c0
    return xs, ys, horizon, hold


def test_enter_left_tangent_body() -> None:
    m_lc_path_reset()
    xs, ys, h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    assert hold["L"] == 40.0
    assert abs(h - (40.0 - 25.0 * 0.05)) < 1e-5
    assert abs(ys[0]) < 1e-6
    assert abs(xs[0]) < 1e-6
    assert ys[-1] > 2.0
    assert hold["delta_ff"] < 0.0


def test_short_dsee_does_not_shrink_hold() -> None:
    m_lc_path_reset()
    _xs, _ys, h, hold = m_lc_path(1, 25.0, 120.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    assert hold["L"] == 40.0
    assert h > 30.0


def test_slow_no_enter() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 2.7, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 0
    m_lc_path_reset()
    _xs2, _ys2, _h2, hold2 = m_lc_path(1, 8.0, 80.0, 20.0, 0.0, 0.05)
    assert hold2["active"] == 1
    assert hold2["L"] == 40.0


def test_dr_zero_steer_e_grows() -> None:
    m_lc_path_reset()
    e0 = 0.0
    for _ in range(20):
        _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0)
        e0 = hold["e"]
    assert hold["active"] == 1
    assert abs(e0) > 0.2


def test_hard_mid_hold_aborts() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0, 120.0)
    assert hold["active"] == 1
    _xs2, _ys2, _h2, hold2 = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0, 5.0)
    assert hold2["aborted"] == 1
    assert hold2["active"] == 0


def test_enter_acc_gap_L_stays_40() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 10.0, 35.0, 30.0, 0.0, 0.05)
    assert hold["active"] == 1
    assert hold["L"] == 40.0
    m_lc_path_reset()
    _xs2, _ys2, _h2, hold2 = m_lc_path(1, 25.0, 15.0, 30.0, 0.0, 0.05)
    assert hold2["active"] == 0


def test_delta_in_then_back() -> None:
    m_lc_path_reset()
    early = None
    late = None
    steer = 0.0
    for _ in range(200):
        _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, steer)
        if hold["done"]:
            break
        steer = hold["delta_ff"] * 180.0 / math.pi
        if hold["s_done"] < 12.0:
            early = hold["delta_ff"]
        if hold["s_done"] > 22.0:
            late = hold["delta_ff"]
    assert early is not None and early < 0.0
    assert late is not None and late > 0.0
    assert abs(early) < 0.08 and abs(late) < 0.08


def test_same_speed_4m_aborts() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    _xs2, _ys2, _h2, hold2 = m_lc_path(1, 25.0, 80.0, 4.0, 0.0, 0.05)
    assert hold2["aborted"] == 1
    assert hold2["active"] == 0


def test_opening_4m_does_not_abort() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    _xs2, _ys2, _h2, hold2 = m_lc_path(1, 25.0, 80.0, 4.0, -1.0, 0.05)
    assert hold2["aborted"] == 0
    assert hold2["active"] == 1


def test_abort_pad() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    _xs2, ys2, _h2, hold2 = m_lc_path(1, 25.0, 80.0, 0.5, 0.0, 0.05)
    assert hold2["aborted"] == 1
    assert hold2["active"] == 0
    assert max(abs(y) for y in ys2) < 1e-9


def test_abort_closing_ttc() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    _xs2, _ys2, _h2, hold2 = m_lc_path(1, 25.0, 80.0, 10.0, 5.0, 0.05)
    assert hold2["aborted"] == 1
    assert hold2["active"] == 0


def test_s_waits_for_y() -> None:
    m_lc_path_reset()
    hold = {"active": 0, "s_done": 0.0, "done": 0}
    for _ in range(40):
        _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0)
    assert hold["active"] == 1
    assert hold["done"] == 0
    assert hold["s_done"] <= 10.0 + 1e-3
    assert hold["delta_ff"] < 0.0


def test_hold_ignores_side_flip() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    _xs2, _ys2, _h2, hold2 = m_lc_path(-1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold2["active"] == 1
    assert hold2["side"] == 1
    assert hold2["delta_ff"] < 0.0


def test_follow_reaches_done() -> None:
    m_lc_path_reset()
    hold = {"done": 0, "active": 0}
    steer = 0.0
    for _ in range(250):
        _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, steer)
        if hold["done"]:
            break
        steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["done"] == 1
    assert hold["active"] == 0


def test_hold_survives_slow() -> None:
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    _xs2, _ys2, _h2, hold2 = m_lc_path(1, 2.7, 80.0, 45.0, 0.0, 0.05)
    assert hold2["aborted"] == 0
    assert hold2["active"] == 1


def test_side_zero_clears() -> None:
    m_lc_path_reset()
    m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    _xs, ys, _h, hold = m_lc_path(0, 25.0, 80.0, 30.0, 0.0, 0.05)
    assert hold["active"] == 0
    assert max(abs(y) for y in ys) < 1e-9


def test_exec_delta_left_is_negative() -> None:
    import test_lat_golden as lat

    lat._LAST_FOLLOW = 0.0
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    s = 0.0
    for _ in range(8):
        s = lat.m_lat_follow(hold["delta_ff"])
    assert s < 0.0
    assert abs(s) <= lat.CAL["lat_dsteer_max"] * 8 + 1e-6


def test_no_return_steer_until_across() -> None:
    m_lc_path_reset()
    for _ in range(40):
        _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0)
        assert hold["active"] == 1
        assert hold["delta_ff"] <= 1e-6
        assert hold["s_done"] <= 20.0 + 1e-3


def test_path_stays_in_commit_corridor() -> None:
    m_lc_path_reset()
    xs, ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05)
    assert hold["active"] == 1
    ylo, yhi = lc_corridor(3.5, 3.5)
    assert ylo == -1.75 and yhi == 5.25
    assert min(ys) > ylo - 0.05
    assert max(ys) < yhi + 0.05
    assert xs[0] == 0.0


def test_enter_allows_residual_steer() -> None:
    # Residual steer is host-keep after done, not an enter veto.
    m_lc_path_reset()
    _xs, _ys, _h, hold = m_lc_path(1, 25.0, 80.0, 45.0, 0.0, 0.05, 11.0)
    assert hold["active"] == 1


def _cool_step(cool: int, follow: bool, done: bool, aborted: bool) -> int:
    # 1:1 m_plan.m: cool only blocks re-enter. No coast law switch.
    p = CAL
    if follow:
        return 0
    if done or aborted:
        cool = int(p["lc_cool_n"])
    if cool > 0:
        cool -= 1
    return cool


def _plan_target(follow: bool) -> int:
    return 1 if follow else 0


def test_cool_expires_even_if_heading_left() -> None:
    cool = _cool_step(0, False, True, False)
    assert cool == 19
    for _ in range(18):
        cool = _cool_step(cool, False, False, False)
    cool = _cool_step(cool, False, False, False)
    assert cool == 0


def test_cool_expires_even_if_ey_small() -> None:
    cool = _cool_step(0, False, True, False)
    assert cool == 19
    for _ in range(19):
        cool = _cool_step(cool, False, False, False)
    assert cool == 0


def test_no_target_two() -> None:
    assert _plan_target(True) == 1
    assert _plan_target(False) == 0


def test_pose_remap_picks_post() -> None:
    pose = _pose_zero()
    pose = gf_lc_pose(pose, -1.47, 0.13, True, 3.5, 2.0, 0.16)
    assert pose["remapped"] == 0
    assert abs(pose["y"] - 1.47) < 1e-6
    pose = gf_lc_pose(pose, 1.45, 0.12, True, 3.5, 2.5, 0.17)
    assert pose["remapped"] == 1
    assert abs(pose["y"] - (3.5 - 1.45)) < 1e-6


def test_paint_blocks_done_while_old_host() -> None:
    m_lc_path_reset()
    hold = {"done": 0, "active": 0}
    steer = 0.0
    for _ in range(250):
        _xs, _ys, _h, hold = m_lc_path(
            1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, -0.20, 0.0, True
        )
        if hold["done"]:
            break
        steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["done"] == 0
    assert hold["active"] == 1
    assert hold["remapped"] == 0


def test_s_monotonic_after_y_drop() -> None:
    m_lc_path_reset()
    steer = 0.0
    last_s = 0.0
    for ey in (-0.2, -0.8, -1.4, 1.3, 1.9, 2.2):
        for _ in range(8):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.10, True
            )
            if hold["done"]:
                break
            assert hold["s_done"] + 1e-4 >= last_s
            last_s = hold["s_done"]
            steer = hold["delta_ff"] * 180.0 / math.pi
        if hold["done"]:
            break
    assert last_s > 1.0
    assert hold["s_done"] + 1e-4 >= last_s


def test_remap_keeps_s_until_in_band() -> None:
    # FCM jump is pose only. e_y=1.4 > settle → stay on S, s still grows.
    m_lc_path_reset()
    steer = 0.0
    hold = {"done": 0, "s_done": 0.0}
    for ey in (-0.2, -1.4, 1.4):
        for _ in range(8):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.12, True
            )
            if hold["done"]:
                break
            steer = hold["delta_ff"] * 180.0 / math.pi
        if hold["done"]:
            break
    assert hold["remapped"] == 1
    assert hold["reg"] == 0
    assert hold["done"] == 0
    s0 = hold["s_done"]
    d_s = hold["delta_ff"]
    d_host = gf_lat_host_delta(True, 1.4, 0.12, 0.0, 0.0, 25.0)
    assert abs(d_s - d_host) > 1e-3
    for _ in range(8):
        _xs, _ys, _h, hold = m_lc_path(
            1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, 1.4, 0.12, True
        )
        steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["reg"] == 0
    assert hold["s_done"] + 1e-4 >= s0
    for _ in range(6):
        _xs, _ys, _h, hold = m_lc_path(
            1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, 0.30, 0.12, True
        )
        steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["reg"] == 1
    s1 = hold["s_done"]
    for _ in range(8):
        _xs, _ys, _h, hold = m_lc_path(
            1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, 0.30, 0.12, True
        )
        assert hold["done"] == 0
        steer = hold["delta_ff"] * 180.0 / math.pi
    assert abs(hold["s_done"] - s1) < 1e-3
    assert hold["reg"] == 1


def test_reg_kills_heading_not_freeze_delta() -> None:
    # In-band after remap: host-keep must track live (e,c1), not a latched S δ.
    m_lc_path_reset()
    steer = 0.0
    hold = {"done": 0}
    for ey in (-0.2, -1.4, 1.67):
        for _ in range(8):
            _xs, _ys, _h, hold = m_lc_path(
                1, 11.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, -0.160, True
            )
            if hold["done"]:
                break
            steer = hold["delta_ff"] * 180.0 / math.pi
        if hold["done"]:
            break
    assert hold["remapped"] == 1
    assert hold["reg"] == 0
    last_d = hold["delta_ff"]
    for _ in range(20):
        _xs, _ys, _h, hold = m_lc_path(
            1, 11.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, 0.70, -0.160, True
        )
        assert hold["done"] == 0
        steer = hold["delta_ff"] * 180.0 / math.pi
        last_d = hold["delta_ff"]
    assert hold["reg"] == 1
    d_des = gf_lat_host_delta(True, 0.70, -0.160, 0.0, 0.0, 11.0)
    assert last_d > 0.03
    assert abs(last_d - d_des) < 1e-6


def test_remap_does_not_chase_host_while_short() -> None:
    # Log case: remapped at y≈1.9 / e_y=1.60. Must not switch to +host-keep.
    m_lc_path_reset()
    steer = 0.0
    hold = {"done": 0}
    for ey in (-0.2, -1.4, 1.5):
        for _ in range(6):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, -0.16, True
            )
            steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["remapped"] == 1
    assert hold["reg"] == 0
    for _ in range(12):
        _xs, _ys, _h, hold = m_lc_path(
            1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, 1.60, -0.20, True
        )
        steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["reg"] == 0
    d_des = gf_lat_host_delta(True, 1.60, -0.20, 0.0, 0.0, 25.0)
    assert abs(hold["delta_ff"] - d_des) > 1e-3


def test_no_done_on_fresh_ey_jump() -> None:
    # Remap into the plant box: first crossing is not done. Need dwell.
    m_lc_path_reset()
    steer = 0.0
    hold = {"done": 0, "plant_n": 0}
    for ey in (-0.2, -1.4):
        for _ in range(6):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.0, True
            )
            steer = hold["delta_ff"] * 180.0 / math.pi
    _xs, _ys, _h, hold = m_lc_path(
        1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0, 1.0e6, 0.0, 0.0, 0.20, 0.02, True
    )
    assert hold["remapped"] == 1
    assert hold["done"] == 0
    assert hold["plant_n"] == 1
    for i in range(CAL["lc_done_hold_n"] - 1):
        _xs, _ys, _h, hold = m_lc_path(
            1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0, 1.0e6, 0.0, 0.0, 0.20, 0.02, True
        )
        if i + 2 < CAL["lc_done_hold_n"]:
            assert hold["done"] == 0
            assert hold["plant_n"] == i + 2
    assert hold["done"] == 1
    assert hold["active"] == 0


def test_abort_after_remap_before_reg() -> None:
    # Remapped but still on S: world/FS abort still applies.
    m_lc_path_reset()
    steer = 0.0
    hold = {"remapped": 0, "aborted": 0}
    for ey in (-0.2, -1.4, 1.5):
        for _ in range(8):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.12, True
            )
            steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["remapped"] == 1
    assert hold["reg"] == 0
    _xs, _ys, _h, hold = m_lc_path(
        1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 5.0, 0.0, 0.0, 1.5, 0.12, True
    )
    assert hold["aborted"] == 1
    assert hold["active"] == 0


def test_no_abort_after_reg_if_hold_ok_fails() -> None:
    # After law switch, tight d_hard must not abort — host-keep stays until dwell.
    m_lc_path_reset()
    steer = 0.0
    hold = {"remapped": 0, "aborted": 0}
    for ey in (-0.2, -1.4, 0.30):
        for _ in range(8):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.12, True
            )
            steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["remapped"] == 1
    assert hold["reg"] == 1
    _xs, _ys, _h, hold = m_lc_path(
        1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 5.0, 0.0, 0.0, 0.30, 0.12, True
    )
    assert hold["aborted"] == 0
    assert hold["active"] == 1
    assert hold["reg"] == 1


def test_land_lost_aborts_before_reg() -> None:
    m_lc_path_reset()
    steer = 0.0
    hold = {"aborted": 0}
    for ey in (-0.2, -1.4):
        for _ in range(6):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.0, True
            )
            steer = hold["delta_ff"] * 180.0 / math.pi
    _xs, _ys, _h, hold = m_lc_path(
        1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, -0.2, 0.0, True, 0.0, 0.0, False
    )
    assert hold["aborted"] == 1
    assert hold["active"] == 0


def test_plant_n_resets_if_gate_fails() -> None:
    m_lc_path_reset()
    steer = 0.0
    hold = {"done": 0, "plant_n": 0}
    for ey in (-0.2, -1.4):
        for _ in range(6):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.0, True
            )
            steer = hold["delta_ff"] * 180.0 / math.pi
    _xs, _ys, _h, hold = m_lc_path(
        1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0, 1.0e6, 0.0, 0.0, 0.20, 0.02, True
    )
    assert hold["plant_n"] == 1
    _xs, _ys, _h, hold = m_lc_path(
        1, 25.0, 80.0, 45.0, 0.0, 0.05, 0.0, 1.0e6, 0.0, 0.0, 0.20, 0.30, True
    )
    assert hold["done"] == 0
    assert hold["plant_n"] == 0
    assert hold["active"] == 1


def test_paint_done_after_remap_centered() -> None:
    m_lc_path_reset()
    steer = 0.0
    hold = {"done": 0}
    for ey in (-0.2, -0.8, -1.4, 1.3, 0.4, 0.2):
        for _ in range(8):
            _xs, _ys, _h, hold = m_lc_path(
                1, 25.0, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.0, True
            )
            if hold["done"]:
                break
            steer = hold["delta_ff"] * 180.0 / math.pi
        if hold["done"]:
            break
    assert hold["done"] == 1
    assert hold["remapped"] == 1


def test_host_keep_same_idle_and_after_reg() -> None:
    e_y, c1, v = 0.35, -0.0014, 20.6
    idle = gf_lat_host_delta(True, e_y, c1, 0.0, 0.0, v)
    m_lc_path_reset()
    steer = 0.0
    hold = {"remapped": 0}
    for ey in (-0.2, -1.4, 0.35):
        for _ in range(8):
            _xs, _ys, _h, hold = m_lc_path(
                1, v, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, ey, 0.12, True
            )
            steer = hold["delta_ff"] * 180.0 / math.pi
    assert hold["remapped"] == 1
    assert hold["reg"] == 1
    _xs, ys, _h, hold = m_lc_path(
        1, v, 80.0, 45.0, 0.0, 0.05, steer, 1.0e6, 0.0, 0.0, e_y, c1, True
    )
    assert abs(hold["delta_ff"] - idle) < 1e-6
    # Reg path is host poly (blend to e_y), not the old y=e_y·t line.
    assert abs(ys[0]) < 1e-6
    assert ys[-1] > 0.2
    assert abs(ys[-1] - e_y) < 0.15


def test_host_keep_curve_ff() -> None:
    flat = gf_lat_host_delta(True, 0.0, 0.0, 0.0, 0.0, 20.0)
    bend = gf_lat_host_delta(True, 0.0, 0.0, 0.002, 0.0, 20.0)
    assert abs(flat) < 1e-9
    assert bend < 0.0
    kappa = 2.0 * 0.002
    assert abs(bend - (-math.atan(CAL["wheelbase_m"] * kappa))) < 1e-6


def test_sigma_endpoints() -> None:
    du = 1e-4
    d0 = (lc_sigma(du) - lc_sigma(0.0)) / du
    d1 = (lc_sigma(1.0) - lc_sigma(1.0 - du)) / du
    assert abs(d0) < 2e-3 and abs(d1) < 2e-3
    _p, k0, dlt0 = lc_geom(0.0, 40.0, 3.5, 2.7)
    _p, k1, dlt1 = lc_geom(40.0, 40.0, 3.5, 2.7)
    assert abs(k0) < 1e-6 and abs(k1) < 1e-6
    assert abs(dlt0) < 1e-6 and abs(dlt1) < 1e-6


def test_generate_lc_path_header() -> None:
    from pathlib import Path

    from gf_octavecoder.generate import generate_sku

    root = Path(__file__).resolve().parents[3]
    assert generate_sku(repo_root=root, sku="adc", force=True) == 0
    p = root / "projects/adc/apps/planning/driving_plus/oct_gen/m_lc_path.hpp"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "m_lc_path" in text
    assert "rel_r" in text
    assert "hdg_f" in text
