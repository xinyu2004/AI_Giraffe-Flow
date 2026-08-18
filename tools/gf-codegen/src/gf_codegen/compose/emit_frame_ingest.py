"""Emit compile-time frame_ingest / optional video-contract config.

Product path: frame_ingest_config.hpp (C++ ingest / FCM / gateway / GfChannel).
Optional export: camera_contract.json for carla_scenarios (read-only consumer).
carla_scenarios/ is never imported by SIL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_VALID_SOURCES = frozenset({"none", "synth", "colorbar", "file", "carla_file"})
_VALID_BACKENDS = frozenset({"stub", "onnx"})
_VALID_PIXEL = frozenset({"nv12", "nv21", "yuv422", "yuv444", "rgb8"})
_VALID_EGO = frozenset({"gateway", "inject", "carla"})
_VALID_TRANSPORT = frozenset({"shm", "file"})
_VALID_ACTIVE = frozenset(
    {"none", "carla", "isp", "replay", "synth", "colorbar", "file"}
)

# Default windshield mount (perception contract; same numbers for carla/isp).
_DEFAULT_MOUNT: dict[str, float] = {
    "x": 0.55,
    "y": 0.0,
    "z": 1.35,
    "pitch": -5.0,
    "yaw": 0.0,
    "roll": 0.0,
    "fov": 100.0,
}

# CARLA SIL file-IPC only (not GfChannel). Live under project/runtime_ipc/ — never /tmp.
_IPC_FILES = {
    "frame": "front.yuv",
    "cmd": "carla_cmd.json",
    "ego": "carla_ego.json",
    "truth": "carla_truth.json",
    "ctrl": "planning_ctrl.json",
}
_LEGACY_TMP_NAMES = {
    "/tmp/gf_front.yuv": "front.yuv",
    "/tmp/gf_front.rgb": "front.yuv",
    "/tmp/gf_carla_cmd.json": "carla_cmd.json",
    "/tmp/gf_carla_ego.json": "carla_ego.json",
    "/tmp/gf_carla_truth.json": "carla_truth.json",
    "/tmp/gf_planning_ctrl.json": "planning_ctrl.json",
}


def _ipc_root(project_dir: Path | None) -> Path:
    if project_dir is not None:
        return Path(project_dir) / "runtime_ipc"
    return Path("runtime_ipc")


def _resolve_ipc_path(raw: str | None, key: str, project_dir: Path | None) -> str:
    """Map missing/legacy /tmp paths → project/runtime_ipc/<name>."""
    root = _ipc_root(project_dir)
    default_name = _IPC_FILES[key]
    if not raw or not str(raw).strip():
        return str(root / default_name)
    s = str(raw).strip()
    if s in _LEGACY_TMP_NAMES:
        return str(root / _LEGACY_TMP_NAMES[s])
    if s.startswith("/tmp/gf_"):
        return str(root / Path(s).name.removeprefix("gf_"))
    p = Path(s)
    if not p.is_absolute():
        # Relative → under project (or cwd runtime_ipc if no project_dir)
        if project_dir is not None:
            return str((Path(project_dir) / p).resolve())
        return str(p)
    return s


def _normalize_mount(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    out: dict[str, Any] = {
        "id": str(raw.get("id") or raw.get("preset") or "1").strip() or "1",
    }
    for k, default in _DEFAULT_MOUNT.items():
        try:
            out[k] = float(raw[k]) if k in raw and raw[k] is not None else float(default)
        except (TypeError, ValueError):
            out[k] = float(default)
    return out


def _normalize_slot(
    raw: Any,
    *,
    default_id: str,
    default_w: int,
    default_h: int,
    default_pixel: str,
    default_mount: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    sid = str(raw.get("id") or default_id).strip() or default_id
    pixel = str(raw.get("pixel_format") or default_pixel).strip().lower() or default_pixel
    if pixel not in _VALID_PIXEL:
        pixel = default_pixel
    w = int(raw.get("w") or default_w)
    h = int(raw.get("h") or default_h)
    if w < 16:
        w = default_w
    if h < 16:
        h = default_h
    buffers = 2  # AB double-buffer; not a product knob
    mount = _normalize_mount(raw.get("mount") if "mount" in raw else (default_mount or {}))
    return {
        "id": sid,
        "w": w,
        "h": h,
        "pixel_format": pixel,
        "buffers": buffers,
        "mount": mount,
    }


def normalize_frame_ingest(
    req: dict[str, Any],
    *,
    project_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Return a fully filled frame_ingest dict (defaults = off / none).

    Missing / empty frame_ingest → optional video contract absent (active=none).
    File-IPC paths default under ``<project>/runtime_ipc/`` (not /tmp).
    """
    raw = req.get("frame_ingest")
    if not isinstance(raw, dict):
        raw = {}
    bridge = raw.get("bridge") if isinstance(raw.get("bridge"), dict) else {}
    paths = raw.get("paths") if isinstance(raw.get("paths"), dict) else {}
    proj = Path(project_dir) if project_dir else None

    backend = "stub"  # FCM-internal; not a product / gf-config knob

    pixel = str(raw.get("pixel_format") or "nv12").strip().lower() or "nv12"
    if pixel not in _VALID_PIXEL:
        pixel = "nv12"

    ego = str(raw.get("ego_source") or "gateway").strip().lower() or "gateway"
    if ego not in _VALID_EGO:
        ego = "gateway"

    frame_w = int(raw.get("frame_w") or bridge.get("frame_w") or 640)
    frame_h = int(raw.get("frame_h") or bridge.get("frame_h") or 480)
    if frame_w < 16:
        frame_w = 640
    if frame_h < 16:
        frame_h = 480

    transport = str(
        raw.get("channel_transport") or raw.get("tip_transport") or "shm"
    ).strip().lower() or "shm"
    if transport not in _VALID_TRANSPORT:
        transport = "shm"

    active = str(raw.get("active_source") or "").strip().lower()
    source = str(raw.get("frame_source") or "").strip() or ""
    if active == "synth":
        active = "colorbar"
    if source == "synth":
        source = "colorbar"
    if not active:
        # SOP default when video contract present: isp (SIL overrides via GF_FRAME_SOURCE)
        if isinstance(raw.get("tip_slots") or raw.get("channel_slots"), list) and (
            raw.get("tip_slots") or raw.get("channel_slots")
        ):
            active = "isp"
        elif source in ("carla_file", "file") or bool(bridge.get("enabled", False)):
            active = "isp"
        elif source in ("synth", "colorbar"):
            active = "colorbar"
        elif source == "none" or not source:
            active = "none"
        else:
            active = "none"
    if active not in _VALID_ACTIVE:
        active = "none"
    if active == "synth":
        active = "colorbar"

    if not source or source not in _VALID_SOURCES:
        if active == "carla":
            source = "carla_file"
        elif active in ("replay", "file"):
            source = "file"
        elif active in ("synth", "colorbar"):
            source = "colorbar"
        elif active == "isp":
            source = "none"  # ISP module; no file IPC source
        else:
            source = "none"

    top_mount = _normalize_mount(raw.get("mount") if isinstance(raw.get("mount"), dict) else {})

    slots_raw = raw.get("tip_slots") or raw.get("channel_slots")
    slots: list[dict[str, Any]] = []
    if isinstance(slots_raw, list) and slots_raw:
        for i, item in enumerate(slots_raw):
            slots.append(
                _normalize_slot(
                    item,
                    default_id="front" if i == 0 else f"cam{i}",
                    default_w=frame_w,
                    default_h=frame_h,
                    default_pixel=pixel,
                    default_mount=top_mount,
                )
            )
    else:
        slots.append(
            _normalize_slot(
                {
                    "id": "front",
                    "w": frame_w,
                    "h": frame_h,
                    "pixel_format": pixel,
                    "mount": top_mount,
                },
                default_id="front",
                default_w=frame_w,
                default_h=frame_h,
                default_pixel=pixel,
                default_mount=top_mount,
            )
        )

    frame_path = _resolve_ipc_path(
        str(paths["frame"]) if paths.get("frame") is not None else None,
        "frame",
        proj,
    )
    if frame_path.endswith(".rgb") and pixel != "rgb8":
        frame_path = frame_path[: -4] + ".yuv"

    if active in ("carla", "replay", "synth", "colorbar", "isp", "file"):
        bridge_enabled = True
    elif active == "none":
        bridge_enabled = False
    else:
        bridge_enabled = bool(bridge.get("enabled", False))

    return {
        "frame_source": source,
        "perception_backend": backend,
        "pixel_format": pixel,
        "ego_source": ego,
        "frame_w": frame_w,
        "frame_h": frame_h,
        "tip_transport": transport,
        "active_source": active,
        "tip_slots": slots,
        "bridge": {
            "enabled": bridge_enabled,
        },
        "paths": {
            "frame": frame_path,
            "cmd": _resolve_ipc_path(
                str(paths["cmd"]) if paths.get("cmd") is not None else None, "cmd", proj
            ),
            "ego": _resolve_ipc_path(
                str(paths["ego"]) if paths.get("ego") is not None else None, "ego", proj
            ),
            "truth": _resolve_ipc_path(
                str(paths["truth"]) if paths.get("truth") is not None else None,
                "truth",
                proj,
            ),
            "ctrl": _resolve_ipc_path(
                str(paths["ctrl"]) if paths.get("ctrl") is not None else None,
                "ctrl",
                proj,
            ),
        },
    }


def _c_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _cxx_bool(v: bool) -> str:
    return "true" if v else "false"


def _slot_name(sid: str) -> str:
    return f"gf.channel.{sid}"


def emit_frame_ingest_hpp(cfg: dict[str, Any], out_path: Path) -> None:
    b = cfg["bridge"]
    p = cfg["paths"]
    slots = cfg["tip_slots"]
    front = slots[0]
    mount = front.get("mount") or _normalize_mount({})
    lines = [
        "// Generated by gf_codegen.compose — do not edit by hand",
        "// Optional video contract: change req.frame_ingest → compose → rebuild.",
        "// GfChannel: gf_frame_ingest + middleware/bindings/gf_channel.",
        "#pragma once",
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace gf_gen::frame_ingest {",
        "",
        f"inline constexpr const char* kFrameSource = {_c_str(cfg['frame_source'])};",
        f"inline constexpr const char* kPerceptionBackend = {_c_str(cfg['perception_backend'])};",
        f"inline constexpr const char* kPixelFormat = {_c_str(cfg['pixel_format'])};",
        f"inline constexpr const char* kEgoSource = {_c_str(cfg['ego_source'])};",
        f"inline constexpr std::uint32_t kFrameW = {int(cfg['frame_w'])}u;",
        f"inline constexpr std::uint32_t kFrameH = {int(cfg['frame_h'])}u;",
        f"inline constexpr bool kBridgeEnabled = {_cxx_bool(b['enabled'])};",
        f"inline constexpr const char* kTipTransport = {_c_str(cfg['tip_transport'])};",
        f"inline constexpr const char* kChannelTransport = kTipTransport;",
        f"inline constexpr const char* kActiveSource = {_c_str(cfg['active_source'])};",
        f"inline constexpr const char* kTipSlotFront = {_c_str(_slot_name(str(front['id'])))};",
        f"inline constexpr const char* kChannelSlotFront = kTipSlotFront;",
        f"inline constexpr std::uint32_t kTipSlotCount = {len(slots)}u;",
        f"inline constexpr const char* kFramePath = {_c_str(p['frame'])};",
        f"inline constexpr const char* kCmdPath = {_c_str(p['cmd'])};",
        f"inline constexpr const char* kEgoPath = {_c_str(p['ego'])};",
        f"inline constexpr const char* kTruthPath = {_c_str(p['truth'])};",
        f"inline constexpr const char* kCtrlPath = {_c_str(p['ctrl'])};",
        "",
        f"inline constexpr const char* kMountId = {_c_str(str(mount['id']))};",
        f"inline constexpr double kMountX = {float(mount['x'])};",
        f"inline constexpr double kMountY = {float(mount['y'])};",
        f"inline constexpr double kMountZ = {float(mount['z'])};",
        f"inline constexpr double kMountPitch = {float(mount['pitch'])};",
        f"inline constexpr double kMountYaw = {float(mount['yaw'])};",
        f"inline constexpr double kMountRoll = {float(mount['roll'])};",
        f"inline constexpr double kMountFov = {float(mount['fov'])};",
        "",
        "struct TipSlotFreeze {",
        "  const char* id;",
        "  const char* slot_name;",
        "  std::uint32_t w;",
        "  std::uint32_t h;",
        "  const char* pixel_format;",
        "  std::uint32_t buffers;",
        "};",
        "",
        "inline constexpr TipSlotFreeze kTipSlots[] = {",
    ]
    for s in slots:
        sid = str(s["id"])
        slot_name = _slot_name(sid)
        lines.append(
            "  {"
            f"{_c_str(sid)}, {_c_str(slot_name)}, "
            f"{int(s['w'])}u, {int(s['h'])}u, "
            f"{_c_str(s['pixel_format'])}, {int(s['buffers'])}u"
            "},"
        )
    lines += [
        "};",
        "",
        "inline constexpr std::size_t kTipSlotsSize =",
        "    sizeof(kTipSlots) / sizeof(kTipSlots[0]);",
        "",
        "}  // namespace gf_gen::frame_ingest",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def emit_camera_contract_json(cfg: dict[str, Any], out_path: Path) -> None:
    """Write camera_contract.json for carla_scenarios / tools (not board runtime)."""
    slots_out = []
    for s in cfg["tip_slots"]:
        m = s.get("mount") or _normalize_mount({})
        slots_out.append(
            {
                "id": s["id"],
                "slot_name": _slot_name(str(s["id"])),
                "w": int(s["w"]),
                "h": int(s["h"]),
                "pixel_format": s["pixel_format"],
                "buffers": int(s["buffers"]),
                "mount": {
                    "id": m["id"],
                    "x": float(m["x"]),
                    "y": float(m["y"]),
                    "z": float(m["z"]),
                    "pitch": float(m["pitch"]),
                    "yaw": float(m["yaw"]),
                    "roll": float(m["roll"]),
                    "fov": float(m["fov"]),
                },
            }
        )
    doc = {
        "schema": "camera_contract/v1",
        "active_source": cfg["active_source"],
        "ego_source": cfg["ego_source"],
        "channel_transport": cfg["tip_transport"],
        "slots": slots_out,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def emit_frame_ingest(req: dict[str, Any], gen_dir: Path) -> dict[str, str]:
    """Emit hpp (+ optional camera_contract.json). Returns output paths."""
    project_dir = gen_dir.parent
    cfg = normalize_frame_ingest(req, project_dir=project_dir)
    ipc = project_dir / "runtime_ipc"
    ipc.mkdir(parents=True, exist_ok=True)
    gitignore = ipc / ".gitignore"
    if not gitignore.is_file():
        gitignore.write_text("# SIL file-IPC scratch (not GfChannel)\n*\n!.gitignore\n", encoding="utf-8")
    hpp = gen_dir / "include" / "gf_gen" / "frame_ingest_config.hpp"
    emit_frame_ingest_hpp(cfg, hpp)
    legacy_env = gen_dir / "frame_ingest.env"
    if legacy_env.is_file():
        legacy_env.unlink()
    out: dict[str, str] = {"hpp": str(hpp)}
    # Only emit camera info when video contract is enabled
    if cfg["bridge"]["enabled"] and cfg["active_source"] != "none":
        cam = gen_dir / "camera_contract.json"
        emit_camera_contract_json(cfg, cam)
        out["camera_contract"] = str(cam)
    else:
        stale = gen_dir / "camera_contract.json"
        if stale.is_file():
            stale.unlink()
    return out
