"""deploy_config.hpp + product em_launch freeze."""

from __future__ import annotations

from pathlib import Path

import yaml

from gf_codegen.compose.emit_deploy_config import (
    emit_deploy_config,
    normalize_deploy_flags,
)
from gf_codegen.compose.emit_em_launch import (
    HOST_DLT,
    HOST_FRAME_INGEST,
    HOST_ROUDI,
    emit_product_em_assets,
)


def test_normalize_deploy_flags() -> None:
    req = {
        "profile": "vehicle-debug",
        "bindings": ["iceoryx"],
        "runtime_modules": ["exec", "log", "com"],
        "observability": {"live_tap": {"enabled": True, "mode": "wiring_all"}},
    }
    platform = {
        "log": {"sinks": ["console", "dlt"]},
        "diag": {"iso_13400_doip": True, "doip": {"enabled": True}},
    }
    wiring = {"dataflows": [{"service": "services.semantic.EgoMotion"}]}
    cfg = normalize_deploy_flags(req, platform, wiring=wiring)
    assert cfg["k_em"] is True
    assert cfg["k_dlt"] is True
    assert cfg["k_roudi"] is True
    assert cfg["k_frame_ingest"] is False
    assert cfg["k_live_tap"] is True
    assert cfg["k_doip"] is True
    assert cfg["k_inject_built"] is True


def test_normalize_deploy_flags_frame_ingest() -> None:
    req = {
        "profile": "vehicle-debug",
        "bindings": ["iceoryx"],
        "runtime_modules": ["exec"],
        "frame_ingest": {"active_source": "carla", "ego_source": "carla"},
    }
    cfg = normalize_deploy_flags(req, {"log": {"sinks": ["console"]}})
    assert cfg["k_frame_ingest"] is True


def test_emit_deploy_config_hpp_and_tables(tmp_path: Path) -> None:
    plat = tmp_path / "platform"
    plat.mkdir()
    (plat / "em_launch.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "processes": [
                    {
                        "name": HOST_DLT,
                        "binary": "bin/dlt-daemon",
                        "args": [],
                        "max_restarts": 3,
                    },
                    {
                        "name": HOST_ROUDI,
                        "binary": "bin/iox-roudi",
                        "args": ["-c", "$GF_IOX_TOML"],
                        "max_restarts": 3,
                    },
                    {
                        "name": "adapter.vehicle_can_gateway",
                        "binary": "apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway",
                        "args": ["15"],
                        "max_restarts": 2,
                    },
                    {
                        "name": "planning.driving",
                        "binary": "apps/planning/driving/gf_planning_driving",
                        "args": ["0"],
                        "max_restarts": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (plat / "exec.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "function_groups": [
                    {"id": "MachineFG", "kind": "machine", "initial": "Running"},
                    {
                        "id": "DriveParkFG",
                        "kind": "mode",
                        "initial": "DrivingActive",
                        "states": ["DrivingActive", "ParkingActive"],
                    },
                ],
                "processes": [
                    {
                        "name": HOST_DLT,
                        "function_group": "MachineFG",
                        "depends_on": [],
                        "execution_client": False,
                    },
                    {
                        "name": HOST_ROUDI,
                        "function_group": "MachineFG",
                        "depends_on": [HOST_DLT],
                        "execution_client": False,
                    },
                    {
                        "name": "adapter.vehicle_can_gateway",
                        "function_group": "MachineFG",
                        "depends_on": [HOST_ROUDI],
                        "execution_client": True,
                    },
                    {
                        "name": "planning.driving",
                        "function_group": "DriveParkFG",
                        "active_in": ["DrivingActive"],
                        "depends_on": [HOST_ROUDI],
                        "execution_client": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    req = {
        "profile": "vehicle-debug",
        "bindings": ["iceoryx"],
        "runtime_modules": ["exec"],
        "observability": {"live_tap": {"enabled": False}},
    }
    platform = {
        "log": {"sinks": ["console", "dlt"]},
        "diag": {
            "doip": {
                "enabled": True,
                "tcp_port": 13400,
                "logical_address": 0x0E00,
                "tester_address": 0x0E80,
            },
            "timing": {"s3_server_ms": 5000, "p2_server_ms": 50},
            "ota_transfer": {
                "mode": "request_file_transfer",
                "require_programming_session": True,
                "require_security": True,
                "max_block_length": 1024,
            },
        },
        "phm": {
            "entities": [
                {"process": "adapter.vehicle_can_gateway", "on_failure": "restart"},
            ]
        },
    }
    gen = tmp_path / "generated"
    meta = emit_deploy_config(req, platform, plat, gen)
    hpp = Path(meta["hpp"]).read_text(encoding="utf-8")
    assert "namespace gf_gen::deploy" in hpp
    assert "kEm = true" in hpp
    assert "kDlt = true" in hpp
    assert "kRouDi = true" in hpp
    assert "kDoip = true" in hpp
    assert "kDoipTcpPort = 13400u" in hpp
    assert "kDiagS3ServerMs = 5000u" in hpp
    assert 'kOtaTransferMode = "request_file_transfer"' in hpp
    assert "kEmLaunch[]" in hpp
    assert "host.iox_roudi" in hpp
    assert "host.dlt_daemon" in hpp
    assert "adapter.vehicle_can_gateway" in hpp
    assert "bool restart_enabled" in hpp
    assert ", true, 2u" in hpp
    assert "FgKind::kMode" in hpp
    assert "kFunctionGroups[]" in hpp
    assert "kActiveIn_planning_driving" in hpp
    assert "DrivingActive" in hpp
    # Human dumps still written
    assert Path(meta["em_launch"]).is_file()
    assert Path(meta["exec"]).is_file()
    assert not (gen / "sil_runtime.env").exists()


def test_emit_product_em_filters_dlt(tmp_path: Path) -> None:
    plat = tmp_path / "platform"
    plat.mkdir()
    (plat / "em_launch.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "processes": [
                    {"name": HOST_DLT, "binary": "dlt", "args": [], "max_restarts": 1},
                    {
                        "name": HOST_ROUDI,
                        "binary": "iox-roudi",
                        "args": ["-c", "$GF_IOX_TOML"],
                        "max_restarts": 1,
                    },
                    {
                        "name": "adapter.vehicle_can_gateway",
                        "binary": "gw",
                        "args": ["15"],
                        "max_restarts": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (plat / "exec.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "function_groups": [{"id": "MachineFG", "initial": "Running"}],
                "processes": [
                    {
                        "name": HOST_DLT,
                        "function_group": "MachineFG",
                        "depends_on": [],
                        "execution_client": False,
                    },
                    {
                        "name": HOST_ROUDI,
                        "function_group": "MachineFG",
                        "depends_on": [HOST_DLT],
                        "execution_client": False,
                    },
                    {
                        "name": "adapter.vehicle_can_gateway",
                        "function_group": "MachineFG",
                        "depends_on": [HOST_ROUDI],
                        "execution_client": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    gen = tmp_path / "generated"
    meta = emit_product_em_assets(plat, gen, k_dlt=False, k_roudi=True)
    launch = yaml.safe_load(Path(meta["em_launch"]).read_text(encoding="utf-8"))
    names = [p["name"] for p in launch["processes"]]
    assert HOST_DLT not in names
    assert HOST_ROUDI in names
    assert HOST_FRAME_INGEST not in names
    gw = next(p for p in launch["processes"] if p["name"] == "adapter.vehicle_can_gateway")
    assert gw["args"] == ["0"]
    exec_doc = yaml.safe_load(Path(meta["exec"]).read_text(encoding="utf-8"))
    roudi = next(p for p in exec_doc["processes"] if p["name"] == HOST_ROUDI)
    assert HOST_DLT not in (roudi.get("depends_on") or [])


def test_emit_product_em_does_not_invent_frame_ingest(tmp_path: Path) -> None:
    """Capability on but host absent in authored YAML → emit must not invent the row."""
    plat = tmp_path / "platform"
    plat.mkdir()
    (plat / "em_launch.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "processes": [
                    {
                        "name": "adapter.vehicle_can_gateway",
                        "binary": "bin/gw",
                        "args": ["0"],
                        "max_restarts": 1,
                    },
                    {
                        "name": "perception.fcm",
                        "binary": "bin/fcm",
                        "args": ["0"],
                        "max_restarts": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (plat / "exec.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "function_groups": [{"id": "MachineFG", "initial": "Running"}],
                "processes": [
                    {
                        "name": "adapter.vehicle_can_gateway",
                        "function_group": "MachineFG",
                        "depends_on": [],
                        "execution_client": True,
                    },
                    {
                        "name": "perception.fcm",
                        "function_group": "MachineFG",
                        "depends_on": ["adapter.vehicle_can_gateway"],
                        "execution_client": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    gen = tmp_path / "generated"
    meta = emit_product_em_assets(
        plat, gen, k_dlt=False, k_roudi=True, k_frame_ingest=True
    )
    launch = yaml.safe_load(Path(meta["em_launch"]).read_text(encoding="utf-8"))
    names = [p["name"] for p in launch["processes"]]
    assert HOST_FRAME_INGEST not in names
    exec_doc = yaml.safe_load(Path(meta["exec"]).read_text(encoding="utf-8"))
    assert HOST_FRAME_INGEST not in [p["name"] for p in exec_doc["processes"]]
    fcm = next(p for p in exec_doc["processes"] if p["name"] == "perception.fcm")
    # depends_on overlay may still reference the host when capability is on
    assert HOST_FRAME_INGEST in (fcm.get("depends_on") or [])
