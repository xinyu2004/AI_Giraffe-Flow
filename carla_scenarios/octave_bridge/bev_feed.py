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
