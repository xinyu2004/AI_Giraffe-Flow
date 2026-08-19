"""Closed-loop verdict helpers for AFC scenarios (no Giraffe imports)."""

from __future__ import annotations

def _ipc_under_project(name: str) -> Path:
    import os
    proj = (os.environ.get("GF_PROJECT_DIR") or "").strip()
    if proj:
        return Path(proj) / "runtime_ipc" / name
    return Path("runtime_ipc") / name


import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def cmd_path() -> Path:
    return Path(os.environ.get("GF_CARLA_CMD_PATH") or str(_ipc_under_project("carla_cmd.json")))


def time_headway_s(gap_m: float, ego_mps: float, v_min: float = 1.0) -> float:
    return float(gap_m) / max(float(ego_mps), float(v_min))


@dataclass
class CmdProbe:
    """Detect Giraffe→bridge cmd freshness during the case window.

    First poll only baselines seq/mtime (stale files do NOT count as control).
    """

    path: Path = field(default_factory=cmd_path)
    last_seq: int = -1
    last_mtime: float = -1.0
    fresh_count: int = 0
    _armed: bool = False

    def poll(self) -> bool:
        p = self.path
        if not p.is_file():
            return False
        try:
            mtime = p.stat().st_mtime
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return False
        seq = int(data.get("seq", 0))
        if not self._armed:
            self.last_seq = seq
            self.last_mtime = mtime
            self._armed = True
            return False
        if seq != self.last_seq or mtime != self.last_mtime:
            self.fresh_count += 1
            self.last_seq = seq
            self.last_mtime = mtime
            return True
        return False

    @property
    def seen_control(self) -> bool:
        return self.fresh_count > 0


@dataclass
class Sample:
    t: float
    gap_m: float
    ego_mps: float
    lead_mps: float
    rel_mps: float
    th_s: float
    collided: bool


def actors_colliding(ego: Any, lead: Any, gap_crash_m: float = 3.5) -> bool:
    """Centroid distance heuristic (vehicles + VRU). Loose enough for walkers/bikes."""
    try:
        a = ego.get_location()
        b = lead.get_location()
        gap = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
        return gap < gap_crash_m
    except Exception:  # noqa: BLE001
        return False


def release_ego(carla_mod: Any, ego: Any) -> None:
    try:
        ego.set_autopilot(False)
    except Exception:  # noqa: BLE001
        pass
    try:
        ego.apply_control(
            carla_mod.VehicleControl(
                throttle=0.0, brake=0.0, steer=0.0, hand_brake=False
            )
        )
    except Exception:  # noqa: BLE001
        pass


def freeze_actors(*actors: Any, carla_mod: Any = None) -> None:
    """Disable constant-velocity and hard-brake (collision early-exit)."""
    mod = carla_mod
    if mod is None:
        import carla as mod  # type: ignore
    for actor in actors:
        if actor is None:
            continue
        try:
            actor.disable_constant_velocity()
        except Exception:  # noqa: BLE001
            pass
        try:
            actor.set_target_velocity(mod.Vector3D(0.0, 0.0, 0.0))
        except Exception:  # noqa: BLE001
            pass
        try:
            actor.set_autopilot(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            actor.apply_control(
                mod.VehicleControl(
                    throttle=0.0,
                    brake=1.0,
                    steer=0.0,
                    hand_brake=True,
                    reverse=False,
                )
            )
        except Exception:  # noqa: BLE001
            try:
                actor.apply_control(mod.WalkerControl(speed=0.0))
            except Exception:  # noqa: BLE001
                pass


def print_verdict(tag: str, passed: bool, reason: str, **extra: Any) -> None:
    bits = " ".join(f"{k}={v}" for k, v in extra.items())
    status = "pass" if passed else "fail"
    line = f"[{tag}] VERDICT {status} reason={reason}"
    if bits:
        line = f"{line} {bits}"
    print("===", flush=True)
    print(line, flush=True)
    print("===", flush=True)


def verdict_acc(
    samples: list[Sample],
    *,
    seen_control: bool,
    th_lo: float = 1.0,
    th_hi: float = 2.5,
    settle_s: float = 3.0,
    in_band_ratio: float = 0.6,
) -> tuple[bool, str, dict[str, Any]]:
    if not seen_control:
        return False, "no_giraffe_control", {"cmd_fresh": 0}
    if any(s.collided for s in samples):
        return False, "collision_lead", {}
    scored = [s for s in samples if s.t >= settle_s]
    if len(scored) < 3:
        return False, "insufficient_samples", {"n": len(scored)}
    in_band = sum(1 for s in scored if th_lo <= s.th_s <= th_hi)
    ratio = in_band / len(scored)
    th_mean = sum(s.th_s for s in scored) / len(scored)
    high = sum(1 for s in scored if s.th_s > th_hi)
    if high / len(scored) > 0.7:
        return False, "headway_too_large", {
            "th_mean": round(th_mean, 3),
            "in_band": round(ratio, 3),
        }
    if ratio < in_band_ratio:
        return False, "headway_out_of_band", {
            "th_mean": round(th_mean, 3),
            "in_band": round(ratio, 3),
        }
    return True, "ok", {"th_mean": round(th_mean, 3), "in_band": round(ratio, 3)}


def verdict_aeb(
    samples: list[Sample],
    *,
    seen_control: bool,
    settle_s: float = 1.5,
) -> tuple[bool, str, dict[str, Any]]:
    """AEB: without brake, closing ego must hit lead; with Giraffe, must not."""
    collided = any(s.collided for s in samples)
    meta: dict[str, Any] = {}
    if samples:
        meta["gap0"] = round(samples[0].gap_m, 2)
        meta["gap_end"] = round(samples[-1].gap_m, 2)
        meta["min_gap"] = round(min(s.gap_m for s in samples), 2)
        meta["v0"] = round(samples[0].ego_mps, 2)

    if not seen_control:
        # Open-loop: must demonstrate hazard — collision expected.
        if collided:
            return False, "no_giraffe_control", {**meta, "note": "hit_without_control"}
        return False, "no_giraffe_control", {
            **meta,
            "note": "no_hit_check_ego_speed",
        }

    if collided:
        return False, "collision_lead", meta

    scored = [s for s in samples if s.t >= settle_s]
    if len(scored) < 3:
        return False, "insufficient_samples", {"n": len(scored), **meta}

    last = scored[-1]
    # Still diving in at the end ⇒ brake not effective.
    if last.gap_m < 5.0 and last.rel_mps < -1.5:
        return False, "no_decel_intent", {
            **meta,
            "rel_end": round(last.rel_mps, 2),
        }
    return True, "ok", meta


def run_duration_loop(
    *,
    duration_s: float,
    period_s: float,
    stop_flag: Any,
    on_tick: Any,
) -> None:
    import time

    t0 = time.time()
    while not stop_flag() and (time.time() - t0) < duration_s:
        on_tick(time.time() - t0)
        time.sleep(period_s)
