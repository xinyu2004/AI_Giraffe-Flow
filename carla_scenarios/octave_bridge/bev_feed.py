"""Feed shared tools/gmt bev_compose.LiveBevComposer (no second BEV)."""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .semantic_map import (
    PlanningResult,
    PlanningView,
    result_to_traj_dict,
    view_to_bev_out_dict,
    view_to_ego_dict,
)


def resolve_gmt_src() -> Optional[Path]:
    """Locate tools/gmt/src (directory that contains package ``gf_gmt``).

    Order:
      1. ``GF_GMT_SRC`` — explicit path (CARLA machine copy / mount)
      2. Monorepo layout: ``<repo>/tools/gmt/src`` next to ``carla_scenarios``
      3. Sibling ``gmt/src`` under the same parent as ``carla_scenarios`` (manual copy)
    """
    env = (os.environ.get("GF_GMT_SRC") or "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "gf_gmt").is_dir():
            return p
        # allow pointing at tools/gmt (with src/) or at gf_gmt itself
        if (p / "src" / "gf_gmt").is_dir():
            return p / "src"
        if p.name == "gf_gmt" and p.is_dir():
            return p.parent
        return None

    here = Path(__file__).resolve()
    # …/AI_Giraffe-Flow/carla_scenarios/octave_bridge/bev_feed.py → repo/tools/gmt/src
    cand = here.parents[2] / "tools" / "gmt" / "src"
    if (cand / "gf_gmt").is_dir():
        return cand
    # …/PythonAPI/carla_scenarios + copied …/PythonAPI/gmt/src
    cand2 = here.parents[1].parent / "gmt" / "src"
    if (cand2 / "gf_gmt").is_dir():
        return cand2
    return None


def ensure_gf_gmt_on_path() -> Optional[Path]:
    src = resolve_gmt_src()
    if src is None:
        return None
    s = str(src)
    if s not in sys.path:
        sys.path.insert(0, s)
    return src


class BevFeed:
    def __init__(self) -> None:
        src = ensure_gf_gmt_on_path()
        if src is None:
            raise ModuleNotFoundError(
                "gf_gmt not found. For shared Foxglove/BEV paintbrush either:\n"
                "  export GF_GMT_SRC=/path/to/AI_Giraffe-Flow/tools/gmt/src\n"
                "  # or: pip install -e /path/to/AI_Giraffe-Flow/tools/gmt\n"
                "  # or: --no-bev  (plan/cmd only)\n"
                f"  (looked at GF_GMT_SRC={os.environ.get('GF_GMT_SRC')!r})"
            )
        from gf_gmt.bev_compose import LiveBevComposer  # noqa: WPS433

        self._comp = LiveBevComposer()
        self.last_png_row: Optional[dict[str, Any]] = None
        self.gmt_src = src

    def update(self, view: PlanningView, result: PlanningResult) -> Optional[dict[str, Any]]:
        """Push Ego + Out + Trajectory shaped rows; return CompressedImage row if any."""
        t = view.stamp_ns or result.stamp_ns
        rows = [
            {"t_ns": t, "topic": "/gf/EgoMotion", "data": view_to_ego_dict(view)},
            {
                "t_ns": t,
                "topic": "/gf/Perception_MESSAGE_Out_St",
                "data": view_to_bev_out_dict(view),
            },
            {"t_ns": t, "topic": "/gf/Trajectory", "data": result_to_traj_dict(result)},
        ]
        cam = None
        for row in rows:
            cam = self._comp.update(row) or cam
        self.last_png_row = cam
        return cam

    def png_bytes(self) -> Optional[bytes]:
        row = self.last_png_row
        if not row:
            return None
        data = row.get("data") or {}
        raw = data.get("data")
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        if isinstance(raw, str) and raw:
            try:
                return base64.b64decode(raw)
            except Exception:  # noqa: BLE001
                return None
        return None


class BevAsync:
    """V-clock: compose off the plan path. Rate-limited; may drop. Never drop perc."""

    def __init__(self, feed: BevFeed, hub: Any) -> None:
        import queue
        import threading

        self._feed = feed
        self._hub = hub
        self._q: Any = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._dropped = 0
        self._last_sub = 0.0
        try:
            self._period = max(0.0, float(os.environ.get("GF_BEV_PERIOD_S") or "0.2"))
        except ValueError:
            self._period = 0.2
        self._perf = None
        try:
            from _perf import PerfAgg  # noqa: WPS433

            self._perf = PerfAgg("bev")
        except Exception:  # noqa: BLE001
            self._perf = None
        print(
            f"[octave_bridge] BEV V-clock period={self._period:.2f}s "
            f"(GF_BEV_PERIOD_S, 0=every plan)",
            flush=True,
        )
        self._th = threading.Thread(target=self._run, name="bev_v", daemon=True)
        self._th.start()

    def submit(self, view: PlanningView, result: PlanningResult) -> None:
        import time

        now = time.monotonic()
        if self._period > 0.0 and (now - self._last_sub) < self._period:
            self._dropped += 1
            return
        item = (view, result)
        try:
            self._q.put_nowait(item)
            self._last_sub = now
            return
        except Exception:  # noqa: BLE001
            self._dropped += 1

    def dropped(self) -> int:
        return int(self._dropped)

    def stop(self) -> None:
        self._stop.set()
        try:
            self._q.put_nowait(None)
        except Exception:  # noqa: BLE001
            pass

    def _run(self) -> None:
        import time

        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.2)
            except Exception:  # noqa: BLE001
                continue
            if item is None:
                break
            view, result = item
            t0 = time.perf_counter()
            try:
                cam = self._feed.update(view, result)
                if cam is not None:
                    self._hub.publish_row(cam)
            except Exception as exc:  # noqa: BLE001
                print(f"[octave_bridge] BEV worker: {exc}", flush=True)
            dt = time.perf_counter() - t0
            if self._perf is not None:
                self._perf.add("compose", dt)
                self._perf.tick(extra={"drop": self._dropped})
