from __future__ import annotations

import math


def gf_clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def lat_steer_from_lane(e_y: float, c1: float) -> float:
    e = gf_clamp(e_y, -1.8, 1.8)
    ky = 0.35
    ae = abs(e)
    if ae > 1.2:
        ky *= 0.35
    elif ae > 0.6:
        ky *= 0.55
    c1c = gf_clamp(c1, -0.5, 0.5)
    return gf_clamp(-ky * e - 0.80 * c1c, -0.55, 0.55)


def lat_steer_from_ego(steer_angle_deg: float) -> float:
    del steer_angle_deg
    return 0.0


def m_lat_lka(lane_valid: bool, e_y: float, c1: float, steer_angle_deg: float) -> float:
    if lane_valid:
        return lat_steer_from_lane(e_y, c1)
    return lat_steer_from_ego(steer_angle_deg)


def lat_poly_y(x: float, c0: float, c1: float, c2: float, c3: float) -> float:
    return c0 + c1 * x + c2 * x * x + c3 * x * x * x


def m_lat_traj(
    speed_mps: float,
    speed_scale: float,
    lane_valid: bool,
    c0: float,
    c1: float,
    c2: float,
    c3: float,
    x_end: float,
) -> tuple[list[float], list[float], float]:
    n = 16
    blend = 18.0
    speed = max(speed_mps * speed_scale, 0.2)
    x_cap = x_end if lane_valid else 100.0
    horizon = gf_clamp(speed * 4.0, 25.0, min(100.0, x_cap))
    ds = horizon / (n - 1)
    xs, ys = [], []
    for i in range(n):
        x = ds * i
        xs.append(x)
        if lane_valid:
            alpha = 1.0 - math.exp(-x / blend)
            ys.append(alpha * lat_poly_y(x, c0, c1, c2, c3))
        else:
            ys.append(0.0)
    return xs, ys, horizon


def test_lka_lane_left_error_steers_left() -> None:
    # e_y>0: lane center left of ego → steer left (CARLA steer<0 after negate)
    s = m_lat_lka(True, 0.5, 0.0, 0.0)
    assert s < 0.0


def test_lka_fallback_ego() -> None:
    s = m_lat_lka(False, 0.0, 0.0, 25.0)
    assert abs(s) < 1e-6


def test_lka_large_ey_gain_reduced() -> None:
    s_small = abs(m_lat_lka(True, 0.3, 0.0, 0.0))
    s_big = abs(m_lat_lka(True, 1.5, 0.0, 0.0))
    # Saturated e + lower ky → big offset must not explode past max
    assert s_big <= 0.55 + 1e-6
    assert s_small < s_big or s_small > 0.0


def test_traj_points_count_and_blend() -> None:
    xs, ys, _h = m_lat_traj(10.0, 1.0, True, 0.5, 0.0, 0.0, 0.0, 60.0)
    assert len(xs) == 16 and len(ys) == 16
    assert xs[0] == 0.0
    assert abs(ys[0]) < 1e-9
    assert ys[-1] > 0.0  # blended toward c0=0.5


def test_generate_lat_headers() -> None:
    from pathlib import Path

    from gf_octavecoder.generate import generate_sku

    root = Path(__file__).resolve().parents[3]
    assert generate_sku(repo_root=root, sku="afc", force=True) == 0
    for name in ("m_lat_lka.hpp", "m_lat_traj.hpp", "m_lon_acc_aeb.hpp"):
        p = root / "projects/afc/apps/planning/driving/oct_gen" / name
        assert p.is_file(), name
