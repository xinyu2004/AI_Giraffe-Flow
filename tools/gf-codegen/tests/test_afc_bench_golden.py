"""P2-G bench golden: compose afc_with_uss and assert stable acceptance invariants.

Full SOR snapshot lives in projects/.../golden/gf.sor.json (often gitignored).
When that file exists, also deep-compare sorted JSON for CI local/golden workflows.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from gf_codegen.compose.pipeline import compose_project


REQUIRED_SERVICES = {
    "services.semantic.EgoMotion",
    "services.semantic.UssZones",
    "services.semantic.Perception_MESSAGE_Out_St",
    "services.semantic.Trajectory",
    "services.semantic.VehicleBus",
}

REQUIRED_PROCESSES = {
    "adapter.vehicle_can_gateway",
    "perception.fcm",
    "sensing.uss",
    "planning.driving",
}


def _service_ids(sor: dict) -> set[str]:
    return {s["id"] for s in (sor.get("services") or []) if isinstance(s, dict) and "id" in s}


def test_afc_bench_golden_invariants(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/oem_a/afc_with_uss/project.yaml"
    out = tmp_path / "gf.sor.json"
    rc = compose_project(project, repo_root=repo_root, out=out)
    assert rc == 0

    sor = json.loads(out.read_text(encoding="utf-8"))
    assert sor.get("topology") == "ap_only"

    pm = sor.get("platform_manifest")
    assert isinstance(pm, dict)
    for key in ("exec", "phm", "diag", "log"):
        assert key in pm, f"platform_manifest missing {key}"
    assert "dem" not in pm and "DEM" not in pm

    names = {p["name"] for p in pm["exec"]["processes"]}
    assert REQUIRED_PROCESSES <= names
    assert "external.vehicle_mcu" not in names

    ids = _service_ids(sor)
    assert REQUIRED_SERVICES <= ids

    report_path = repo_root / "projects/oem_a/afc_with_uss/reports/signal_lineage_report.yaml"
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True


def test_afc_golden_snapshot_if_present(repo_root: Path, tmp_path: Path) -> None:
    golden = repo_root / "projects/oem_a/afc_with_uss/golden/gf.sor.json"
    if not golden.is_file():
        return  # optional snapshot; invariants test above is the CI gate

    project = repo_root / "projects/oem_a/afc_with_uss/project.yaml"
    out = tmp_path / "gf.sor.json"
    assert compose_project(project, repo_root=repo_root, out=out) == 0

    got = json.loads(out.read_text(encoding="utf-8"))
    expect = json.loads(golden.read_text(encoding="utf-8"))
    assert json.dumps(got, sort_keys=True) == json.dumps(expect, sort_keys=True)
