from __future__ import annotations

"""Golden vectors for v4 lon: plan_v_at_s + lon_exec (not ACC/AEB FSM)."""

import math

CAL = {
    "lane_width_m": 3.50,
    "ego_width_m": 1.80,
    "pass_clear_m": 0.30,
    "obj_width_car_m": 1.80,
    "obj_width_truck_m": 2.55,
    "obj_width_ped_m": 0.60,
    "occ_overlap_min_m": 0.30,
    "cls_truck": 2.0,
    "cls_ped": 5.0,
    "cls_reg_stop": 16.0,
    "reg_stop_lat_m": 18.0,
    "reg_stop_margin_m": 3.0,
    "reg_stop_decel_mps2": 1.5,
    "reg_stop_late_mps2": 3.5,
    "reg_stop_behind_m": 8.0,
    "reg_stop_hold_m": 1.0,
    "peer_v_min_mps": 1.0,
    "peer_lat_max_m": 7.0,
    "peer_d_max_m": 35.0,
    "lat_aeb_m": 8.0,
    "lat_merge_m": 1.0,
    "lon_max_d_m": 80.0,
    "t_base_s": 10.0,
    "t_plan_min_s": 1.0,
    "d_cal_cap_m": 120.0,
    "see_fov_deg": 50.0,
    "d_fov_conf_m": 120.0,
    "d_see_lane_bad_m": 12.0,
    "vis_up_alpha": 0.08,
    "cutin_head_gain": 1.20,
    "cutin_approach_m": 1.50,
    "cutin_close_mps": 0.5,
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
    "lat_ey_invalid_m": 1.6,
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


def plan_d_fov(c0: float, c1: float, c2: float, c3: float, x_end: float) -> float:
    p = CAL
    D_fov = p["d_cal_cap_m"]
    if x_end > 0.5:
        D_fov = min(D_fov, x_end)
    half = 0.5 * p["see_fov_deg"] * math.pi / 180.0
    step = 2.0
    x = 2.0
    while x <= D_fov + 1e-6:
        y = c0 + c1 * x + c2 * x * x + c3 * x * x * x
        if abs(math.atan2(y, x)) > half:
            return x
        x += step
    return D_fov


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
        D_fov = p["d_cal_cap_m"]
    D_vr = p["d_cal_cap_m"]
    if lane_usable(lane_valid, e_y, c1):
        if x_end > 0.5:
            D_vr = x_end
    else:
        D_vr = min(D_vr, p["d_see_lane_bad_m"])
    D_raw = min(D_vr, D_occ, D_fov, p["d_cal_cap_m"])
    D_see = plan_vis_slew(D_raw, D_see_prev, p.get("vis_up_alpha", 0.08))
    T_raw = min(p["t_base_s"], D_see / max(v, p["traj_speed_floor_mps"]))
    T_raw = max(T_raw, p["t_plan_min_s"])
    T_plan = plan_vis_slew(T_raw, T_plan_prev, p.get("vis_up_alpha", 0.08))
    return D_see, T_plan


def plan_obj_width(cls: float, is_ped: float = 0.0) -> float:
    p = CAL
    if is_ped != 0.0 or cls == p["cls_ped"]:
        return p["obj_width_ped_m"]
    if cls == p["cls_truck"]:
        return p["obj_width_truck_m"]
    return p["obj_width_car_m"]


def plan_lane_occupy(
    c0: float, lat: float, len_m: float, cls: float, heading: float, is_ped: float = 0.0
) -> float:
    if plan_is_reg_stop(cls):
        return 0.0
    p = CAL
    W = p["lane_width_m"]
    wo = plan_obj_width(cls, is_ped)
    half = 0.5 * (wo * abs(math.cos(heading)) + max(len_m, 0.5) * abs(math.sin(heading)))
    y0, y1 = c0 - 0.5 * W, c0 + 0.5 * W
    return max(0.0, min(y1, lat + half) - max(y0, lat - half))


def plan_can_pass(occupy: float, cls: float = 1.0, is_ped: float = 0.0) -> bool:
    p = CAL
    if (is_ped != 0.0 or cls == p["cls_ped"]) and occupy > 1e-3:
        return False
    return (p["lane_width_m"] - occupy) >= (p["ego_width_m"] + p["pass_clear_m"])


def plan_is_reg_stop(cls: float) -> bool:
    return cls == CAL["cls_reg_stop"]


def plan_reg_stop(obj: list[list[float]], c0: float = 0.0) -> float:
    p = CAL
    s_stop = p["d_cal_cap_m"]
    hold = max(p["reg_stop_hold_m"], 0.2)
    behind = max(p["reg_stop_behind_m"], 0.0)
    for row in obj:
        d, _rel, lat, _ln, cls = row[0], row[1], row[2], row[3], row[4]
        if not plan_is_reg_stop(cls):
            continue
        if abs(lat - c0) > p["reg_stop_lat_m"]:
            continue
        if d < -behind or d > p["lon_max_d_m"]:
            continue
        s_line = d - p["reg_stop_margin_m"]
        if s_line <= 0.0:
            s_stop = min(s_stop, hold)
        else:
            s_stop = min(s_stop, s_line)
    return s_stop


def plan_v_reg(s: float, s_stop: float, v_ego: float = 0.0) -> float:
    p = CAL
    if s_stop <= 0.0 or s_stop >= p["d_cal_cap_m"] - 0.5:
        return 1.0e6
    hold = max(p["reg_stop_hold_m"], 0.2)
    gap = s_stop - s
    if gap <= hold:
        return 0.0
    a = max(p["reg_stop_decel_mps2"], 0.5)
    s_need = (max(v_ego, 0.0) ** 2) / (2.0 * a) + hold
    if gap < s_need:
        a = max(p["reg_stop_late_mps2"], a)
    return math.sqrt(max(0.0, 2.0 * a * (gap - hold)))


def lon_a_req_stop(v: float, s_stop: float) -> float:
    p = CAL
    if s_stop <= 0.0 or s_stop >= p["d_cal_cap_m"] - 0.5:
        return 0.0
    hold = max(p["reg_stop_hold_m"], 0.2)
    a_c = max(p["reg_stop_decel_mps2"], 0.5)
    a_late = max(p["reg_stop_late_mps2"], a_c)
    vv = max(0.0, v)
    if s_stop <= hold:
        return a_late if vv > 0.05 else 0.0
    s_need = (vv * vv) / (2.0 * a_c) + hold
    if s_stop > s_need + 0.05:
        return 0.0
    a_kin = (vv * vv) / (2.0 * max(s_stop - hold, 0.2))
    return min(a_late, max(0.0, a_kin))


def plan_v_peers(s: float, v_ego: float, obj: list[list[float]], c0: float = 0.0) -> float:
    p = CAL
    vi = 1.0e6
    vv = max(0.0, v_ego)
    half_w = 0.5 * p["lane_width_m"]
    for row in obj:
        d, rel, lat, ln, cls = row[0], row[1], row[2], row[3], row[4]
        hdg = row[5] if len(row) > 5 else 0.0
        ped = row[6] if len(row) > 6 else 0.0
        if plan_is_reg_stop(cls):
            continue
        if d <= s or d > p["peer_d_max_m"]:
            continue
        alat = abs(lat - c0)
        if alat <= half_w or alat > p["peer_lat_max_m"]:
            continue
        w = plan_obj_weight(lat, hdg, ped, ln, cls, c0, rel)
        if w > 0.5:
            continue
        v_obj = max(0.0, vv + rel)
        if v_obj < p["peer_v_min_mps"]:
            continue
        vi = min(vi, v_obj)
    return vi


def plan_obj_weight(
    lat: float,
    heading: float = 0.0,
    is_ped: float = 0.0,
    len_m: float = 4.5,
    cls: float = 1.0,
    c0: float = 0.0,
    rel: float = 0.0,
) -> float:
    if plan_is_reg_stop(cls):
        return 0.0
    p = CAL
    occupy = plan_lane_occupy(c0, lat, len_m, cls, heading, is_ped)
    w = 0.0 if plan_can_pass(occupy, cls, is_ped) else 1.0
    wo = plan_obj_width(cls, is_ped)
    half = 0.5 * (wo * abs(math.cos(heading)) + max(len_m, 0.5) * abs(math.sin(heading)))
    gap = (abs(lat - c0) - half) - 0.5 * p["lane_width_m"]
    closing = rel < -p.get("cutin_close_mps", 0.5)
    if gap < p.get("cutin_approach_m", 1.50) and lat * heading < -0.02 and closing:
        w = min(1.0, max(w, 0.55) + p.get("cutin_head_gain", 1.20) * min(abs(heading), 0.5))
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
    w = plan_obj_weight(lat, 0.0, 0.0, 4.5, 1.0, 0.0, rel)
    if w <= 0.0:
        return vi
    if rel > p.get("cutin_close_mps", 0.5) and w < 1.0:
        return vi
    gap = d - s
    a = max(p["aeb_decel_mps2"], 0.5)
    if gap <= p["aeb_d_min_m"]:
        return 0.0 if w > 0.5 else vi
    vv = max(0.0, v_ego)
    v_obj = max(0.0, vv + rel)
    v_kin = math.sqrt(max(0.0, v_obj * v_obj + 2.0 * a * (gap - p["aeb_d_min_m"])))
    desired = p["acc_gap_min_m"] + p["acc_time_gap_s"] * max(v_obj, 0.5)
    v_follow = v_obj + max(-4.0, min(3.0, 0.4 * (gap - desired)))
    v_lim = v_kin
    if w >= 1.0 or rel <= 0.0:
        v_lim = min(v_kin, max(0.0, v_follow))
    return min(vi, v_lim * w + v_cap * (1.0 - w))


def plan_v_at_s_n(
    s: float,
    v_ego: float,
    obj: list[list[float]],
    D_see: float,
    lane_ok: bool,
    c0: float = 0.0,
    s_stop: float | None = None,
    v_sign_max: float = 1.0e6,
    v_sign_min: float = 0.0,
) -> float:
    p = CAL
    v_cap = plan_v_cap_vis(D_see)
    if not lane_ok:
        return 0.0
    if s > D_see + 0.05:
        return 0.0
    vi = v_cap
    if s_stop is None:
        s_stop = plan_reg_stop(obj, c0)
    vi = min(vi, v_sign_max)
    if v_sign_min > 0.5 and s_stop >= p["d_cal_cap_m"] - 0.5:
        vi = max(vi, min(v_sign_min, v_sign_max, v_cap))
    vi = min(vi, plan_v_reg(s, s_stop, v_ego))
    vi = min(vi, plan_v_peers(s, v_ego, obj, c0))
    a = max(p["aeb_decel_mps2"], 0.5)
    vv = max(0.0, v_ego)
    for row in obj:
        d, rel, lat, ln, cls = row[0], row[1], row[2], row[3], row[4]
        hdg = row[5] if len(row) > 5 else 0.0
        ped = row[6] if len(row) > 6 else 0.0
        if d > p["lon_max_d_m"]:
            continue
        w = plan_obj_weight(lat, hdg, ped, ln, cls, c0, rel)
        if w <= 0.0:
            continue
        if rel > p.get("cutin_close_mps", 0.5) and w < 1.0:
            continue
        gap = d - s
        if gap <= p["aeb_d_min_m"]:
            if w > 0.5:
                vi = 0.0
            continue
        v_obj = max(0.0, vv + rel)
        v_kin = math.sqrt(max(0.0, v_obj * v_obj + 2.0 * a * (gap - p["aeb_d_min_m"])))
        desired = p["acc_gap_min_m"] + p["acc_time_gap_s"] * max(v_obj, 0.5)
        v_follow = v_obj + max(-4.0, min(3.0, 0.4 * (gap - desired)))
        v_lim = v_kin
        if w >= 1.0 or rel <= 0.0:
            v_lim = min(v_kin, max(0.0, v_follow))
        vi = min(vi, v_lim * w + v_cap * (1.0 - w))
    return vi


def lon_a_req(v: float, lead_valid: bool, d: float, rel: float, lat: float, w: float | None = None) -> float:
    p = CAL
    if w is None:
        w = plan_obj_weight(lat)
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


def lon_a_req_n(v: float, obj: list[list[float]], c0: float = 0.0) -> float:
    a_req = 0.0
    for row in obj:
        d, rel, lat, ln, cls = row[0], row[1], row[2], row[3], row[4]
        hdg = row[5] if len(row) > 5 else 0.0
        ped = row[6] if len(row) > 6 else 0.0
        if plan_is_reg_stop(cls):
            continue
        w = plan_obj_weight(lat, hdg, ped, ln, cls, c0, rel)
        a_req = max(a_req, lon_a_req(v, True, d, rel, lat, w))
    return a_req


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
        occupy = plan_lane_occupy(0.0, lead_lat_m, 4.5, 1.0, 0.0, 0.0)
        if occupy >= p["occ_overlap_min_m"]:
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


def test_horizon_c1_alone_does_not_cut_d_see() -> None:
    D_straight, _ = plan_horizon(12.0, True, 0.0, 0.0, 120.0)
    D_same_vr, _ = plan_horizon(12.0, True, 0.0, 0.20, 120.0)
    D_short_vr, _ = plan_horizon(12.0, True, 0.0, 0.0, 40.0)
    assert D_straight >= 80.0
    assert abs(D_same_vr - D_straight) < 1e-3
    assert 39.0 <= D_short_vr <= 40.0


def test_horizon_in_lane_occ_cuts_from_mark_vr() -> None:
    D_see, _ = plan_horizon(12.0, True, 0.0, 0.0, 120.0, D_occ=17.0, D_see_prev=120.0)
    assert abs(D_see - 17.0) < 1e-6


def test_horizon_adj_occ_does_not_cut() -> None:
    D_see, _ = plan_horizon(12.0, True, 0.0, 0.0, 120.0, D_occ=120.0, D_see_prev=120.0)
    assert abs(D_see - 120.0) < 1e-6


def test_d_fov_straight_keeps_cap() -> None:
    assert abs(plan_d_fov(0.0, 0.0, 0.0, 0.0, 120.0) - 120.0) < 1e-6


def test_d_fov_curve_bearing_cuts() -> None:
    D_fov = plan_d_fov(0.0, 0.0, 0.02, 0.0, 120.0)
    assert 10.0 <= D_fov <= 50.0
    D_see, _ = plan_horizon(12.0, True, 0.0, 0.0, 120.0, D_fov=D_fov)
    assert abs(D_see - D_fov) < 1e-6


def test_d_fov_is_bearing_not_heading() -> None:
    # Constant C1: road heading is constant; bearing = atan(C1). 0.20 rad ≈ 11° < 25°.
    assert abs(plan_d_fov(0.0, 0.20, 0.0, 0.0, 120.0) - 120.0) < 1e-6


def test_cutin_lat_has_weight() -> None:
    assert plan_obj_weight(0.0) >= 0.99
    assert plan_obj_weight(3.5) < 0.1
    c = m_lon_acc_aeb(3.9, True, 34.4, -3.9, -2.6)
    assert c["throttle"] >= 0.0


def test_reg_stop_past_line_not_hidden_by_d_see() -> None:
    cap = CAL["d_cal_cap_m"]
    hold = CAL["reg_stop_hold_m"]
    # Packed light, already past the planned line — hold, do not release.
    past = [[2.0, 0.0, 6.0, 1.0, 16.0, 0.0, 0.0]]
    assert abs(plan_reg_stop(past) - hold) < 1e-6
    # Light a few metres behind ego still holds until pack drops.
    rear = [[-3.0, 0.0, 6.0, 1.0, 16.0, 0.0, 0.0]]
    assert abs(plan_reg_stop(rear) - hold) < 1e-6
    gone = [[-9.0, 0.0, 6.0, 1.0, 16.0, 0.0, 0.0]]
    assert plan_reg_stop(gone) == cap
    # Line still ahead: keep it even if current v cannot comfort-stop.
    mid = [[11.0, 0.0, 8.0, 1.0, 16.0, 0.0, 0.0]]
    assert abs(plan_reg_stop(mid) - 8.0) < 1e-6
    # Known TSR is not dropped because a lead cut D_see short of the pole.
    behind = [[35.0, 0.0, 8.0, 1.0, 16.0, 0.0, 0.0]]
    assert abs(plan_reg_stop(behind) - 32.0) < 1e-6
    far = [[40.0, 0.0, 8.0, 1.0, 16.0, 0.0, 0.0]]
    assert abs(plan_reg_stop(far) - 37.0) < 1e-6
    hold_row = [[8.0, 0.0, 6.0, 1.0, 16.0, 0.0, 0.0]]
    assert abs(plan_reg_stop(hold_row) - 5.0) < 1e-6


def test_reg_stop_roadside_light_cuts_v_not_occ() -> None:
    light = [[35.0, 0.0, 8.5, 1.0, 16.0, 0.0, 0.0]]
    s_stop = plan_reg_stop(light)
    assert abs(s_stop - 32.0) < 1e-6
    assert plan_v_reg(0.0, s_stop, 0.0) < 12.0
    assert plan_v_reg(32.0, s_stop, 12.0) == 0.0
    # Roadside car still passable; a stop class on the centerline is not occupy.
    assert plan_obj_weight(8.5, 0.0, 0.0, 1.0, 1.0) < 0.1
    assert plan_lane_occupy(0.0, 0.0, 1.0, 16.0, 0.0) == 0.0
    assert plan_lane_occupy(0.0, 0.0, 1.0, 1.0, 0.0) > 1.0
    assert plan_obj_weight(0.0, 0.0, 0.0, 1.0, 16.0) < 0.1
    v_plan = plan_v_at_s_n(0.0, 12.0, light, 120.0, True)
    assert abs(v_plan - min(12.0, plan_v_reg(0.0, s_stop, 12.0))) < 1e-4
    # Occupy a_req still skips the light; late a_req_stop is separate.
    assert lon_a_req_n(12.0, light) == 0.0
    assert lon_a_req_stop(12.0, 32.0) > 0.0
    assert lon_a_req_stop(12.0, 77.0) == 0.0


def test_v_reg_hold_not_aeb_gap() -> None:
    s_stop = 32.0
    hold = CAL["reg_stop_hold_m"]
    # Inside hold → 0. AEB d_min is unrelated.
    assert plan_v_reg(s_stop - hold, s_stop) == 0.0
    assert plan_v_reg(s_stop - hold + 0.5, s_stop) == 0.0
    # Just outside hold: kinematics may still allow motion.
    assert plan_v_reg(s_stop - hold - 0.5, s_stop) > 0.0
    v0 = plan_v_reg(0.0, s_stop)
    # Kinematics-only (no follow time-gap): higher than old min(v_kin, v_time).
    assert 8.0 < v0 < 20.0


def test_v_reg_no_time_gap_crawl() -> None:
    # Near line: hold kills crawl; never use (gap-hold)/acc_time_gap.
    assert plan_v_reg(0.0, 0.8, 0.18) == 0.0
    assert plan_v_reg(0.0, 1.0, 2.22) == 0.0
    assert lon_a_req_stop(2.22, 1.0) == CAL["reg_stop_late_mps2"]
    assert lon_a_req_stop(0.0, 0.8) == 0.0
    # Farther than hold: kinematics, not time-gap ~0.76 at 2.3 m.
    v_far = plan_v_reg(0.0, 2.3, 0.18)
    assert v_far > 1.0  # not the old ~0.76 crawl cap
    assert v_far == math.sqrt(max(0.0, 2.0 * 1.5 * (2.3 - 1.0)))


def test_light_outranks_runner_past_line() -> None:
    light = [35.0, 0.0, 8.0, 1.0, 16.0, 0.0, 0.0]
    runner = [50.0, 0.0, 0.0, 4.5, 1.0, 0.0, 0.0]
    obj = [runner, light]
    s_stop = plan_reg_stop(obj)
    assert abs(s_stop - 32.0) < 1e-6
    v_plan = plan_v_at_s_n(0.0, 12.0, obj, 120.0, True)
    assert abs(v_plan - min(12.0, plan_v_reg(0.0, s_stop, 12.0))) < 1e-4
    # Line is not a_req; occupy of the far runner is unchanged.
    assert lon_a_req_n(12.0, obj) == lon_a_req_n(12.0, [runner])


def test_peer_flow_matches_not_occupy() -> None:
    peer = [[30.0, -4.0, 3.5, 4.5, 1.0, 0.0, 0.0]]
    assert plan_obj_weight(3.5) < 0.1
    assert abs(plan_v_peers(0.0, 12.0, peer) - 8.0) < 1e-6
    v_plan = plan_v_at_s_n(0.0, 12.0, peer, 120.0, True)
    assert abs(v_plan - 8.0) < 1e-4
    parked = [[30.0, -12.0, 3.5, 4.5, 1.0, 0.0, 0.0]]
    assert plan_v_peers(0.0, 12.0, parked) > 1.0e5
    # Foxglove turtle: adjacent at ~48 m, v_obj≈1.7 — must not set cruise.
    far = [[48.2, -0.28, -3.50, 4.5, 1.0, 0.0, 0.0]]
    assert plan_v_peers(0.0, 2.0, far) > 1.0e5
    assert plan_v_at_s_n(0.0, 2.0, far, 120.0, True) >= 11.5


def test_in_lane_pass_not_stop() -> None:
    # W=3.5, We=1.8, clear=0.3; ~0.5 m occupy still passable.
    occ = plan_lane_occupy(0.0, 2.15, 4.5, 1.0, 0.0)
    assert 0.4 < occ < 0.7
    assert plan_can_pass(occ)
    assert plan_obj_weight(2.15) < 0.1
    # Centered car blocks.
    assert plan_obj_weight(0.0) >= 0.99
    # Adjacent parallel car: pass.
    assert plan_obj_weight(3.5) < 0.1
    # Ped on lane: no squeeze.
    assert plan_obj_weight(0.8, 0.0, 1.0, 0.8, 5.0) >= 0.99
    # Off-lane CIPV (this log: lat≈-10) + heading toward ego must not raise w.
    assert plan_obj_weight(-10.3, 0.4, 0.0, 4.5, 1.0) < 0.1


def test_fleeing_neighbor_does_not_cutin_gap() -> None:
    # Foxglove turtle: lat≈3.73, rel=+14, inward heading — was w≥0.55 + v_gap≈10.5.
    flee = [[23.9, 14.4, 3.73, 4.5, 1.0, -0.2, 0.0]]
    assert plan_obj_weight(3.73, -0.2, 0.0, 4.5, 1.0, 0.0, 14.4) < 0.1
    v_plan = plan_v_at_s_n(0.0, 5.36, flee, 120.0, True)
    assert v_plan >= 11.5


def test_closing_cutin_still_has_weight() -> None:
    assert plan_obj_weight(2.2, -0.3, 0.0, 4.5, 1.0, 0.0, -2.0) >= 0.55
    assert plan_obj_weight(2.2, -0.3, 0.0, 4.5, 1.0, 0.0, 2.0) < 0.1


def test_late_reg_stop_requests_brake() -> None:
    # 12 m/s comfort needs ~49 m; 20 m remaining is late.
    assert lon_a_req_stop(12.0, 20.0) > 1.0
    assert plan_v_reg(0.0, 20.0, 12.0) < 12.0
    assert plan_v_reg(0.0, 20.0, 12.0) > plan_v_reg(0.0, 20.0, 0.0)
    past = [[1.5, 0.0, 6.0, 1.0, 16.0, 0.0, 0.0]]
    assert abs(plan_v_at_s_n(0.0, 12.0, past, 120.0, True)) < 1e-6
    assert lon_a_req_stop(12.0, plan_reg_stop(past)) == CAL["reg_stop_late_mps2"]


def test_sign_speed_limits_not_vis_cap() -> None:
    # 50 kph max ≈ 13.89 m/s; empty road vis cap is 12 → min still 12 without sign.
    empty: list[list[float]] = []
    assert abs(plan_v_at_s_n(0.0, 12.0, empty, 120.0, True) - 12.0) < 1e-4
    # 40 kph max ≈ 11.11 → caps below cruise.
    v40 = 40.0 / 3.6
    assert abs(plan_v_at_s_n(0.0, 12.0, empty, 120.0, True, v_sign_max=v40) - v40) < 1e-4
    # Min 30 kph with vis 12: floor only if min < vis; 30 kph ≈ 8.33 → raise above? Wait
    # vis cap 12, min 8.33 → max(12 after max, min 8.33) stays 12. Use low vis via short D.
    # With D_see large, v_cap=12; min=10 kph≈2.78 should not change.
    # Use min=50 kph≈13.89 with v_cap=12 → floor min(min,v_cap)=12 (no raise above vis).
    v50 = 50.0 / 3.6
    assert abs(plan_v_at_s_n(0.0, 12.0, empty, 120.0, True, v_sign_min=v50) - 12.0) < 1e-4
    # Max 30 + min 20: cruise at max.
    v30 = 30.0 / 3.6
    v20 = 20.0 / 3.6
    assert (
        abs(plan_v_at_s_n(0.0, 12.0, empty, 120.0, True, v_sign_max=v30, v_sign_min=v20) - v30)
        < 1e-4
    )
    # Stop-line active: min floor must not fight stop (s_stop far from cap).
    light = [[32.0, 0.0, 0.5, 1.0, 16.0, 0.0, 0.0]]
    s_stop = plan_reg_stop(light)
    v_with_min = plan_v_at_s_n(
        0.0, 12.0, light, 120.0, True, s_stop=s_stop, v_sign_min=v50
    )
    v_no_min = plan_v_at_s_n(0.0, 12.0, light, 120.0, True, s_stop=s_stop)
    assert abs(v_with_min - v_no_min) < 1e-4


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
    assert "v_sign_max" in tick
    assert "v_sign_min" in tick
