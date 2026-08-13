"""Shared truth-tip writer for carla_scenarios (no Giraffe / gf-* imports)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional


def truth_path() -> Path:
    return Path(os.environ.get("GF_CARLA_TRUTH_PATH") or "/tmp/gf_carla_truth.json")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_truth(
    *,
    scenario: str,
    lead_distance_m: float,
    lead_rel_speed_mps: float,
    seq: int,
    ego_mps: Optional[float] = None,
    th_s: Optional[float] = None,
    set_speed_kph: Optional[float] = None,
    case_index: Optional[int] = None,
    case_total: Optional[int] = None,
    keyword: Optional[str] = None,
    t_s: Optional[float] = None,
    duration_s: Optional[float] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Write truth tip. Legacy flat fields kept for planning ACC/AEB."""
    payload: dict[str, Any] = {
        "timestamp_ns": time.time_ns(),
        "seq": seq,
        "scenario": scenario,
        "lead_distance_m": float(lead_distance_m),
        "lead_rel_speed_mps": float(lead_rel_speed_mps),
        "dyn_obj_count": 1 if lead_distance_m < 120.0 else 0,
    }
    if ego_mps is not None:
        payload["ego_mps"] = float(ego_mps)
        payload["ego_kph"] = float(ego_mps) * 3.6
    if th_s is not None:
        payload["th_s"] = float(th_s)
    if set_speed_kph is not None:
        payload["set_speed_kph"] = float(set_speed_kph)
    run: dict[str, Any] = {"case_id": scenario}
    if case_index is not None:
        run["case_index"] = int(case_index)
    if case_total is not None:
        run["case_total"] = int(case_total)
    if keyword is not None:
        run["keyword"] = keyword
    if t_s is not None:
        run["t_s"] = float(t_s)
    if duration_s is not None:
        run["duration_s"] = float(duration_s)
    if len(run) > 1:
        payload["run"] = run
    if extra:
        payload.update(extra)
    atomic_write_text(
        truth_path(), json.dumps(payload, separators=(",", ":")) + "\n"
    )
