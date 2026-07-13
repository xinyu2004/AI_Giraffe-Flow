from __future__ import annotations

import json
from pathlib import Path

import yaml

from gf_codegen.compose.pipeline import compose_project


def test_compose_adc_full(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/oem_b/adc_full/project.yaml"
    out = tmp_path / "gf.sor.json"
    rc = compose_project(project, repo_root=repo_root, out=out)
    assert rc == 0
    assert out.is_file()
    sor = json.loads(out.read_text(encoding="utf-8"))

    service_ids = {s["id"] for s in sor["services"]}
    for svc in (
        "services.semantic.EgoMotion",
        "services.semantic.UssZones",
        "services.semantic.FrontObjectList",
        "services.semantic.SurroundWorld",
        "services.semantic.ParkingWorld",
        "services.semantic.DrivingObjectList",
        "services.semantic.Trajectory",
        "services.semantic.ActuatorCommand",
        "services.semantic.EgoMotionExtended",
        "services.semantic.VehicleModeStatus",
    ):
        assert svc in service_ids

    procs = {d["process"] for d in sor["deployments"]}
    assert "adapter.vehicle_can_gateway" in procs
    assert "adapter.mcu_cp_gateway" in procs
    assert "sensing.uss" in procs
    assert "perception.surround" in procs
    assert "perception.parking" in procs
    assert "perception.driving.nullmax" in procs
    assert "planning.driving" in procs
    assert "planning.parking" in procs

    assert sor.get("topology") == "ap_mcu_cp"

    report_path = repo_root / "projects/oem_b/adc_full/reports/signal_lineage_report.yaml"
    assert report_path.is_file()
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
