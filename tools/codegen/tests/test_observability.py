"""Profile + observability allowlist for compose / CMake."""

from __future__ import annotations

import json
from pathlib import Path

from gf_codegen.compose.emit_build_cmake import emit_build_cmake, emit_observability_json
from gf_codegen.compose.observability import (
    TAP_APP,
    effective_apps,
    live_tap_config,
    record_config,
    validate_observability,
)
from gf_codegen.compose.pipeline import compose_project


def test_live_tap_disabled_on_production_release() -> None:
    req = {
        "profile": "production-release",
        "observability": {
            "live_tap": {"enabled": True, "services": ["EgoMotion"]},
            "record": {"mode": "minimal", "services": ["Trajectory"]},
        },
        "apps": ["adapters/vehicle_can_gateway"],
    }
    en, svcs = live_tap_config(req)
    assert en is False
    mode, _ = record_config(req)
    assert mode == "off"
    apps = effective_apps(req)
    assert TAP_APP not in apps
    assert "adapters/vehicle_can_gateway" in apps


def test_live_tap_adds_app_on_debug() -> None:
    req = {
        "profile": "vehicle-debug",
        "observability": {
            "live_tap": {
                "enabled": True,
                "services": ["services.semantic.EgoMotion", "Trajectory"],
            },
            "record": {"mode": "minimal", "services": ["EgoMotion"]},
        },
        "apps": ["planning/driving", TAP_APP],
    }
    en, svcs = live_tap_config(req)
    assert en is True
    assert svcs == ["EgoMotion", "Trajectory"]
    apps = effective_apps(req)
    assert apps.count(TAP_APP) == 1
    assert apps[-1] == TAP_APP


def test_record_empty_whitelist_fails_validate() -> None:
    req = {
        "profile": "vehicle-debug",
        "observability": {"record": {"mode": "minimal", "services": []}},
    }
    err, _warn, checks = validate_observability(req)
    assert any("record.services" in e for e in err)
    assert any(c.get("id") == "record_whitelist" and c.get("status") == "fail" for c in checks)


def test_emit_observability_and_cmake(tmp_path: Path) -> None:
    req = {
        "profile": "vehicle-debug",
        "variant": "t",
        "runtime_modules": ["core", "com"],
        "bindings": ["iceoryx"],
        "apps": ["perception/fcm"],
        "observability": {
            "live_tap": {"enabled": True, "services": ["EgoMotion"]},
            "record": {"mode": "minimal", "services": ["Trajectory"]},
        },
    }
    cmake = tmp_path / "gf_build.cmake"
    obs = tmp_path / "observability.json"
    emit_build_cmake(req, cmake)
    emit_observability_json(req, obs)
    text = cmake.read_text(encoding="utf-8")
    assert "GF_SKU_PROFILE" in text and "vehicle-debug" in text
    assert "GF_OBS_LIVE_TAP ON" in text
    assert TAP_APP in text
    data = json.loads(obs.read_text(encoding="utf-8"))
    assert data["live_tap"]["enabled"] is True
    assert data["live_tap"]["services"] == ["EgoMotion"]


def test_compose_afc_writes_observability(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/oem_a/afc_with_uss/project.yaml"
    out = tmp_path / "gf.sor.json"
    rc = compose_project(project, repo_root=repo_root, out=out)
    assert rc == 0
    obs = repo_root / "projects/oem_a/afc_with_uss/generated/observability.json"
    assert obs.is_file()
    data = json.loads(obs.read_text(encoding="utf-8"))
    assert data.get("profile") == "vehicle-debug"
    assert data["live_tap"]["enabled"] is True
    cmake = (repo_root / "projects/oem_a/afc_with_uss/generated/gf_build.cmake").read_text(
        encoding="utf-8"
    )
    assert "tools/iox_obs_tap" in cmake
