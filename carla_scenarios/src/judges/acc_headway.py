"""ACC time-headway verdict (thin wrapper over _verdict.verdict_acc)."""

from __future__ import annotations

from typing import Any

from _verdict import Sample, verdict_acc


def judge_acc(
    samples: list[Sample],
    *,
    seen_control: bool,
    th_lo: float = 1.0,
    th_hi: float = 2.5,
) -> tuple[bool, str, dict[str, Any]]:
    return verdict_acc(
        samples, seen_control=seen_control, th_lo=th_lo, th_hi=th_hi
    )
