from __future__ import annotations

"""LC layers: can / weights / commit. Mirrors gf_lc_*.m and lc_side.hpp."""

CAL = {
    "d_lc_min_m": 40.0,
    "d_cal_cap_m": 120.0,
    "t_lc_min_s": 6.0,
    "d_lc_rear_min_m": 2.0,
    "d_lc_host_min_m": 8.0,
    "lc_ttc_margin_s": 1.0,
    "lc_hdg_same": 0.50,
    "lc_left_bias_m": 8.0,
    "lc_hyst_m": 6.0,
    "lc_stay_m": 12.0,
    "closing_min_mps": 0.3,
    "traj_speed_floor_mps": 0.2,
    "cruise_v_mps": 25.0,
    "acc_time_gap_s": 1.7,
    "acc_gap_min_m": 8.0,
}


def q(
    *,
    have_H: bool = True,
    d_H_f: float = 80.0,
    d_H_hard: float = 1.0e6,
    rel_H_f: float = 0.0,
    hdg_H_f: float = 0.0,
    d_H_r: float = 30.0,
    rel_H_r: float = 0.0,
    have_L: bool = False,
    d_L_f: float = 0.0,
    d_L_hard: float = 1.0e6,
    rel_L_f: float = 0.0,
    hdg_L_f: float = 0.0,
    d_L_r: float = 0.0,
    rel_L_r: float = 0.0,
    have_R: bool = False,
    d_R_f: float = 0.0,
    d_R_hard: float = 1.0e6,
    rel_R_f: float = 0.0,
    hdg_R_f: float = 0.0,
    d_R_r: float = 0.0,
    rel_R_r: float = 0.0,
) -> dict:
    return {
        "have_H": have_H,
        "d_H_f": d_H_f,
        "d_H_hard": d_H_hard,
        "rel_H_f": rel_H_f,
        "hdg_H_f": hdg_H_f,
        "d_H_r": d_H_r,
        "rel_H_r": rel_H_r,
        "have_L": have_L,
        "d_L_f": d_L_f,
        "d_L_hard": d_L_hard,
        "rel_L_f": rel_L_f,
        "hdg_L_f": hdg_L_f,
        "d_L_r": d_L_r,
        "rel_L_r": rel_L_r,
        "have_R": have_R,
        "d_R_f": d_R_f,
        "d_R_hard": d_R_hard,
        "rel_R_f": rel_R_f,
        "hdg_R_f": hdg_R_f,
        "d_R_r": d_R_r,
        "rel_R_r": rel_R_r,
    }


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


def gf_lc_rear_ok(d_r: float, rel_r: float, v: float) -> bool:
    T = gf_lc_T_need(v)
    if T > CAL["t_lc_min_s"]:
        return False
    return gf_lc_time_ok(d_r, max(0.0, rel_r), rel_r < -0.3, v, T)


def gf_lc_host_ok(
    d_f: float,
    rel_f: float,
    hdg_f: float,
    v: float,
    d_hard: float = 1.0e6,
) -> bool:
    T = gf_lc_T_need(v)
    if d_f < CAL["d_lc_host_min_m"]:
        return False
    if d_f < 100.0 and not gf_lc_same_way(hdg_f):
        return False
    if not gf_lc_time_ok(d_f, max(0.0, -rel_f), True, v, T):
        return False
    if not gf_lc_time_ok(d_hard, max(0.0, v), False, v, T):
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


def gf_lc_quality(d_f: float, d_r: float, rel_r: float) -> float:
    p = CAL
    d_f = min(max(0.0, d_f), p["d_cal_cap_m"])
    d_r = min(max(0.0, d_r), p["d_lc_min_m"])
    s = d_f + 0.6 * d_r
    if rel_r > 0.3:
        ttc = d_r / max(rel_r, 0.05)
        s -= max(0.0, 8.0 - ttc) * 2.0
    return s


def gf_lc_weights(quad: dict, v: float, D_see: float) -> dict:
    w = {"H": 0.0, "L": 0.0, "R": 0.0, "ok_H": False, "ok_L": False, "ok_R": False}
    w["ok_H"] = bool(quad["have_H"])
    if w["ok_H"]:
        w["H"] = gf_lc_quality(quad["d_H_f"], CAL["d_lc_min_m"], 0.0)
    leave = gf_lc_host_ok(
        quad.get("d_H_f", 80.0),
        quad.get("rel_H_f", 0.0),
        quad.get("hdg_H_f", 0.0),
        v,
        quad.get("d_H_hard", 1.0e6),
    )
    w["ok_L"] = leave and gf_lc_can(
        quad["have_L"],
        quad["d_L_f"],
        quad["d_L_r"],
        quad["rel_L_r"],
        v,
        D_see,
        quad.get("d_L_hard", 1.0e6),
        quad.get("rel_L_f", 0.0),
        quad.get("hdg_L_f", 0.0),
    )
    if w["ok_L"]:
        w["L"] = gf_lc_quality(quad["d_L_f"], quad["d_L_r"], quad["rel_L_r"])
    w["ok_R"] = leave and gf_lc_can(
        quad["have_R"],
        quad["d_R_f"],
        quad["d_R_r"],
        quad["rel_R_r"],
        v,
        D_see,
        quad.get("d_R_hard", 1.0e6),
        quad.get("rel_R_f", 0.0),
        quad.get("hdg_R_f", 0.0),
    )
    if w["ok_R"]:
        w["R"] = gf_lc_quality(quad["d_R_f"], quad["d_R_r"], quad["rel_R_r"])
    return w


def gf_lc_side(quad: dict, v: float, D_see: float, last: int = 0) -> int:
    p = CAL
    w = gf_lc_weights(quad, v, D_see)
    host = w["H"] + p["lc_stay_m"]
    _ = last
    if w["ok_L"] and w["L"] > host:
        if w["ok_R"] and w["R"] > w["L"] + p["lc_left_bias_m"] and w["R"] > host:
            return -1
        return 1
    if w["ok_R"] and w["R"] > host:
        return -1
    return 0


def test_weights_same_formula_three_lanes() -> None:
    w = gf_lc_weights(
        q(d_H_f=80, d_H_r=45, have_L=True, d_L_f=80, d_L_r=45, have_R=True, d_R_f=80, d_R_r=45),
        25.0,
        120.0,
    )
    assert w["ok_H"] and w["ok_L"] and w["ok_R"]
    assert abs(w["H"] - w["L"]) < 1e-9
    assert abs(w["L"] - w["R"]) < 1e-9
    assert abs(w["H"] - gf_lc_quality(80, 45, 0)) < 1e-9


def test_host_as_good_stays() -> None:
    # Both neighbors open, host equally free → no S (not LC-for-LC).
    assert gf_lc_side(q(have_L=True, d_L_f=80, d_L_r=45, have_R=True, d_R_f=80, d_R_r=45), 25.0, 120.0) == 0


def test_no_la_stays() -> None:
    assert gf_lc_side(q(), 25.0, 120.0) == 0


def test_right_open_host_good_stays() -> None:
    assert gf_lc_side(q(have_R=True, d_R_f=80, d_R_r=45), 25.0, 120.0) == 0


def test_overtake_left_when_host_short() -> None:
    assert (
        gf_lc_side(q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45), 25.0, 17.0) == 1
    )


def test_overtake_right_when_no_left() -> None:
    assert (
        gf_lc_side(q(d_H_f=17, d_H_r=30, have_R=True, d_R_f=80, d_R_r=45), 25.0, 17.0) == -1
    )


def test_right_wins_only_if_clearly_better() -> None:
    blocked = q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=50, d_L_r=45, have_R=True, d_R_f=55, d_R_r=47)
    assert gf_lc_side(blocked, 25.0, 120.0) == 1
    right_clear = q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=45, d_L_r=45, have_R=True, d_R_f=90, d_R_r=50)
    assert gf_lc_side(right_clear, 25.0, 120.0) == -1


def test_enter_only_ignores_last() -> None:
    overtake = q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45, have_R=True, d_R_f=80, d_R_r=45)
    assert gf_lc_side(overtake, 25.0, 120.0, last=-1) == 1
    even = q(d_H_f=80, d_H_r=45, have_L=True, d_L_f=80, d_L_r=45, have_R=True, d_R_f=80, d_R_r=45)
    assert gf_lc_side(even, 25.0, 120.0, last=1) == 0
    assert gf_lc_side(even, 25.0, 120.0, last=-1) == 0


def test_short_fwd_no_s() -> None:
    # 20 m at 25 m/s is inside ACC gap (42.5), not a 40 m stick.
    assert gf_lc_side(q(have_L=True, d_L_f=20, d_L_r=45, have_R=True, d_R_f=20, d_R_r=45), 25.0, 120.0) == 0


def test_front_acc_gap_not_40_stick() -> None:
    assert gf_lc_can(True, 120.0, 45.0, 0.0, 25.0, 120.0)
    assert not gf_lc_can(True, 15.0, 45.0, 0.0, 25.0, 120.0)
    assert gf_lc_can(True, 35.0, 30.0, 0.0, 10.0, 120.0)
    assert not gf_lc_can(True, 120.0, 45.0, 0.0, 25.0, 120.0, 20.0)
    assert (
        gf_lc_side(q(d_H_f=15, d_H_r=30, have_R=True, d_R_f=120, d_R_r=45), 25.0, 120.0) == -1
    )
    assert (
        gf_lc_side(
            q(d_H_f=15, d_H_r=30, have_R=True, d_R_f=120, d_R_hard=20, d_R_r=45), 25.0, 120.0
        )
        == 0
    )


def test_same_speed_needs_acc_gap() -> None:
    assert not gf_lc_can(True, 80.0, 4.0, 0.0, 25.0, 120.0)
    assert gf_lc_can(True, 80.0, 45.0, 0.0, 25.0, 120.0)
    assert gf_lc_side(q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=4.0), 25.0, 120.0) == 0


def test_opening_rear_pad() -> None:
    assert gf_lc_can(True, 80.0, 4.0, -1.0, 25.0, 120.0)
    assert gf_lc_side(q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=4.0, rel_L_r=-1.0), 25.0, 120.0) == 1


def test_opening_front_not_acc() -> None:
    assert gf_lc_can(True, 15.0, 45.0, 0.0, 25.0, 120.0, 1.0e6, 2.0, 0.0)
    assert not gf_lc_can(True, 15.0, 45.0, 0.0, 25.0, 120.0, 1.0e6, 0.0, 0.0)


def test_oncoming_heading_veto() -> None:
    assert not gf_lc_can(True, 80.0, 45.0, 0.0, 25.0, 120.0, 1.0e6, 0.0, 1.0)
    assert gf_lc_can(True, 80.0, 45.0, 0.0, 25.0, 120.0, 1.0e6, 0.0, 0.0)
    assert gf_lc_can(True, 120.0, 45.0, 0.0, 25.0, 120.0, 1.0e6, 0.0, 1.0)
    assert (
        gf_lc_side(q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45, hdg_L_f=1.0), 25.0, 17.0)
        == 0
    )


def test_slow_no_enter() -> None:
    assert not gf_lc_can(True, 80.0, 45.0, 0.0, 2.7, 120.0)
    assert gf_lc_can(True, 80.0, 20.0, 0.0, 8.0, 120.0)


def test_rear_pad_withdraws() -> None:
    good = q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45)
    assert gf_lc_side(good, 25.0, 120.0) == 1
    rear = q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=0.5)
    assert gf_lc_side(rear, 25.0, 120.0) == 0
    assert gf_lc_side(rear, 25.0, 120.0, last=1) == 0


def test_empty_rear_far_passes() -> None:
    assert gf_lc_can(True, 80.0, 120.0, 0.0, 25.0, 120.0)
    assert gf_lc_side(q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=120.0), 25.0, 120.0) == 1


def test_closing_rear_ttc_withdraws() -> None:
    assert gf_lc_side(q(d_H_f=17, have_L=True, d_L_f=80, d_L_r=10, rel_L_r=5.0), 25.0, 120.0) == 0
    assert gf_lc_side(
        q(d_H_f=17, have_L=True, d_L_f=80, d_L_r=10, rel_L_r=5.0), 25.0, 120.0, last=1
    ) == 0


def test_enter_zero_when_have_lost() -> None:
    lost = q(d_H_f=17, d_H_r=30, have_L=False)
    assert gf_lc_side(lost, 25.0, 120.0, last=1) == 0
    assert gf_lc_side(q(d_H_f=17, d_H_r=30, have_R=False), 25.0, 120.0, last=-1) == 0


def test_host_dsee_does_not_veto_overtake() -> None:
    # Host follow D_see=17 is not a land veto; host *land* 17 vs left 80 is the reason.
    assert gf_lc_side(q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45), 25.0, 17.0) == 1


def test_cruise_90_in_cal() -> None:
    assert abs(CAL["cruise_v_mps"] - 90.0 / 3.6) < 1e-6


def test_quality_caps_empty_rear() -> None:
    far = gf_lc_quality(120.0, 1.0e6, 0.0)
    near = gf_lc_quality(120.0, 45.0, 0.0)
    assert far == gf_lc_quality(120.0, 40.0, 0.0)
    assert abs(far - near) < 1.0
    even = q(d_H_f=80, d_H_r=35, have_L=True, d_L_f=80, d_L_r=1.0e6, have_R=True, d_R_f=80, d_R_r=1.0e6)
    assert gf_lc_side(even, 25.0, 120.0) == 0


def test_allow_lc_only_when_side_committed() -> None:
    # Tick layer: allow_lc follows m_lc_path hold. Host-better pick is 0.
    even = q(d_H_f=80, d_H_r=45, have_L=True, d_L_f=80, d_L_r=45, have_R=True, d_R_f=80, d_R_r=45)
    assert gf_lc_side(even, 25.0, 120.0) == 0
    overtake = q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45)
    assert gf_lc_side(overtake, 25.0, 120.0) == 1


def test_host_pad_blocks_leave() -> None:
    # 1.7 m host lead is pad, not "overtake the car you are about to hit".
    assert not gf_lc_host_ok(1.7, 0.0, 0.0, 25.0)
    assert gf_lc_side(q(d_H_f=1.7, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45), 25.0, 120.0) == 0


def test_host_bumper_blocks_close_opening() -> None:
    # Opening skips ACC time-gap, not the host bumper. 2.4 m must not leave.
    assert not gf_lc_host_ok(2.38, 1.78, -0.43, 18.0)
    assert gf_lc_side(q(d_H_f=2.38, rel_H_f=1.78, hdg_H_f=-0.43, have_L=True, d_L_f=120, d_L_r=45), 18.0, 120.0) == 0
    assert not gf_lc_host_ok(7.9, 0.0, 0.0, 25.0)
    assert gf_lc_host_ok(8.0, 0.0, 0.0, 25.0)


def test_host_same_speed_overtake_still() -> None:
    assert gf_lc_host_ok(17.0, 0.0, 0.0, 25.0)
    assert gf_lc_side(q(d_H_f=17, d_H_r=30, have_L=True, d_L_f=80, d_L_r=45), 25.0, 17.0) == 1


def test_host_closing_ttc_blocks() -> None:
    assert not gf_lc_host_ok(17.0, -10.0, 0.0, 25.0)
    assert (
        gf_lc_side(q(d_H_f=17, rel_H_f=-10.0, have_L=True, d_L_f=80, d_L_r=45), 25.0, 120.0) == 0
    )


def test_host_oncoming_heading_blocks() -> None:
    assert not gf_lc_host_ok(17.0, 0.0, 1.0, 25.0)
    assert (
        gf_lc_side(q(d_H_f=17, hdg_H_f=1.0, have_L=True, d_L_f=80, d_L_r=45), 25.0, 17.0) == 0
    )


def test_host_rear_does_not_invite_leave() -> None:
    # Passed car sitting in host rear must not flip us back.
    dirty_rear = q(d_H_f=120, d_H_r=14.9, have_R=True, d_R_f=120, d_R_r=1.0e6)
    assert gf_lc_side(dirty_rear, 25.0, 120.0) == 0


def test_host_hard_blocks_leave() -> None:
    assert not gf_lc_host_ok(80.0, 0.0, 0.0, 25.0, 5.0)
    assert gf_lc_side(q(d_H_f=17, d_H_hard=5.0, have_L=True, d_L_f=80, d_L_r=45), 25.0, 120.0) == 0
