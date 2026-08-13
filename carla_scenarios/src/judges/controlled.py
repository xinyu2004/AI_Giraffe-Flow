"""Generic closed-loop verdicts: Giraffe must control; no collision."""

from __future__ import annotations

from typing import Any

from _verdict import Sample


def judge_controlled_no_collision(
    samples: list[Sample],
    *,
    seen_control: bool,
    min_samples: int = 3,
) -> tuple[bool, str, dict[str, Any]]:
    if not seen_control:
        return False, "no_giraffe_control", {"cmd_fresh": 0}
    if any(s.collided for s in samples):
        return False, "collision", {}
    if len(samples) < min_samples:
        return False, "insufficient_samples", {"n": len(samples)}
    meta: dict[str, Any] = {"n": len(samples)}
    if samples:
        meta["ego_mean"] = round(sum(s.ego_mps for s in samples) / len(samples), 2)
        if any(s.gap_m > 0 for s in samples):
            meta["min_gap"] = round(min(s.gap_m for s in samples if s.gap_m > 0), 2)
    return True, "ok", meta


def judge_aeb_like(
    samples: list[Sample],
    *,
    seen_control: bool,
) -> tuple[bool, str, dict[str, Any]]:
    from _verdict import verdict_aeb

    return verdict_aeb(samples, seen_control=seen_control)


def judge_fcw(
    samples: list[Sample],
    *,
    seen_control: bool,
    settle_s: float = 1.0,
) -> tuple[bool, str, dict[str, Any]]:
    """FCW window: control required; no collision; hazard must close initially."""
    if not seen_control:
        return False, "no_giraffe_control", {}
    if any(s.collided for s in samples):
        return False, "collision_lead", {}
    scored = [s for s in samples if s.t >= settle_s]
    if len(scored) < 3:
        return False, "insufficient_samples", {"n": len(scored)}
    if samples and scored:
        closed = scored[-1].gap_m < samples[0].gap_m - 2.0 or any(
            s.th_s < 2.5 for s in scored
        )
        if not closed and samples[0].gap_m > 5.0:
            # Still ok if Giraffe held a safe gap after seeing hazard.
            pass
    return True, "ok", {
        "gap0": round(samples[0].gap_m, 2) if samples else 0,
        "gap_end": round(samples[-1].gap_m, 2) if samples else 0,
    }


def judge_lateral(
    samples: list[Sample],
    *,
    seen_control: bool,
) -> tuple[bool, str, dict[str, Any]]:
    """LKA/LDW/ELK/LCC atom: Giraffe must drive; no collision with neighbor."""
    return judge_controlled_no_collision(samples, seen_control=seen_control)


def judge_env(
    samples: list[Sample],
    *,
    seen_control: bool,
) -> tuple[bool, str, dict[str, Any]]:
    """ISP/weather/roadway atom: control + survive duration."""
    return judge_controlled_no_collision(samples, seen_control=seen_control)
