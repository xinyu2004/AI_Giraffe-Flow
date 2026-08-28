"""Camera contract for host (scenario_client / giraffe_client).

真源：gf-config Verify/compose → 导出
  ``carla_scenarios/config/<product>/camera_contract.json``

上位机用 ``GF_CAMERA_CONTRACT``（路径或短名），不使用 ``GF_PROJECT_DIR``。

解析：
  - ``GF_CAMERA_CONTRACT=config/afc/camera_contract.json`` → 该文件
  - ``GF_CAMERA_CONTRACT=afc`` → ``config/afc/camera_contract.json``
  - 未设置 → 默认 ``config/afc/camera_contract.json``
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple


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


@dataclass(frozen=True)
class HostCamera:
    """One camera slot from product camera_contract (maps to gf.channel.<id>)."""

    id: str
    enabled: bool
    w: int
    h: int
    pixel_format: str
    mount: CameraMount
    slot_name: str

    @property
    def channel_slot(self) -> str:
        return self.slot_name or f"gf.channel.{self.id}"


def _scenarios_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_under_bases(raw: str) -> Path | None:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p if p.is_file() else None
    for base in (Path.cwd(), _scenarios_root()):
        c = (base / p).resolve()
        if c.is_file():
            return c
    return None


def camera_contract_path() -> Path | None:
    """Resolve GF_CAMERA_CONTRACT to a camera_contract.json file."""
    raw = (os.environ.get("GF_CAMERA_CONTRACT") or "afc").strip()
    if not raw:
        raw = "afc"

    # Short product name → config/<name>/camera_contract.json
    if "/" not in raw and "\\" not in raw and not raw.endswith(".json"):
        raw = f"config/{raw.lower()}/camera_contract.json"

    return _resolve_under_bases(raw)


def _require_float(mount: dict[str, Any], key: str, path: Path) -> float:
    if key not in mount or mount[key] is None:
        raise SystemExit(f"[ERROR] camera_contract missing mount.{key} in {path}")
    try:
        return float(mount[key])
    except (TypeError, ValueError) as e:
        raise SystemExit(
            f"[ERROR] camera_contract mount.{key}={mount[key]!r} not a number ({path})"
        ) from e


def _missing_hint() -> str:
    env = (os.environ.get("GF_CAMERA_CONTRACT") or "").strip() or "(default afc)"
    return "\n".join(
        [
            "[ERROR] camera_contract.json not found for host",
            f"  GF_CAMERA_CONTRACT={env!r}",
            "  examples:",
            "    export GF_CAMERA_CONTRACT=afc",
            "    export GF_CAMERA_CONTRACT=config/afc/camera_contract.json",
            "  -> authoring PC: gf-config Verify (compose exports config/<product>/)",
            "  上位机不使用 GF_PROJECT_DIR；合同真源是 compose 导出物",
        ]
    )


def _parse_slot(raw: dict[str, Any], path: Path) -> HostCamera:
    cid = str(raw.get("id") or "").strip()
    if not cid:
        raise SystemExit(f"[ERROR] camera_contract slot missing id ({path})")
    mount_raw = raw.get("mount")
    if not isinstance(mount_raw, dict):
        raise SystemExit(f"[ERROR] camera_contract {cid}: mount missing ({path})")
    mount = CameraMount(
        name=str(mount_raw.get("id") or cid),
        x=_require_float(mount_raw, "x", path),
        y=_require_float(mount_raw, "y", path),
        z=_require_float(mount_raw, "z", path),
        pitch=_require_float(mount_raw, "pitch", path),
        yaw=_require_float(mount_raw, "yaw", path),
        roll=_require_float(mount_raw, "roll", path),
        fov=_require_float(mount_raw, "fov", path),
    )
    slot_name = str(raw.get("slot_name") or f"gf.channel.{cid}").strip()
    return HostCamera(
        id=cid,
        enabled=bool(raw.get("enabled", True)),
        w=int(raw.get("w") or 640),
        h=int(raw.get("h") or 480),
        pixel_format=str(raw.get("pixel_format") or "nv12"),
        mount=mount,
        slot_name=slot_name,
    )


_CAMS_CACHE: dict[str, List[HostCamera]] = {}
_MOUNT_CACHE: dict[str, CameraMount] = {}


def reset_camera_contract_cache() -> None:
    """Tests only: drop memo so the next load hits disk."""
    _CAMS_CACHE.clear()
    _MOUNT_CACHE.clear()


def load_host_cameras(*, enabled_only: bool = True) -> List[HostCamera]:
    """All slots from camera_contract (N 路由 compose 决定). Cached per path."""
    path = camera_contract_path()
    if path is None:
        print(_missing_hint(), file=sys.stderr)
        raise SystemExit(2)
    key = f"{path.resolve()}|{int(enabled_only)}"
    hit = _CAMS_CACHE.get(key)
    if hit is not None:
        return list(hit)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"[ERROR] camera_contract: cannot read {path}: {e}") from e
    slots = data.get("slots")
    if not isinstance(slots, list) or not slots:
        raise SystemExit(f"[ERROR] camera_contract: no slots[] in {path}")
    out = [_parse_slot(s, path) for s in slots if isinstance(s, dict)]
    if enabled_only:
        out = [c for c in out if c.enabled]
    if not out:
        raise SystemExit(f"[ERROR] camera_contract: no enabled slots in {path}")
    prod = data.get("product") or path.parent.name
    print(
        f"[cameras] product={prod} {len(out)} slot(s) <- {path}: "
        + ", ".join(c.id for c in out),
        flush=True,
    )
    _CAMS_CACHE[key] = list(out)
    return list(out)


def load_camera_mount() -> CameraMount:
    """Front (or first) mount — scenario pygame / single-cam callers."""
    path = camera_contract_path()
    key = str(path.resolve()) if path is not None else ""
    hit = _MOUNT_CACHE.get(key)
    if hit is not None:
        return hit
    cams = load_host_cameras(enabled_only=True)
    front = next((c for c in cams if c.id == "front"), cams[0])
    print(f"[camera_mount] {front.mount.describe()} <- contract", flush=True)
    _MOUNT_CACHE[key] = front.mount
    return front.mount


def scene_chase_pose() -> Tuple[float, float, float, float, float]:
    return (-6.5, 3.0, -12.0, 0.0, 90.0)


def host_cameras_path() -> Optional[Path]:
    return camera_contract_path()


__all__ = [
    "CameraMount",
    "HostCamera",
    "camera_contract_path",
    "host_cameras_path",
    "load_camera_mount",
    "load_host_cameras",
    "reset_camera_contract_cache",
    "scene_chase_pose",
]
