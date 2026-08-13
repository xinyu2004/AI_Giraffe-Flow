"""Thin re-export of tip mount — do **not** copy logic here.

Canonical: ``carla_scenarios/src/lib/_tip_mount.py`` (product camera geometry).
Bridge only reads already-set env (SKU ``carla.env`` via ``run_sil``); never
loads ``carla_scenarios/carla.env``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _scenarios_lib() -> Path:
    env = (os.environ.get("GF_SCENARIOS_DIR") or "").strip()
    if env:
        root = Path(env).expanduser().resolve()
    else:
        # tip_mount.py → carla_bridge → tools → sku → oem → projects → repo
        root = Path(__file__).resolve().parents[5] / "carla_scenarios"
    lib = root / "src" / "lib"
    if not (lib / "_tip_mount.py").is_file():
        raise ImportError(
            f"tip_mount canonical missing: {lib / '_tip_mount.py'} "
            f"(set GF_SCENARIOS_DIR to carla_scenarios root)"
        )
    return lib


_lib = _scenarios_lib()
_lib_s = str(_lib)
if _lib_s not in sys.path:
    sys.path.insert(0, _lib_s)

from _tip_mount import (  # noqa: E402
    TipMount,
    load_tip_mount,
    resolve_tip_mount_id,
    scene_chase_pose,
)

__all__ = [
    "TipMount",
    "load_tip_mount",
    "resolve_tip_mount_id",
    "scene_chase_pose",
]
