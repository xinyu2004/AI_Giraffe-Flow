from __future__ import annotations

import json
from pathlib import Path

from gf_codegen.compose.pipeline import compose_project


def test_compose_adc_empty_slot(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/adc/project.yaml"
    out = tmp_path / "gf.sor.json"
    rc = compose_project(project, repo_root=repo_root, out=out)
    assert rc == 0
    assert out.is_file()
    sor = json.loads(out.read_text(encoding="utf-8"))

    service_ids = {s["id"] for s in (sor.get("services") or [])}
    assert "services.semantic.UssZones" not in service_ids

    procs = {d["process"] for d in (sor.get("deployments") or [])}
    assert "sensing.uss" not in procs
    assert "adapter.mcu_cp_gateway" not in procs
