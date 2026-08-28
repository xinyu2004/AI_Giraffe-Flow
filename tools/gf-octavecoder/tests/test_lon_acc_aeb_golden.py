from __future__ import annotations

"""Golden vectors for v4 lon: plan_v_at_s + lon_exec (not ACC/AEB FSM)."""

import math

CAL = {
    "lat_aeb_m": 8.0,
    "lat_merge_m": 1.0,
    "lon_max_d_m": 80.0,
    "t_base_s": 10.0,
    "t_plan_min_s": 1.0,
    "d_cal_cap_m": 120.0,
    "d_fov_conf_m": 120.0,
    "d_see_lane_bad_m": 12.0,
    "vis_up_alpha": 0.08,
    "cutin_head_gain": 1.20,
    "acc_time_gap_s": 1.7,
    "acc_gap_min_m": 8.0,
    "aeb_decel_mps2": 6.0,
    "aeb_d_min_m": 4.5,
    "aeb_margin_m": 2.0,
    "aeb_react_s": 0.50,
    "closing_min_mps": 0.3,
    "a_req_label_acc": 0.12,
    "a_req_label_aeb": 0.85,
    "cruise_v_mps": 12.0,
    "acc_speed_db_mps": 0.25,
    "acc_thr_gain": 0.11,
    "acc_thr_max": 0.50,
    "acc_thr_hold": 0.10,
    "acc_brake_min": 0.08,
    "acc_brake_max": 0.85,
    "acc_over_v_gain": 0.28,
    "cruise_standstill_v_mps": 0.8,
    "cruise_thr_standstill_min": 0.42,
    "cruise_thr_standstill_max": 0.72,
    "hold_brake": 0.22,
    "lat_ey_invalid_m": 3.0,
    "lat_c1_invalid": 0.40,
    "lat_ey_slow_m": 1.0,
    "traj_speed_floor_mps": 0.2,
}


def gf_clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def lane_usable(lane_valid: bool, e_y: float, c1: float) -> bool:
    p = CAL
    return lane_valid and abs(e_y) <= p["lat_ey_invalid_m"] and abs(c1) <= p["lat_c1_invalid"]


def plan_lat_weight(alat: float) -> float:
    p = CAL
    aa = abs(alat)
    if aa >= p["lat_aeb_m"]:
        return 0.0
    if aa <= p["lat_merge_m"]:
        return 1.0
    return gf_clamp(1.0 - (aa - p["lat_merge_m"]) / max(p["lat_aeb_m"] - p["lat_merge_m"], 0.1), 0.0, 1.0)


def plan_v_cap_vis(D_see: float) -> float:
    p = CAL
    a = max(p["aeb_decel_mps2"], 0.5)
    vc = math.sqrt(max(0.0, 2.0 * a * max(0.0, D_see - p["aeb_d_min_m"])))
    return min(vc, p["cruise_v_mps"])


def plan_vis_slew(raw: float, prev: float, alpha: float) -> float:
    if prev <= 0.0:
        return raw
    if raw < prev:
        return raw
    return prev + alpha * (raw - prev)


def plan_horizon(
    v: float,
    lane_valid: bool,
    e_y: float,
    c1: float,
    x_end: float,
    D_occ: float | None = None,
    D_fov: float | None = None,
    D_see_prev: float = 0.0,
    T_plan_prev: float = 0.0,
) -> tuple[float, float]:
    p = CAL
    if D_occ is None:
        D_occ = p["d_cal_cap_m"]
    if D_fov is None:
        D_fov = p["d_fov_conf_m"]
    D_vr = p["d_cal_cap_m"]
    if lane_usable(lane_valid, e_y, c1):
        if x_end > 0.5:
            D_vr = x_end
    else:
        D_vr = min(D_vr, p["d_see_lane_bad_m"])
    D_raw = min(D_fov, D_vr, D_occ, p["d_cal_cap_m"])
    D_see = plan_vis_slew(D_raw, D_see_prev, p.get("vis_up_alpha", 0.08))
    T_raw = min(p["t_base_s"], D_see / max(v, p["traj_speed_floor_mps"]))
    T_raw = max(T_raw, p["t_plan_min_s"])
    T_plan = plan_vis_slew(T_raw, T_plan_prev, p.get("vis_up_alpha", 0.08))
    return D_see, T_plan


def plan_obj_weight(lat: float, heading: float = 0.0, is_ped: float = 0.0) -> float:
    p = CAL
    w = plan_lat_weight(lat)
    if is_ped != 0.0 and abs(lat) < p["lat_aeb_m"]:
        w = max(w, 0.85)
    if lat * heading < -0.02:
        w = min(1.0, w + p.get("cutin_head_gain", 1.20) * min(abs(heading), 0.5))
    return w


def plan_v_at_s(
    s: float,
    v_ego: float,
    lead_valid: bool,
    d: float,
    rel: float,
    lat: float,
    D_see: float,
    lane_ok: bool,
) -> float:
    p = CAL
    v_cap = plan_v_cap_vis(D_see)
    if not lane_ok:
        return 0.0
    if s > D_see + 0.05:
        return 0.0
    vi = v_cap
    if (not lead_valid) or d > p["lon_max_d_m"]:
        return vi
    w = plan_obj_weight(lat, 0.0, 0.0)
    if w <= 0.0:
        return vi
    gap = d - s
    a = max(p["aeb_decel_mps2"], 0.5)
    if gap <= p["aeb_d_min_m"]:
        return 0.0 if w > 0.5 else vi
    vv = max(0.0, v_ego)
    v_obj = max(0.0, vv + rel)
    v_kin = math.sqrt(max(0.0, v_obj * v_obj + 2.0 * a * (gap - p["aeb_d_min_m"])))
    v_gap = max(0.0, (gap - p["acc_gap_min_m"]) / max(p["acc_time_gap_s"], 0.2))
    v_lim = min(v_kin, v_gap)
    return min(vi, v_lim * w + v_cap * (1.0 - w))


def lon_a_req(v: float, lead_valid: bool, d: float, rel: float, lat: float, w: float | None = None) -> float:
    p = CAL
    if w is None:
        w = plan_lat_weight(lat)
    if (not lead_valid) or w <= 0.0 or d > p["lon_max_d_m"]:
        return 0.0
    d_use = max(d, 0.05)
    a = max(p["aeb_decel_mps2"], 0.5)
    gap = max(d_use - p["aeb_d_min_m"], 0.2)
    vv = max(0.0, v)
    v_obj = max(0.0, vv + rel)
    a_req = 0.0
    if v_obj < 0.3:
        v_safe = math.sqrt(max(0.0, 2.0 * a * gap))
        if vv > v_safe:
            a_req = min(a, (vv * vv) / (2.0 * gap))
    else:
        v_safe = math.sqrt(v_obj * v_obj + 2.0 * a * gap)
        if vv > v_safe:
            a_req = min(a, (vv * vv - v_obj * v_obj) / (2.0 * gap))
    if d_use < p["aeb_d_min_m"]:
        a_req = a
    return a_req * w


def lon_exec(v: float, v_plan: float, a_req: float) -> dict:
    p = CAL
    v = max(0.0, v)
    v_plan = max(0.0, v_plan)
    a_max = max(p["aeb_decel_mps2"], 0.5)
    brk_req = gf_clamp(a_req / a_max, 0.0, 1.0)
    err = v_plan - v
    if brk_req >= p["a_req_label_aeb"]:
        return {"mode": "aeb", "throttle": 0.0, "brake": 1.0, "target_speed_mps": v_plan}
    if brk_req >= p["a_req_label_acc"]:
        return {
            "mode": "acc",
            "throttle": 0.0,
            "brake": gf_clamp(brk_req, p["acc_brake_min"], 1.0),
            "target_speed_mps": v_plan,
        }
    if v_plan < 0.4:
        return {
            "mode": "cruise",
            "throttle": 0.0,
            "brake": p["hold_brake"] if v > 0.4 else 0.0,
            "target_speed_mps": v_plan,
        }
    if v > v_plan + p["acc_speed_db_mps"]:
        return {
            "mode": "acc",
            "throttle": 0.0,
            "brake": gf_clamp((v - v_plan) * p["acc_over_v_gain"], p["acc_brake_min"], p["acc_brake_max"]),
            "target_speed_mps": v_plan,
        }
    if err >= p["acc_speed_db_mps"]:
        if v < p["cruise_standstill_v_mps"]:
            thr = gf_clamp(0.48 + err * 0.04, p["cruise_thr_standstill_min"], p["cruise_thr_standstill_max"])
        else:
            thr = gf_clamp(0.14 + err * p["acc_thr_gain"], 0.0, p["acc_thr_max"])
        return {"mode": "cruise", "throttle": thr, "brake": 0.0, "target_speed_mps": v_plan}
    return {"mode": "cruise", "throttle": p["acc_thr_hold"], "brake": 0.0, "target_speed_mps": v_plan}


def m_lon_acc_aeb(
    v: float,
    lead_valid: bool,
    d: float,
    rel: float,
    lead_lat_m: float = 0.0,
    e_y: float = 0.0,
    c1: float = 0.0,
    lane_valid: bool = True,
) -> dict:
    p = CAL
    v = max(0.0, v)
    D_fov = p["d_fov_conf_m"]
    D_occ = p["d_cal_cap_m"]
    if lead_valid:
        w = plan_obj_weight(lead_lat_m)
        if w >= 0.40 and w > 0.85:
            D_occ = min(D_occ, max(0.0, d - 0.5 * 4.5))
    D_see, _t = plan_horizon(v, lane_valid, e_y, c1, 1.0e6, D_occ, D_fov, 0.0, 0.0)
    lane_ok = lane_usable(lane_valid, e_y, c1)
    if abs(e_y) > p["lat_ey_slow_m"]:
        lane_ok = False
    v_plan = plan_v_at_s(0.0, v, lead_valid, d, rel, lead_lat_m, D_see, lane_ok)
    a_req = lon_a_req(v, lead_valid, d, rel, lead_lat_m)
    if D_see < 40.0:
        a_max = max(p["aeb_decel_mps2"], 0.5)
        a_req = min(a_max, a_req * 1.25)
    if not lane_ok:
        v_plan = 0.0
    return lon_exec(v, v_plan, a_req)


def test_empty_road_standstill_pulls() -> None:
    c = m_lon_acc_aeb(0.0, False, 0.0, 0.0)
    assert c["throttle"] >= 0.40
    assert c["brake"] == 0.0
    assert c["target_speed_mps"] >= 10.0


def test_inpath_close_full_brake() -> None:
    c = m_lon_acc_aeb(17.4, True, 20.1, -17.4, 0.0)
    assert c["brake"] >= 0.85
    assert c["throttle"] == 0.0


def test_far_adjacent_not_aeb() -> None:
    c = m_lon_acc_aeb(12.0, True, 66.0, 0.0, 11.0, 0.2, 0.0, True)
    assert c["brake"] < 0.5
    assert c["throttle"] > 0.0


def test_huge_ey_no_cruise_floor() -> None:
    c = m_lon_acc_aeb(0.3, True, 66.0, 0.0, 11.0, 28.3, 0.0, True)
    assert c["throttle"] == 0.0
    assert c["target_speed_mps"] == 0.0


def test_profile_slows_near_lead() -> None:
    D_see, _ = plan_horizon(12.0, True, 0.0, 0.0, 80.0)
    v0 = plan_v_at_s(0.0, 12.0, True, 40.0, -12.0, 0.0, D_see, True)
    v_near = plan_v_at_s(35.0, 12.0, True, 40.0, -12.0, 0.0, D_see, True)
    assert v_near < v0
    assert v_near < 6.0


def test_horizon_bad_lane_short() -> None:
    D_good, T_good = plan_horizon(12.0, True, 0.0, 0.0, 80.0)
    D_bad, T_bad = plan_horizon(12.0, True, 28.0, 0.0, 80.0)
    assert D_bad < D_good
    assert T_bad <= T_good


def test_cutin_lat_has_weight() -> None:
    assert plan_lat_weight(2.6) > 0.5
    c = m_lon_acc_aeb(3.9, True, 34.4, -3.9, -2.6)
    assert c["throttle"] >= 0.0


def test_overshoot_brakes() -> None:
    c = m_lon_acc_aeb(17.4, True, 50.8, -17.4, 0.0)
    assert c["throttle"] == 0.0
    assert c["brake"] > 0.1


def test_generate_lon_header() -> None:
    from pathlib import Path

    from gf_octavecoder.generate import generate_sku

    root = Path(__file__).resolve().parents[3]
    assert generate_sku(repo_root=root, sku="afc", force=True) == 0
    text = (root / "projects/afc/apps/planning/driving/oct_gen/m_lon_acc_aeb.hpp").read_text(
        encoding="utf-8"
    )
    assert "gf_octave_planning::m_lon_acc_aeb" in text
    assert "lon_exec" in text
    tick = (root / "projects/afc/apps/planning/driving/oct_gen/m_plan_tick.hpp").read_text(
        encoding="utf-8"
    )
    assert "gf_octave_planning::m_plan_tick" in tick
    assert "m_plan_tick_pack" not in tick
