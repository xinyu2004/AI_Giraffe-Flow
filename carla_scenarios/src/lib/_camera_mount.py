"""Camera mount (extrinsics) — **only** from SKU ``camera_contract.json``.

Truth: gf-config → compose → ``generated/camera_contract.json``.
No local presets, no ``GF_CAMERA_MOUNT_*`` authoring here.

Resolve path (first hit):
  1. ``GF_CAMERA_CONTRACT`` — absolute/relative file path
  2. ``$GF_PROJECT_DIR/generated/camera_contract.json``
  3. Repo-relative ``projects/oem_a/afc_no_uss/generated/camera_contract.json``
     (when this tree sits next to ``projects/``)

Missing / incomplete contract → hard error (do not invent numbers).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Tuple

_REQUIRED_MOUNT = ("x", "y", "z", "pitch", "yaw", "roll", "fov")


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


def _scenarios_root() -> Path:
    # …/carla_scenarios/src/lib/_camera_mount.py → carla_scenarios/
    return Path(__file__).resolve().parents[2]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(raw: str, *, want_file: bool) -> Path | None:
    """Resolve absolute or relative path against cwd and carla_scenarios root."""
    p = Path(raw).expanduser()
    bases = (Path.cwd(), _scenarios_root())
    cands = [p] if p.is_absolute() else [b / p for b in bases]
    for c in cands:
        try:
            r = c.resolve()
        except OSError:
            continue
        if want_file and r.is_file():
            return r
        if not want_file and r.is_dir():
            return r
    return None


def camera_contract_path() -> Path | None:
    """Return path to camera_contract.json if it exists, else None.

    If ``GF_CAMERA_CONTRACT`` / ``GF_PROJECT_DIR`` is set, do **not** fall back to
    the repo-default SKU path (wrong dir must fail loudly).
    """
    env = (os.environ.get("GF_CAMERA_CONTRACT") or "").strip()
    if env:
        return _resolve_path(env, want_file=True)

    proj = (os.environ.get("GF_PROJECT_DIR") or "").strip()
    if proj:
        root = _resolve_path(proj, want_file=False)
        if root is None:
            return None
        cand = root / "generated" / "camera_contract.json"
        return cand if cand.is_file() else None

    cand = (
        _repo_root()
        / "projects"
        / "oem_a"
        / "afc_no_uss"
        / "generated"
        / "camera_contract.json"
    )
    return cand if cand.is_file() else None


def _missing_contract_hint() -> str:
    env = (os.environ.get("GF_CAMERA_CONTRACT") or "").strip()
    proj = (os.environ.get("GF_PROJECT_DIR") or "").strip()
    lines = ["[ERROR] camera_mount: no camera_contract.json"]
    if env:
        lines.append(f"  GF_CAMERA_CONTRACT={env!r} not found as a file")
    elif proj:
        lines.append(f"  GF_PROJECT_DIR={proj!r} has no generated/camera_contract.json")
        lines.append("  → run gf-config Verify / compose for that SKU first")
    else:
        lines.append("  Compose SKU first, then set one of:")
        lines.append("    export GF_CAMERA_CONTRACT=/path/to/generated/camera_contract.json")
        lines.append("    export GF_PROJECT_DIR=/path/to/projects/oem_a/afc_no_uss")
        lines.append(
            "  (unset env also looks for projects/oem_a/afc_no_uss/generated/camera_contract.json)"
        )
    return "\n".join(lines)


def _require_float(mount: dict[str, Any], key: str, path: Path) -> float:
    if key not in mount or mount[key] is None:
        raise SystemExit(
            f"[ERROR] camera_contract missing mount.{key} in {path} "
            f"(re-compose after gf-config camera edit)"
        )
    try:
        return float(mount[key])
    except (TypeError, ValueError) as e:
        raise SystemExit(
            f"[ERROR] camera_contract mount.{key}={mount[key]!r} not a number ({path})"
        ) from e


def load_camera_mount() -> CameraMount:
    """Load front-slot camera mount from camera_contract.json only."""
    path = camera_contract_path()
    if path is None:
        print(_missing_contract_hint(), file=sys.stderr)
        raise SystemExit(2)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"[ERROR] camera_mount: cannot read {path}: {e}") from e

    slots = data.get("slots")
    if not isinstance(slots, list) or not slots:
        raise SystemExit(f"[ERROR] camera_mount: no slots[] in {path}")
    slot = slots[0] if isinstance(slots[0], dict) else {}
    mount = slot.get("mount")
    if not isinstance(mount, dict) or not mount:
        raise SystemExit(f"[ERROR] camera_mount: slots[0].mount missing in {path}")

    name = str(mount.get("id") or slot.get("id") or "front").strip() or "front"
    out = CameraMount(
        name=name,
        x=_require_float(mount, "x", path),
        y=_require_float(mount, "y", path),
        z=_require_float(mount, "z", path),
        pitch=_require_float(mount, "pitch", path),
        yaw=_require_float(mount, "yaw", path),
        roll=_require_float(mount, "roll", path),
        fov=_require_float(mount, "fov", path),
    )
    print(f"[camera_mount] {out.describe()} ← {path}", flush=True)
    return out


def scene_chase_pose() -> Tuple[float, float, float, float, float]:
    """Scene overview cam only (not product camera). Vehicle-relative x,z,pitch,yaw,fov."""
    return (-6.5, 3.0, -12.0, 0.0, 90.0)


__all__ = [
    "CameraMount",
    "camera_contract_path",
    "load_camera_mount",
    "scene_chase_pose",
]
