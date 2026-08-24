from __future__ import annotations

import json
from pathlib import Path

import yaml

from gf_codegen.compose.pipeline import compose_project


def test_compose_afc(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/afc/project.yaml"
    out = tmp_path / "gf.sor.json"
    rc = compose_project(project, repo_root=repo_root, out=out)
    assert rc == 0
    assert out.is_file()
    sor = json.loads(out.read_text(encoding="utf-8"))

    service_ids = {s["id"] for s in sor["services"]}
    for svc in (
        "services.semantic.EgoMotion",
        "services.semantic.Perception_MESSAGE_Out_St",
        "services.semantic.Trajectory",
        "services.semantic.VehicleBus",
    ):
        assert svc in service_ids
    assert "services.semantic.UssZones" not in service_ids

    procs = {d["process"] for d in sor["deployments"]}
    assert procs == {
        "external.vehicle_mcu",
        "adapter.vehicle_can_gateway",
        "perception.fcm",
        "planning.driving",
    }
    assert "sensing.uss" not in procs

    pm = sor.get("platform_manifest")
    assert isinstance(pm, dict)
    assert "exec" in pm and "phm" in pm

    report_path = repo_root / "projects/afc/reports/signal_lineage_report.yaml"
    assert report_path.is_file()
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
