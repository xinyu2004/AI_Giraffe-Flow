"""Load project.yaml and resolve related paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from gf_codegen.paths import find_repo_root, resolve_path


PLATFORM_KEYS = ("exec", "phm", "diag", "log", "ucm")


@dataclass
class ProjectPaths:
    repo_root: Path
    project_dir: Path
    project_file: Path
    data: dict[str, Any]
    base_sor: Path
    dbc: Path
    manifest: Path
    wiring: Path
    req: Path
    out_sor: Path
    lineage_report: Path
    fail_on_error: bool
    # key → absolute path; missing project.platform → empty dict
    platform: dict[str, Path]


def load_project(project_file: Path, repo_root: Path | None = None) -> ProjectPaths:
    project_file = project_file.resolve()
    project_dir = project_file.parent
    root = repo_root or find_repo_root(project_dir)

    with project_file.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    oem = data.get("oem") or {}
    integ = data.get("integration") or {}
    delivery = data.get("delivery") or {}
    lineage = data.get("lineage") or {}
    plat = data.get("platform") or {}

    base_rel = data.get("base") or "schemas/examples/desktop_ap_only.sor.json"
    base_sor = resolve_path(root, base_rel, repo_root=root)

    out_name = data.get("out") or "gf.sor.json"
    out_sor = resolve_path(project_dir, out_name, repo_root=root)

    report_rel = lineage.get("report") or "reports/signal_lineage_report.yaml"
    lineage_report = resolve_path(project_dir, report_rel, repo_root=root)

    platform_paths: dict[str, Path] = {}
    # Only resolve keys explicitly listed under project.platform (no silent defaults)
    if isinstance(plat, dict) and plat:
        for key in PLATFORM_KEYS:
            if key not in plat:
                continue
            rel = plat.get(key)
            if rel:
                platform_paths[key] = resolve_path(project_dir, str(rel), repo_root=root)

    return ProjectPaths(
        repo_root=root,
        project_dir=project_dir,
        project_file=project_file,
        data=data,
        base_sor=base_sor,
        dbc=resolve_path(project_dir, oem.get("dbc") or "oem/oem_import.dbc", repo_root=root),
        manifest=resolve_path(
            project_dir, oem.get("manifest") or "oem/oem_import.yaml", repo_root=root
        ),
        wiring=resolve_path(
            project_dir, integ.get("wiring") or "integration/wiring.yaml", repo_root=root
        ),
        req=resolve_path(project_dir, delivery.get("req") or "req.yaml", repo_root=root),
        out_sor=out_sor,
        lineage_report=lineage_report,
        fail_on_error=bool(lineage.get("fail_on_error", True)),
        platform=platform_paths,
    )
