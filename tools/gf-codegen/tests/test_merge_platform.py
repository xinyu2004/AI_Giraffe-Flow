"""Tests for platform merge / validation in compose."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from gf_codegen.compose.load_project import load_project
from gf_codegen.compose.merge_platform import validate_platform
from gf_codegen.compose.pipeline import compose_project


def test_compose_afc_writes_platform_manifest(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/oem_a/afc_with_uss/project.yaml"
    out = tmp_path / "gf.sor.json"
    rc = compose_project(project, repo_root=repo_root, out=out)
    assert rc == 0, "compose should succeed with valid platform"
    sor = json.loads(out.read_text(encoding="utf-8"))
    pm = sor.get("platform_manifest")
    assert isinstance(pm, dict)
    assert "exec" in pm and "phm" in pm and "log" in pm and "diag" in pm
    assert "ucm" not in pm  # not in runtime_modules
    names = {p["name"] for p in pm["exec"]["processes"]}
    assert "adapter.vehicle_can_gateway" in names
    assert "external.vehicle_mcu" not in names

    report = yaml.safe_load(
        (repo_root / "projects/oem_a/afc_with_uss/reports/signal_lineage_report.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert report["ok"] is True
    check_ids = {c["id"] for c in report.get("checks") or []}
    assert "platform_exec_processes" in check_ids
    assert "platform_phm_processes" in check_ids


def test_bad_exec_process_fails_compose(repo_root: Path, tmp_path: Path) -> None:
    """Copy SKU inputs, poison exec.yaml process → compose rc != 0."""
    src = repo_root / "projects/oem_a/afc_with_uss"
    dst = tmp_path / "sku"
    # minimal copy of needed files
    import shutil

    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("generated", "reports", "gf.sor.json", "golden"),
    )
    # rewrite project paths to be self-contained (already relative)
    exec_path = dst / "platform" / "exec.yaml"
    data = yaml.safe_load(exec_path.read_text(encoding="utf-8"))
    data["processes"].append(
        {
            "name": "does.not.exist",
            "function_group": "MachineFG",
            "depends_on": [],
            "execution_client": True,
        }
    )
    exec_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    out = tmp_path / "bad.sor.json"
    rc = compose_project(dst / "project.yaml", repo_root=repo_root, out=out)
    assert rc == 1
    report = yaml.safe_load((dst / "reports" / "signal_lineage_report.yaml").read_text(encoding="utf-8"))
    assert report["ok"] is False
    err_text = "\n".join(report.get("errors") or [])
    assert "does.not.exist" in err_text


def test_validate_rejects_external_process() -> None:
    errors, _warnings, checks = validate_platform(
        {
            "exec": {
                "function_groups": [{"id": "MachineFG", "initial": "Running"}],
                "processes": [
                    {
                        "name": "external.vehicle_mcu",
                        "function_group": "MachineFG",
                        "depends_on": [],
                        "execution_client": True,
                    }
                ],
            }
        },
        ap_processes={"adapter.vehicle_can_gateway"},
    )
    assert errors
    assert any(c.get("id") == "platform_exec_processes" and c.get("status") == "fail" for c in checks)


def test_adc_full_skips_platform(repo_root: Path, tmp_path: Path) -> None:
    """adc_full has no project.platform → skip, still compose."""
    project = repo_root / "projects/oem_b/adc_full/project.yaml"
    paths = load_project(project, repo_root=repo_root)
    assert paths.platform == {}
    out = tmp_path / "adc.sor.json"
    rc = compose_project(project, repo_root=repo_root, out=out)
    assert rc == 0
    sor = json.loads(out.read_text(encoding="utf-8"))
    assert "platform_manifest" not in sor
