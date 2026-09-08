"""Drive C gf_host_bev_ws (gold paint). No Python LiveBevComposer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from .semantic_map import (
    PlanningResult,
    PlanningView,
    result_to_traj_dict,
    view_to_bev_out_dict,
    view_to_ego_dict,
)


def resolve_host_bev_bin() -> Optional[Path]:
    """Locate gf_host_bev_ws binary.

    Order:
      1. GF_HOST_BEV_BIN
      2. PATH
      3. repo build/stage: …/runtime/bin or …/apps/gmt_board/iox_obs_foxglove/
    """
    env = (os.environ.get("GF_HOST_BEV_BIN") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p.resolve()
        return None
    which = shutil.which("gf_host_bev_ws")
    if which:
        return Path(which).resolve()

    here = Path(__file__).resolve()
    # …/carla_scenarios/octave_bridge → repo
    repo = here.parents[2]
    cands = [
        repo / "projects" / "afc" / "runtime" / "bin" / "gf_host_bev_ws",
        repo / "build" / "apps" / "gmt_board" / "iox_obs_foxglove" / "gf_host_bev_ws",
        repo / "build-sil" / "apps" / "gmt_board" / "iox_obs_foxglove" / "gf_host_bev_ws",
        # CARLA copy: sibling next to carla_scenarios
        here.parents[1].parent / "gf_host_bev_ws",
        here.parents[1].parent / "bin" / "gf_host_bev_ws",
    ]
    for c in cands:
        if c.is_file():
            return c.resolve()
    return None


class BevFeed:
    """Spawn gf_host_bev_ws; push Ego/Out/Traj NDJSON on stdin. C owns Foxglove WS."""

    def __init__(self, *, foxglove_host: str = "0.0.0.0", foxglove_port: int = 8765) -> None:
        bin_path = resolve_host_bev_bin()
        if bin_path is None:
            raise FileNotFoundError(
                "gf_host_bev_ws not found. Build/stage it, then either:\n"
                "  export GF_HOST_BEV_BIN=/path/to/gf_host_bev_ws\n"
                "  # or put it on PATH / projects/afc/runtime/bin/\n"
                "  # or: --no-foxglove (plan/cmd only)\n"
                f"  (looked at GF_HOST_BEV_BIN={os.environ.get('GF_HOST_BEV_BIN')!r})"
            )
        self.bin_path = bin_path
        self.last_png_row: Optional[dict[str, Any]] = None
        cmd = [
            str(bin_path),
            "--host",
            foxglove_host,
            "--port",
            str(int(foxglove_port)),
        ]
        try:
            period = float(os.environ.get("GF_BEV_PERIOD_S") or "0.033")
            period_ms = max(1, int(round(period * 1000.0)))
        except ValueError:
            period_ms = 33
        cmd.extend(["--period-ms", str(period_ms)])
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=None,
            text=True,
            bufsize=1,
        )
        self.gmt_src = bin_path  # log field reuse: show paint binary path

    def update(self, view: PlanningView, result: PlanningResult) -> Optional[dict[str, Any]]:
        """Push Ego + Out + Trajectory NDJSON; C paints asynchronously. Always None."""
        if self._proc.poll() is not None:
            raise RuntimeError(f"gf_host_bev_ws exited rc={self._proc.returncode}")
        assert self._proc.stdin is not None
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
        for row in rows:
            self._proc.stdin.write(json.dumps(row, separators=(",", ":")) + "\n")
        self._proc.stdin.flush()
        self.last_png_row = None
        return None

    def png_bytes(self) -> Optional[bytes]:
        return None

    def stop(self) -> None:
        if self._proc.poll() is not None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2.0)
        except Exception:  # noqa: BLE001
            try:
                self._proc.kill()
            except Exception:  # noqa: BLE001
                pass


class BevAsync:
    """V-clock: feed C painter off the plan path. Rate-limited; may drop."""

    def __init__(self, feed: BevFeed, hub: Any = None) -> None:
        import queue
        import threading

        self._feed = feed
        self._hub = hub  # unused; C owns WS (kept for call-site compat)
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
            f"(GF_BEV_PERIOD_S) → {feed.bin_path.name}",
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
        try:
            self._feed.stop()
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
                self._feed.update(view, result)
            except Exception as exc:  # noqa: BLE001
                print(f"[octave_bridge] BEV worker: {exc}", flush=True)
            dt = time.perf_counter() - t0
            if self._perf is not None:
                self._perf.add("compose", dt)
                self._perf.tick(extra={"drop": self._dropped})
