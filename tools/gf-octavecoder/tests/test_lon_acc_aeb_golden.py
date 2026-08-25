from __future__ import annotations

"""Golden vectors mirroring octave_planning/afc/m_lon_acc_aeb.m / ops lon_acc_aeb.hpp."""


def gf_clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def lon_cruise(v: float) -> dict:
    target = 12.0
    err = target - v
    if v < 0.8:
        thr = gf_clamp(0.45 + err * 0.05, 0.40, 0.75)
        brk = 0.0
    else:
        thr = gf_clamp(0.2 + err * 0.08, 0.0, 0.7)
        brk = gf_clamp((-err - 2.0) * 0.1, 0.0, 0.4) if err < -2.0 else 0.0
    return {"mode": "cruise", "throttle": thr, "brake": brk, "target_speed_mps": target}


def lon_aeb(v: float, d: float, ttc: float) -> dict:
    brk = 1.0 if (d < 5.0 or ttc < 1.0) else gf_clamp(0.55 + (10.0 - d) * 0.05, 0.55, 1.0)
    return {"mode": "aeb", "throttle": 0.0, "brake": brk, "target_speed_mps": 0.0}


def lon_pullaway(v: float, d: float, rel: float, gap_err: float) -> dict:
    pull = gf_clamp(8.0 + gap_err * 0.2 + rel * 0.3, 6.0, 12.0)
    return {
        "mode": "pullaway",
        "throttle": gf_clamp(0.42 + (pull - v) * 0.06, 0.35, 0.75),
        "brake": 0.0,
        "target_speed_mps": pull,
    }


def lon_acc_follow(v: float, d: float, rel: float) -> dict:
    desired_gap = gf_clamp(max(8.0, v * 1.6), 8.0, 40.0)
    gap_err = d - desired_gap
    target = gf_clamp(v + gap_err * 0.15 + rel * 0.4, 0.0, 16.0)
    speed_err = target - v
    if speed_err >= 0.0:
        thr, brk = gf_clamp(0.15 + speed_err * 0.1, 0.0, 0.65), 0.0
    else:
        thr, brk = 0.0, gf_clamp((-speed_err) * 0.12, 0.0, 0.7)
    return {"mode": "acc", "throttle": thr, "brake": brk, "target_speed_mps": target}


def m_lon_acc_aeb(v: float, lead_valid: bool, d: float, rel: float) -> dict:
    v = max(0.0, v)
    if not lead_valid:
        return lon_cruise(v)
    closing = max(0.0, -rel)
    ttc = (d / closing) if closing > 0.5 else 1.0e6
    if d < 5.0 or (v > 1.2 and (d < 10.0 or ttc < 1.4)):
        return lon_aeb(v, d, ttc)
    desired_gap = gf_clamp(max(8.0, v * 1.6), 8.0, 40.0)
    gap_err = d - desired_gap
    if v < 1.0 and d > 10.0:
        return lon_pullaway(v, d, rel, gap_err)
    return lon_acc_follow(v, d, rel)


def test_cruise_standstill_pull_floor() -> None:
    c = m_lon_acc_aeb(0.0, False, 0.0, 0.0)
    assert c["mode"] == "cruise"
    assert c["throttle"] >= 0.40


def test_aeb_near() -> None:
    c = m_lon_acc_aeb(8.0, True, 4.0, -2.0)
    assert c["mode"] == "aeb"
    assert c["brake"] == 1.0
    assert c["throttle"] == 0.0


def test_pullaway() -> None:
    c = m_lon_acc_aeb(0.2, True, 20.0, 0.0)
    assert c["mode"] == "pullaway"
    assert c["throttle"] >= 0.35


def test_generate_lon_header() -> None:
    from pathlib import Path

    from gf_octavecoder.generate import generate_sku

    root = Path(__file__).resolve().parents[3]
    assert generate_sku(repo_root=root, sku="afc", force=True) == 0
    text = (
        root / "projects/afc/apps/planning/driving/oct_gen/m_lon_acc_aeb.hpp"
    ).read_text(encoding="utf-8")
    assert "gf_octave_planning::m_lon_acc_aeb" in text
    assert "lon_cruise" in text
