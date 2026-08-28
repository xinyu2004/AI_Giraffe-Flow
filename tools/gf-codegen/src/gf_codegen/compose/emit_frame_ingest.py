"""Emit compile-time frame_ingest / optional video-contract config.

Product path: frame_ingest_config.hpp (C++ ingest / FCM / gateway / GfChannel).
Also exports camera_contract.json:
  - projects/<product>/generated/camera_contract.json
  - carla_scenarios/config/<product>/camera_contract.json  (host; GF_CAMERA_CONTRACT)
carla_scenarios/ is never imported by SIL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


_VALID_SOURCES = frozenset({"none", "synth", "colorbar", "file", "carla_file"})
_VALID_BACKENDS = frozenset({"stub", "onnx"})
_VALID_PIXEL = frozenset({"nv12", "nv21", "yuv422", "yuv444", "rgb8"})
_VALID_EGO = frozenset({"gateway", "inject", "carla", "stub", "channel", "vehicle_bus"})
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

# Optional replay tee only (not vehicle/cmd/truth json IPC).
_IPC_FILES = {
    "frame": "front.yuv",
}
_LEGACY_TMP_NAMES = {
    "/tmp/gf_front.yuv": "front.yuv",
    "/tmp/gf_front.rgb": "front.yuv",
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
    try:
        fps = int(raw.get("fps") or 0)
    except (TypeError, ValueError):
        fps = 0
    if fps < 0:
        fps = 0
    if fps > 240:
        fps = 240
    return {
        "id": sid,
        "w": w,
        "h": h,
        "pixel_format": pixel,
        "buffers": buffers,
        "fps": fps,
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
        raw.get("camera_transport")
        or raw.get("channel_transport")
        or "shm"
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
        slots_probe = raw.get("camera_slots") or raw.get("channel_slots")
        if isinstance(slots_probe, list) and slots_probe:
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

    slots_raw = raw.get("camera_slots") or raw.get("channel_slots")
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

    # Replay/file only: optional frame path. Live CARLA uses GfChannel — no default front.yuv.
    frame_path = ""
    if paths.get("frame") is not None and str(paths.get("frame")).strip():
        frame_path = _resolve_ipc_path(str(paths["frame"]), "frame", proj)
        if frame_path.endswith(".rgb") and pixel != "rgb8":
            frame_path = frame_path[: -4] + ".yuv"
    elif active in ("replay", "file") or source == "file":
        # Explicit replay sources without paths.frame still get a conventional name
        # under runtime_ipc (host tool / frame_replay); not product live IPC.
        frame_path = _resolve_ipc_path(None, "frame", proj)

    if active in ("carla", "replay", "synth", "colorbar", "isp", "file"):
        bridge_enabled = True
    elif active == "none":
        bridge_enabled = False
    else:
        bridge_enabled = bool(bridge.get("enabled", False))

    ch = raw.get("channels") if isinstance(raw.get("channels"), dict) else {}
    vehicle_state_slot = str(ch.get("vehicle_state") or "gf.channel.vehicle_state")
    vehicle_cmd_slot = str(ch.get("vehicle_cmd") or "gf.channel.vehicle_cmd")
    fake_perc_slot = str(ch.get("fake_perc") or "gf.channel.fake_perc")

    return {
        "frame_source": source,
        "perception_backend": backend,
        "pixel_format": pixel,
        "ego_source": ego,
        "frame_w": frame_w,
        "frame_h": frame_h,
        "camera_transport": transport,
        "active_source": active,
        "camera_slots": slots,
        "bridge": {
            "enabled": bridge_enabled,
        },
        "paths": {
            "frame": frame_path,
        },
        "channels": {
            "vehicle_state": vehicle_state_slot,
            "vehicle_cmd": vehicle_cmd_slot,
            "fake_perc": fake_perc_slot,
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
    ch = cfg.get("channels") or {}
    slots = cfg["camera_slots"]
    front = slots[0]
    mount = front.get("mount") or _normalize_mount({})
    lines = [
        "// Generated by gf_codegen.compose — do not edit by hand",
        "// Optional video contract: change req.frame_ingest → compose → rebuild.",
        "// GfChannel: general shm (camera + boundary blobs). No carla_*.json IPC.",
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
        f"inline constexpr const char* kCameraTransport = {_c_str(cfg['camera_transport'])};",
        f"inline constexpr const char* kActiveSource = {_c_str(cfg['active_source'])};",
        f"inline constexpr const char* kCameraSlotFront = {_c_str(_slot_name(str(front['id'])))};",
        f"inline constexpr std::uint32_t kCameraFpsFront = {int(front.get('fps') or 0)}u;",
        f"inline constexpr std::uint32_t kCameraSlotCount = {len(slots)}u;",
        f"inline constexpr const char* kFramePath = {_c_str(p.get('frame') or '')};",
        f"inline constexpr const char* kVehicleStateSlot = {_c_str(str(ch.get('vehicle_state') or 'gf.channel.vehicle_state'))};",
        f"inline constexpr const char* kVehicleCmdSlot = {_c_str(str(ch.get('vehicle_cmd') or 'gf.channel.vehicle_cmd'))};",
        f"inline constexpr const char* kFakePercSlot = {_c_str(str(ch.get('fake_perc') or 'gf.channel.fake_perc'))};",
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
        "struct CameraSlotFreeze {",
        "  const char* id;",
        "  const char* slot_name;",
        "  std::uint32_t w;",
        "  std::uint32_t h;",
        "  const char* pixel_format;",
        "  std::uint32_t buffers;",
        "  std::uint32_t fps;  // 0 = unspecified; physical ceiling for expect_fps",
        "};",
        "",
        "inline constexpr CameraSlotFreeze kCameraSlots[] = {",
    ]
    for s in slots:
        sid = str(s["id"])
        slot_name = _slot_name(sid)
        lines.append(
            "  {"
            f"{_c_str(sid)}, {_c_str(slot_name)}, "
            f"{int(s['w'])}u, {int(s['h'])}u, "
            f"{_c_str(s['pixel_format'])}, {int(s['buffers'])}u, "
            f"{int(s.get('fps') or 0)}u"
            "},"
        )
    lines += [
        "};",
        "",
        "inline constexpr std::size_t kCameraSlotsSize =",
        "    sizeof(kCameraSlots) / sizeof(kCameraSlots[0]);",
        "",
        "}  // namespace gf_gen::frame_ingest",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def product_key(req: dict[str, Any], project_dir: Path) -> str:
    """Lowercase product id for export path config/<product>/ (from req.product)."""
    raw = str(req.get("product") or "").strip()
    if raw:
        return raw.lower()
    return project_dir.name.lower() or "default"


def scenarios_camera_contract_path(project_dir: Path, product: str) -> Optional[Path]:
    """carla_scenarios/config/<product>/camera_contract.json if scenarios tree exists."""
    projects = project_dir.parent
    repo = projects.parent if projects.name == "projects" else project_dir.parent
    scenarios = repo / "carla_scenarios"
    if not scenarios.is_dir():
        return None
    return scenarios / "config" / product / "camera_contract.json"


def emit_camera_contract_json(
    cfg: dict[str, Any], out_path: Path, *, product: str = ""
) -> None:
    """Write camera_contract.json for carla_scenarios / tools (not board runtime)."""
    slots_out = []
    for s in cfg["camera_slots"]:
        m = s.get("mount") or _normalize_mount({})
        slots_out.append(
            {
                "id": s["id"],
                "slot_name": _slot_name(str(s["id"])),
                "w": int(s["w"]),
                "h": int(s["h"]),
                "pixel_format": s["pixel_format"],
                "buffers": int(s["buffers"]),
                "fps": int(s.get("fps") or 0),
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
        "product": product,
        "active_source": cfg["active_source"],
        "ego_source": cfg["ego_source"],
        "camera_transport": cfg["camera_transport"],
        "slots": slots_out,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def emit_frame_ingest(req: dict[str, Any], gen_dir: Path) -> dict[str, str]:
    """Emit hpp (+ camera_contract.json to generated/ and carla_scenarios/config/<product>/)."""
    project_dir = gen_dir.parent
    product = product_key(req, project_dir)
    cfg = normalize_frame_ingest(req, project_dir=project_dir)
    # replay/file only: ensure parent of the yuv path. GfChannel (carla/isp/colorbar)
    # must not recreate empty projects/*/runtime_ipc.
    frame_path = ""
    if isinstance(cfg.get("paths"), dict):
        frame_path = str(cfg["paths"].get("frame") or "").strip()
    ipc = project_dir / "runtime_ipc"
    if frame_path:
        Path(frame_path).parent.mkdir(parents=True, exist_ok=True)
    elif ipc.is_dir():
        try:
            if not any(ipc.iterdir()):
                ipc.rmdir()
        except OSError:
            pass
    hpp = gen_dir / "include" / "gf_gen" / "frame_ingest_config.hpp"
    emit_frame_ingest_hpp(cfg, hpp)
    legacy_env = gen_dir / "frame_ingest.env"
    if legacy_env.is_file():
        legacy_env.unlink()
    out: dict[str, str] = {"hpp": str(hpp), "product": product}
    # Only emit camera info when video contract is enabled
    if cfg["bridge"]["enabled"] and cfg["active_source"] != "none":
        cam = gen_dir / "camera_contract.json"
        emit_camera_contract_json(cfg, cam, product=product)
        out["camera_contract"] = str(cam)
        host = scenarios_camera_contract_path(project_dir, product)
        if host is not None:
            emit_camera_contract_json(cfg, host, product=product)
            out["camera_contract_host"] = str(host)
    else:
        stale = gen_dir / "camera_contract.json"
        if stale.is_file():
            stale.unlink()
    return out
