"""Camera mount (extrinsics) for SIL carla tip module — **compose freeze only**.

Order (one geometry truth, no local preset table):
  1. Full ``GF_CAMERA_MOUNT_{X,Y,Z,PITCH,YAW,ROLL,FOV}`` from gf_frame_ingest
     (exported from ``frame_ingest_config.hpp``; legacy ``GF_CARLA_TIP_*`` accepted)
  2. Else ``camera_contract.json`` via ``GF_CAMERA_CONTRACT`` /
     ``$GF_PROJECT_DIR/generated/camera_contract.json``

Does **not** import carla_scenarios. Missing both → hard error.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Tuple

# Primary env keys; legacy GF_CARLA_TIP_* kept as read aliases.
_ENV_KEYS = (
    (("GF_CAMERA_MOUNT_X", "GF_CARLA_TIP_X"), "x"),
    (("GF_CAMERA_MOUNT_Y", "GF_CARLA_TIP_Y"), "y"),
    (("GF_CAMERA_MOUNT_Z", "GF_CARLA_TIP_Z"), "z"),
    (("GF_CAMERA_MOUNT_PITCH", "GF_CARLA_TIP_PITCH"), "pitch"),
    (("GF_CAMERA_MOUNT_YAW", "GF_CARLA_TIP_YAW"), "yaw"),
    (("GF_CAMERA_MOUNT_ROLL", "GF_CARLA_TIP_ROLL"), "roll"),
    (("GF_CAMERA_MOUNT_FOV", "GF_CARLA_TIP_FOV"), "fov"),
)
_REQUIRED = ("x", "y", "z", "pitch", "yaw", "roll", "fov")


@dataclass(frozen=True)
class CameraMount:
    """Vehicle-relative camera extrinsics (xyz + RPY deg + fov)."""

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


def _env_float(*keys: str) -> float | None:
    for key in keys:
        raw = os.environ.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _from_ingest_env() -> dict[str, Any] | None:
    vals: dict[str, Any] = {}
    for env_keys, field in _ENV_KEYS:
        v = _env_float(*env_keys)
        if v is None:
            return None
        vals[field] = v
    mid = (
        os.environ.get("GF_CAMERA_MOUNT_ID")
        or os.environ.get("GF_CARLA_TIP_MOUNT")
        or ""
    ).strip() or "1"
    vals["id"] = mid
    return vals


def _contract_path() -> Path | None:
    env = (os.environ.get("GF_CAMERA_CONTRACT") or "").strip()
    if env:
        p = Path(env).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return p if p.is_file() else None
    proj = (os.environ.get("GF_PROJECT_DIR") or "").strip()
    if proj:
        p = Path(proj).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        cand = p / "generated" / "camera_contract.json"
        return cand if cand.is_file() else None
    return None


def _from_camera_contract() -> tuple[dict[str, Any], Path] | None:
    path = _contract_path()
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    slots = data.get("slots") or []
    if not isinstance(slots, list) or not slots or not isinstance(slots[0], dict):
        return None
    mount = slots[0].get("mount")
    if not isinstance(mount, dict):
        return None
    out: dict[str, Any] = {"id": str(mount.get("id") or slots[0].get("id") or "1")}
    for k in _REQUIRED:
        if k not in mount or mount[k] is None:
            return None
        out[k] = float(mount[k])
    return out, path


def load_camera_mount() -> CameraMount:
    """Resolve mount from ingest env or camera_contract — never invent numbers."""
    base = _from_ingest_env()
    src = "GF_CAMERA_MOUNT_* (hpp/ingest)"
    if base is None:
        got = _from_camera_contract()
        if got is None:
            print(
                "[ERROR] camera_mount: need ingest GF_CAMERA_MOUNT_* or camera_contract.json\n"
                "  Under EM: gf_frame_ingest SetEnv from frame_ingest_config.hpp\n"
                "  Standalone: export GF_CAMERA_CONTRACT=…/generated/camera_contract.json\n"
                "  or GF_PROJECT_DIR=…/projects/oem_a/afc_no_uss",
                file=sys.stderr,
            )
            raise SystemExit(2)
        base, path = got
        src = str(path)

    out = CameraMount(
        name=str(base["id"]),
        x=float(base["x"]),
        y=float(base["y"]),
        z=float(base["z"]),
        pitch=float(base["pitch"]),
        yaw=float(base["yaw"]),
        roll=float(base["roll"]),
        fov=float(base["fov"]),
    )
    print(f"[carla_bridge] camera_mount {out.describe()} ← {src}", flush=True)
    return out


def scene_chase_pose() -> Tuple[float, float, float, float, float]:
    """Vehicle-relative chase cam: x, z, pitch, yaw, fov (overview only)."""
    return (-6.5, 3.0, -12.0, 0.0, 90.0)


__all__ = [
    "CameraMount",
    "load_camera_mount",
    "scene_chase_pose",
]
