"""req.frame_ingest → hpp (behavior freeze; no .env)."""

from __future__ import annotations

import json
from pathlib import Path

from gf_codegen.compose.emit_build_cmake import emit_build_cmake
from gf_codegen.compose.emit_frame_ingest import (
    emit_frame_ingest,
    normalize_frame_ingest,
)


def test_normalize_defaults() -> None:
    cfg = normalize_frame_ingest({})
    assert cfg["frame_source"] == "none"
    assert cfg["pixel_format"] == "nv12"
    assert cfg["ego_source"] == "gateway"
    assert cfg["bridge"]["enabled"] is False
    assert "dry_run" not in cfg["bridge"]
    assert cfg["paths"]["frame"].endswith("runtime_ipc/front.yuv") or "runtime_ipc" in cfg["paths"]["frame"]
    assert "/tmp/gf_" not in cfg["paths"]["frame"]


def test_emit_frame_ingest_carla(tmp_path: Path) -> None:
    req = {
        "frame_ingest": {
            "frame_source": "carla_file",
            "perception_backend": "stub",
            "pixel_format": "nv12",
            "ego_source": "carla",
            "tip_transport": "shm",
            "active_source": "carla",
            "tip_slots": [{"id": "front", "w": 640, "h": 480, "pixel_format": "nv12"}],
            "bridge": {
                "enabled": True,
            },
            "paths": {
                "frame": "/tmp/gf_front.yuv",
                "cmd": "/tmp/gf_carla_cmd.json",
            },
        }
    }
    meta = emit_frame_ingest(req, tmp_path)
    hpp = Path(meta["hpp"]).read_text(encoding="utf-8")
    assert 'kFrameSource = "carla_file"' in hpp
    assert 'kPixelFormat = "nv12"' in hpp
    assert 'kEgoSource = "carla"' in hpp
    assert "kBridgeEnabled = true" in hpp
    assert 'kTipTransport = "shm"' in hpp
    assert 'kActiveSource = "carla"' in hpp
    assert 'kTipSlotFront = "gf.channel.front"' in hpp
    assert "kTipSlots" in hpp
    assert "kMountFov" in hpp
    assert "kBridgeDryRun" not in hpp
    assert "kDemoLaneChange" not in hpp
    assert "kFramePath" in hpp
    assert not (tmp_path / "frame_ingest.env").exists()
    assert "camera_contract" in meta
    cam = json.loads(Path(meta["camera_contract"]).read_text(encoding="utf-8"))
    assert cam["schema"] == "camera_contract/v1"
    assert cam["slots"][0]["slot_name"] == "gf.channel.front"


def test_normalize_active_source_enables_bridge() -> None:
    cfg = normalize_frame_ingest(
        {"frame_ingest": {"active_source": "carla", "ego_source": "carla"}}
    )
    assert cfg["active_source"] == "carla"
    assert cfg["frame_source"] == "carla_file"
    assert cfg["bridge"]["enabled"] is True


def test_normalize_none_disables_bridge() -> None:
    cfg = normalize_frame_ingest(
        {"frame_ingest": {"active_source": "none", "ego_source": "inject"}}
    )
    assert cfg["active_source"] == "none"
    assert cfg["ego_source"] == "inject"
    assert cfg["bridge"]["enabled"] is False


def test_normalize_tip_slots_default_front() -> None:
    cfg = normalize_frame_ingest(
        {"frame_ingest": {"bridge": {"enabled": True}, "frame_source": "carla_file"}}
    )
    # SOP default when video contract present: isp (SIL overrides via GF_FRAME_SOURCE)
    assert cfg["active_source"] == "isp"
    assert cfg["tip_transport"] == "shm"
    assert cfg["tip_slots"][0]["id"] == "front"


def test_normalize_synth_alias_to_colorbar() -> None:
    cfg = normalize_frame_ingest({"frame_ingest": {"active_source": "synth"}})
    assert cfg["active_source"] == "colorbar"
    assert cfg["frame_source"] == "colorbar"
    assert cfg["bridge"]["enabled"] is True


def test_normalize_tip_slots_default_isp() -> None:
    cfg = normalize_frame_ingest(
        {
            "frame_ingest": {
                "tip_slots": [{"id": "front", "w": 640, "h": 480}],
            }
        }
    )
    assert cfg["active_source"] == "isp"
    assert cfg["bridge"]["enabled"] is True


def test_legacy_tmp_paths_migrate_to_runtime_ipc(tmp_path: Path) -> None:
    cfg = normalize_frame_ingest(
        {
            "frame_ingest": {
                "paths": {
                    "frame": "/tmp/gf_front.yuv",
                    "cmd": "/tmp/gf_carla_cmd.json",
                }
            }
        },
        project_dir=tmp_path,
    )
    assert cfg["paths"]["frame"] == str(tmp_path / "runtime_ipc" / "front.yuv")
    assert cfg["paths"]["cmd"] == str(tmp_path / "runtime_ipc" / "carla_cmd.json")
    assert not cfg["paths"]["frame"].startswith("/tmp/gf_")


def test_legacy_rgb_path_migrates_to_yuv() -> None:
    cfg = normalize_frame_ingest(
        {"frame_ingest": {"paths": {"frame": "/tmp/gf_front.rgb"}, "pixel_format": "nv12"}}
    )
    assert cfg["paths"]["frame"].endswith("front.yuv")
    assert "/tmp/" not in cfg["paths"]["frame"]


def test_gf_build_cmake_no_frame_ingest_env(tmp_path: Path) -> None:
    out = tmp_path / "gf_build.cmake"
    emit_build_cmake(
        {
            "variant": "t",
            "runtime_modules": ["core"],
            "bindings": ["iceoryx"],
            "apps": ["perception/fcm"],
        },
        out,
        project_dir=tmp_path / "proj",
        repo_root=tmp_path,
    )
    text = out.read_text(encoding="utf-8")
    assert "frame_ingest.env" not in text
