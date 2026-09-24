from __future__ import annotations

import math

# Mirror octave_planning/common/gf_plan_cal.m defaults (demo acceptance set).
CAL = {
    "lat_ky": 0.38,
    "lat_kpsi": 0.65,
    "lc_reg_k": 1.0,
    "cruise_v_mps": 25.0,
    "lat_max_steer": 0.42,
    "lat_e_sat_m": 1.8,
    "lat_e_desense_hi_m": 1.2,
    "lat_e_desense_lo_m": 0.6,
    "lat_ky_scale_hi": 0.30,
    "lat_ky_scale_lo": 0.50,
    "lat_c1_sat": 0.40,
    "lat_dsteer_max": 0.055,
    "wheelbase_m": 2.70,
    "steer_max_deg": 70.0,
    "lat_ey_invalid_m": 1.6,
    "host_width_min_m": 2.50,
    "host_width_max_m": 5.50,
    "host_inside_m": 0.25,
    "traj_n": 16,
    "traj_blend_m": 14.0,
    "traj_horizon_floor_m": 8.0,
    "traj_horizon_max_m": 120.0,
    "traj_speed_floor_mps": 0.2,
    "lane_width_m": 3.50,
    "d_lc_min_m": 40.0,
    "t_lc_min_s": 6.0,
    "d_lc_rear_min_m": 2.0,
}


def gf_clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def steer_rad_to_plant(rad: float) -> float:
    full = CAL["steer_max_deg"] * math.pi / 180.0
    return gf_clamp(rad / max(full, 1.0e-3), -1.0, 1.0)


def steer_deg_to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


_LAST_STEER = 0.0
_LAST_FOLLOW = 0.0


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


def lat_steer_from_lane(e_y: float, c1: float) -> float:
    return gf_lat_host_delta(True, e_y, c1, 0.0, 0.0, CAL["cruise_v_mps"])


def lat_steer_from_ego(steer_angle_deg: float) -> float:
    del steer_angle_deg
    return 0.0


def plan_host_pair_ok(lc0: float, rc0: float) -> bool:
    w = lc0 - rc0
    if w < CAL["host_width_min_m"] or w > CAL["host_width_max_m"]:
        return False
    inside = max(CAL["host_inside_m"], 0.05)
    if lc0 < inside or rc0 > -inside:
        return False
    return True


def plan_host_pair_geom(lc0: float, rc0: float) -> bool:
    w = lc0 - rc0
    return CAL["host_width_min_m"] <= w <= CAL["host_width_max_m"]


def gf_lane_usable(lane_valid: bool, e_y: float, c1: float) -> bool:
    del c1
    return bool(lane_valid) and abs(e_y) <= CAL["lat_ey_invalid_m"]


def m_lat_lka(lane_valid: bool, e_y: float, c1: float, steer_angle_deg: float) -> float:
    global _LAST_STEER
    v = CAL["cruise_v_mps"]
    cmd = gf_lat_host_delta(lane_valid, e_y, c1, 0.0, 0.0, v)
    ds = gf_clamp(cmd - _LAST_STEER, -CAL["lat_dsteer_max"], CAL["lat_dsteer_max"])
    _LAST_STEER = _LAST_STEER + ds
    return _LAST_STEER


def lat_poly_y(x: float, c0: float, c1: float, c2: float, c3: float) -> float:
    return c0 + c1 * x + c2 * x * x + c3 * x * x * x


def m_lat_traj(
    speed_mps: float,
    D_see: float,
    T_plan: float,
    lane_valid: bool,
    c0: float,
    c1: float,
    c2: float,
    c3: float,
    x_end: float,
) -> tuple[list[float], list[float], float]:
    p = CAL
    n = p["traj_n"]
    blend = p["traj_blend_m"]
    use_lane = gf_lane_usable(lane_valid, c0, c1)
    v = max(speed_mps, p["traj_speed_floor_mps"])
    D_plan = min(D_see, v * T_plan, p["traj_horizon_max_m"])
    if use_lane and x_end > 0.5:
        D_plan = min(D_plan, x_end)
    D_plan = min(D_plan, D_see)
    D_plan = max(D_plan, p["traj_horizon_floor_m"])
    if D_plan > D_see:
        D_plan = max(D_see, 1.0)
    horizon = D_plan
    ds = horizon / (n - 1)
    xs, ys = [], []
    for i in range(n):
        x = ds * i
        xs.append(x)
        if use_lane:
            alpha = 1.0 - math.exp(-x / blend)
            ys.append(alpha * lat_poly_y(x, c0, c1, c2, c3))
        else:
            ys.append(0.0)
    return xs, ys, horizon


def test_host_pair_straddles_ego() -> None:
    assert plan_host_pair_ok(1.75, -1.75)
    assert plan_host_pair_ok(2.2, -1.3)
    # Foxglove wall case: both lines left of ego (right C0 still +).
    assert not plan_host_pair_ok(4.12, 0.59)
    assert not plan_host_pair_ok(-2.88, -5.87)


def test_host_pair_geom_on_the_line() -> None:
    # Sitting on the left mark: LKA straddle fails, LC pose still has a pair.
    assert not plan_host_pair_ok(0.19, -3.34)
    assert plan_host_pair_geom(0.19, -3.34)
    assert plan_host_pair_geom(1.75, -1.75)
    assert not plan_host_pair_geom(0.4, 0.1)


def test_lka_lane_left_error_steers_left() -> None:
    global _LAST_STEER
    _LAST_STEER = 0.0
    s = m_lat_lka(True, 0.5, 0.0, 0.0)
    assert s < 0.0


def test_lka_fallback_ego() -> None:
    global _LAST_STEER
    _LAST_STEER = 0.0
    s = m_lat_lka(False, 0.0, 0.0, 25.0)
    assert abs(s) < 1e-6


def test_lka_large_ey_gain_reduced() -> None:
    global _LAST_STEER
    _LAST_STEER = 0.0
    # Rate-limited: need several ticks to approach max
    s_big = 0.0
    for _ in range(20):
        s_big = abs(m_lat_lka(True, 1.5, 0.0, 0.0))
    assert s_big <= CAL["lat_max_steer"] + 1e-6


def test_lka_absurd_ey_commands_zero() -> None:
    global _LAST_STEER
    _LAST_STEER = 0.2
    s = m_lat_lka(True, 28.3, 0.0, 0.0)
    # rate-limited toward 0, not toward max steer
    assert s < 0.2
    for _ in range(20):
        s = m_lat_lka(True, 28.3, 0.0, 0.0)
    assert abs(s) < 1e-6


def test_traj_absurd_c0_straight() -> None:
    _xs, ys, _h = m_lat_traj(10.0, 80.0, 10.0, True, 28.3, 0.0, 0.0, 0.0, 60.0)
    assert all(abs(y) < 1e-9 for y in ys)


def test_curve_heading_still_lka_and_poly() -> None:
    global _LAST_STEER
    _LAST_STEER = 0.0
    s = m_lat_lka(True, 0.2, 0.55, 0.0)
    assert s < 0.0
    _xs, ys, _h = m_lat_traj(10.0, 80.0, 10.0, True, 0.2, 0.55, -0.002, 0.0, 60.0)
    assert ys[-1] > 0.5


def test_lka_dsteer_rate_limited() -> None:
    global _LAST_STEER
    _LAST_STEER = 0.0
    s1 = abs(m_lat_lka(True, 1.5, 0.0, 0.0))
    assert s1 <= CAL["lat_dsteer_max"] + 1e-6


def test_traj_points_count_and_blend() -> None:
    xs, ys, _h = m_lat_traj(10.0, 80.0, 10.0, True, 0.5, 0.0, 0.0, 0.0, 60.0)
    assert len(xs) == 16 and len(ys) == 16
    assert xs[0] == 0.0
    assert abs(ys[0]) < 1e-9
    assert ys[-1] > 0.0


def m_lat_follow(delta_ff: float, steer_angle_deg: float = 0.0) -> float:
    del steer_angle_deg
    global _LAST_FOLLOW
    p = CAL
    cmd = gf_clamp(delta_ff, -p["lat_max_steer"], p["lat_max_steer"])
    ds = gf_clamp(cmd - _LAST_FOLLOW, -p["lat_dsteer_max"], p["lat_dsteer_max"])
    _LAST_FOLLOW = _LAST_FOLLOW + ds
    return _LAST_FOLLOW


def test_steer_rad_to_plant_matches_cal() -> None:
    # 0.034 rad ≈ 1.95° wheel; plant = rad / (70° in rad) ≈ 0.0278
    u = steer_rad_to_plant(0.034)
    assert abs(u - 0.034 / (70.0 * math.pi / 180.0)) < 1e-6
    assert abs(u - 0.0278) < 5e-4


def test_steer_rad_to_plant_sat() -> None:
    assert steer_rad_to_plant(2.0) == 1.0
    assert steer_rad_to_plant(-2.0) == -1.0


def test_steer_deg_to_rad_roundtrip_plant() -> None:
    rad = 0.034
    plant = steer_rad_to_plant(rad)
    ego_deg = plant * CAL["steer_max_deg"]
    assert abs(steer_deg_to_rad(ego_deg) - rad) < 1e-6


def test_follow_zero_plan_stays_zero() -> None:
    global _LAST_FOLLOW
    _LAST_FOLLOW = 0.0
    s = m_lat_follow(0.0)
    assert abs(s) < 1e-6


def test_follow_executes_plan_delta() -> None:
    global _LAST_FOLLOW
    _LAST_FOLLOW = 0.0
    s = 0.0
    for _ in range(8):
        s = m_lat_follow(-0.03)
    assert s < 0.0
    assert abs(s + 0.03) < 1e-6


def test_follow_enter_snaps_off_lka_last() -> None:
    # Hold enter sets last = δ_ff. First cmd is the S, not leftover LKA.
    global _LAST_FOLLOW
    _LAST_FOLLOW = 0.30
    dff = 0.03
    _LAST_FOLLOW = dff
    s = m_lat_follow(dff)
    assert abs(s - dff) < 1e-6


def test_generate_lat_headers() -> None:
    from pathlib import Path

    from gf_octavecoder.generate import generate_sku

    root = Path(__file__).resolve().parents[3]
    assert generate_sku(repo_root=root, sku="afc", force=True) == 0
    for name in (
        "m_lat_lka.hpp",
        "m_lat_follow.hpp",
        "m_lat_traj.hpp",
        "m_lc_path.hpp",
        "m_lon_acc_aeb.hpp",
        "m_plan_tick.hpp",
    ):
        p = root / "projects/afc/apps/planning/driving/oct_gen" / name
        assert p.is_file(), name
    follow = (root / "projects/afc/apps/planning/driving/oct_gen/m_lat_follow.hpp").read_text(
        encoding="utf-8"
    )
    assert "m_lat_follow" in follow
    path = (root / "projects/afc/apps/planning/driving/oct_gen/m_lc_path.hpp").read_text(
        encoding="utf-8"
    )
    assert "m_lc_path" in path
    tick = (root / "projects/afc/apps/planning/driving/oct_gen/m_plan_tick.hpp").read_text(
        encoding="utf-8"
    )
    assert "lc_side" in tick
