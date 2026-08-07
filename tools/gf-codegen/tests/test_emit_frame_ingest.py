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
    assert cfg["bridge"]["enabled"] is False
    assert cfg["bridge"]["dry_run"] is True


def test_emit_frame_ingest_carla_dry(tmp_path: Path) -> None:
    req = {
        "frame_ingest": {
            "frame_source": "carla_file",
            "perception_backend": "stub",
            "bridge": {
                "enabled": True,
                "dry_run": True,
                "demo_lane_change": True,
                "demo_lane_change_sec": 8,
            },
            "paths": {
                "frame": "/tmp/gf_front.rgb",
                "cmd": "/tmp/gf_carla_cmd.json",
            },
        }
    }
    meta = emit_frame_ingest(req, tmp_path)
    hpp = Path(meta["hpp"]).read_text(encoding="utf-8")
    assert 'kFrameSource = "carla_file"' in hpp
    assert "kBridgeEnabled = true" in hpp
    assert "kBridgeDryRun = true" in hpp
    assert "kFramePath" in hpp
    assert not (tmp_path / "frame_ingest.env").exists()
    assert "env" not in meta


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
    assert "deploy_config.hpp" in text or "frame_ingest_config.hpp" in text
