"""Wall-clock stages for CARLA host fps diagnosis (iGPU-friendly).

Enable: GF_PERF=1 (default). Off: GF_PERF=0.
Period: GF_PERF_PERIOD_S (default 2).

Read a line as: hz = how often THIS process stepped; *ms = mean stage time.
Compare processes: giraffe loop vs UE cam_age vs octave plan/bev vs pygame.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional


def perf_enabled() -> bool:
    v = (os.environ.get("GF_PERF") or "1").strip().lower()
    return v not in ("0", "off", "false", "no")


def perf_period_s() -> float:
    try:
        return max(0.5, float(os.environ.get("GF_PERF_PERIOD_S") or "2"))
    except ValueError:
        return 2.0


class PerfAgg:
    def __init__(self, name: str) -> None:
        self.name = name
        self._n = 0
        self._sums: dict[str, float] = {}
        self._counts: dict[str, int] = {}
        self._last = time.perf_counter()

    def add(self, key: str, seconds: float) -> None:
        self._sums[key] = self._sums.get(key, 0.0) + float(seconds)

    def count(self, key: str, n: int = 1) -> None:
        self._counts[key] = self._counts.get(key, 0) + int(n)

    def tick(self, extra: Optional[dict[str, Any]] = None) -> None:
        if not perf_enabled():
            return
        self._n += 1
        now = time.perf_counter()
        dt = now - self._last
        if dt < perf_period_s():
            return
        n = max(self._n, 1)
        parts = [f"hz={self._n / dt:.1f}", f"n={self._n}"]
        for k, v in self._sums.items():
            parts.append(f"{k}={1000.0 * v / n:.1f}ms")
        for k, v in self._counts.items():
            parts.append(f"{k}={v / dt:.1f}/s")
        if extra:
            for k, v in extra.items():
                parts.append(f"{k}={v}")
        print(f"[perf][{self.name}] " + " ".join(parts), flush=True)
        self._n = 0
        self._sums.clear()
        self._counts.clear()
        self._last = now


def dump_ue_settings(world: Any, *, log_prefix: str = "[perf][ue]") -> None:
    if not perf_enabled():
        return
    try:
        s = world.get_settings()
        n_veh = len(world.get_actors().filter("vehicle.*"))
        n_cam = len(world.get_actors().filter("sensor.camera.*"))
        snap = world.get_snapshot()
        print(
            f"{log_prefix} sync={int(bool(s.synchronous_mode))} "
            f"fixed_dt={float(s.fixed_delta_seconds):.4f} "
            f"no_render={int(bool(s.no_rendering_mode))} "
            f"veh={n_veh} cams={n_cam} frame={int(snap.frame)}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"{log_prefix} settings unavailable: {exc}", flush=True)
