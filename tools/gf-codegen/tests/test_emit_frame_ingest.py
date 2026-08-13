"""req.frame_ingest → hpp (behavior freeze; no .env)."""

from __future__ import annotations

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
    assert cfg["paths"]["frame"].endswith(".yuv")


def test_emit_frame_ingest_carla(tmp_path: Path) -> None:
    req = {
        "frame_ingest": {
            "frame_source": "carla_file",
            "perception_backend": "stub",
            "pixel_format": "nv12",
            "ego_source": "carla",
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
    assert "kBridgeDryRun" not in hpp
    assert "kDemoLaneChange" not in hpp
    assert "kFramePath" in hpp
    assert not (tmp_path / "frame_ingest.env").exists()


def test_legacy_rgb_path_migrates_to_yuv() -> None:
    cfg = normalize_frame_ingest(
        {"frame_ingest": {"paths": {"frame": "/tmp/gf_front.rgb"}, "pixel_format": "nv12"}}
    )
    assert cfg["paths"]["frame"] == "/tmp/gf_front.yuv"


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
