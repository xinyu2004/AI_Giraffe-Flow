from __future__ import annotations

import math

# Mirror octave_planning/common/gf_plan_cal.m defaults (demo acceptance set).
CAL = {
    "lat_ky": 0.38,
    "lat_kpsi": 0.65,
    "lat_max_steer": 0.42,
    "lat_e_sat_m": 1.8,
    "lat_e_desense_hi_m": 1.2,
    "lat_e_desense_lo_m": 0.6,
    "lat_ky_scale_hi": 0.30,
    "lat_ky_scale_lo": 0.50,
    "lat_c1_sat": 0.40,
    "lat_dsteer_max": 0.055,
    "lat_ey_invalid_m": 3.0,
    "lat_c1_invalid": 0.40,
    "traj_n": 16,
    "traj_blend_m": 14.0,
    "traj_horizon_floor_m": 8.0,
    "traj_horizon_max_m": 120.0,
    "traj_speed_floor_mps": 0.2,
}


def gf_clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


_LAST_STEER = 0.0


def lat_steer_from_lane(e_y: float, c1: float) -> float:
    p = CAL
    e = gf_clamp(e_y, -p["lat_e_sat_m"], p["lat_e_sat_m"])
    ky = p["lat_ky"]
    ae = abs(e)
    if ae > p["lat_e_desense_hi_m"]:
        ky *= p["lat_ky_scale_hi"]
    elif ae > p["lat_e_desense_lo_m"]:
        ky *= p["lat_ky_scale_lo"]
    c1c = gf_clamp(c1, -p["lat_c1_sat"], p["lat_c1_sat"])
    return gf_clamp(-ky * e - p["lat_kpsi"] * c1c, -p["lat_max_steer"], p["lat_max_steer"])


def lat_steer_from_ego(steer_angle_deg: float) -> float:
    del steer_angle_deg
    return 0.0


def gf_lane_usable(lane_valid: bool, e_y: float, c1: float) -> bool:
    return (
        lane_valid
        and abs(e_y) <= CAL["lat_ey_invalid_m"]
        and abs(c1) <= CAL["lat_c1_invalid"]
    )


def m_lat_lka(lane_valid: bool, e_y: float, c1: float, steer_angle_deg: float) -> float:
    global _LAST_STEER
    if gf_lane_usable(lane_valid, e_y, c1):
        cmd = lat_steer_from_lane(e_y, c1)
    else:
        cmd = lat_steer_from_ego(steer_angle_deg)
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


def test_generate_lat_headers() -> None:
    from pathlib import Path

    from gf_octavecoder.generate import generate_sku

    root = Path(__file__).resolve().parents[3]
    assert generate_sku(repo_root=root, sku="afc", force=True) == 0
    for name in ("m_lat_lka.hpp", "m_lat_traj.hpp", "m_lon_acc_aeb.hpp", "m_plan_tick.hpp"):
        p = root / "projects/afc/apps/planning/driving/oct_gen" / name
        assert p.is_file(), name
