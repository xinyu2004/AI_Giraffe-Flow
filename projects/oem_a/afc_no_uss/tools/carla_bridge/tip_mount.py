"""Tip camera mount for carla_bridge (keep in sync with carla_scenarios/src/lib/_tip_mount.py).

Env:

  GF_CARLA_TIP_MOUNT   1 = windshield (default); legacy names still accepted
  GF_CARLA_TIP_FOV     degrees (default 100)
  GF_CARLA_TIP_X/Y/Z   meters, vehicle-relative
  GF_CARLA_TIP_PITCH/YAW/ROLL  degrees
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


_PRESETS: dict[str, dict[str, float]] = {
    "1": {
        "x": 0.55,
        "y": 0.0,
        "z": 1.35,
        "pitch": -5.0,
        "yaw": 0.0,
        "roll": 0.0,
        "fov": 100.0,
    },
}

_MOUNT_ALIASES: dict[str, str] = {
    "1": "1",
    "mobileye_windshield": "1",
    "windshield": "1",
}


@dataclass(frozen=True)
class TipMount:
    name: str
    x: float
    y: float
    z: float
    pitch: float
    yaw: float
    roll: float
    fov: float

    def as_carla_transform(self, carla_mod: Any) -> Any:
        return carla_mod.Transform(
            carla_mod.Location(x=self.x, y=self.y, z=self.z),
            carla_mod.Rotation(pitch=self.pitch, yaw=self.yaw, roll=self.roll),
        )

    def describe(self) -> str:
        return (
            f"mount={self.name} fov={self.fov:.0f} "
            f"xyz=({self.x:.2f},{self.y:.2f},{self.z:.2f}) "
            f"pyr=({self.pitch:.1f},{self.yaw:.1f},{self.roll:.1f})"
        )


def _f(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return float(default)
    return float(raw)


def resolve_tip_mount_id(raw: str | None = None) -> str:
    key = (raw if raw is not None else os.environ.get("GF_CARLA_TIP_MOUNT") or "1")
    key = str(key).strip().lower()
    if not key:
        return "1"
    if key in _MOUNT_ALIASES:
        return _MOUNT_ALIASES[key]
    if key in _PRESETS:
        return key
    return key


def load_tip_mount() -> TipMount:
    mid = resolve_tip_mount_id()
    if mid in _PRESETS:
        base = dict(_PRESETS[mid])
        out_name = mid
    else:
        base = dict(_PRESETS["1"])
        out_name = mid or "custom"

    return TipMount(
        name=out_name,
        x=_f("GF_CARLA_TIP_X", base["x"]),
        y=_f("GF_CARLA_TIP_Y", base["y"]),
        z=_f("GF_CARLA_TIP_Z", base["z"]),
        pitch=_f("GF_CARLA_TIP_PITCH", base["pitch"]),
        yaw=_f("GF_CARLA_TIP_YAW", base["yaw"]),
        roll=_f("GF_CARLA_TIP_ROLL", base["roll"]),
        fov=_f("GF_CARLA_TIP_FOV", base["fov"]),
    )
