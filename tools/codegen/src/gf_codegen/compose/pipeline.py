"""Compose pipeline orchestration."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from gf_codegen.compose.apply_wiring import apply_wiring
from gf_codegen.compose.emit_build_cmake import emit_build_cmake, emit_observability_json
from gf_codegen.compose.emit_platform_tables import emit_platform_tables
from gf_codegen.compose.import_oem import import_oem
from gf_codegen.compose.lineage import run_lineage
from gf_codegen.compose.load_project import ProjectPaths, load_project
from gf_codegen.compose.merge_platform import merge_platform
from gf_codegen.compose.merge_req import merge_req
from gf_codegen.compose.observability import validate_observability
from gf_codegen.compose.write_sor import write_lineage, write_sor

def _merge_overlay(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    for key, val in overlay.items():
        if key == "imports_meta" and isinstance(val, dict):
            cur = base.get("imports_meta")
            if isinstance(cur, dict):
                cur.update(val)
            else:
                base["imports_meta"] = val
        elif key == "types" and isinstance(val, list):
            existing = {t.get("id") for t in (base.get("types") or []) if isinstance(t, dict)}
            types = list(base.get("types") or [])
            for t in val:
                if isinstance(t, dict) and t.get("id") not in existing:
                    types.append(t)
                    existing.add(t.get("id"))
            base["types"] = types
        elif key == "adapter_mappings" and isinstance(val, list):
            base["adapter_mappings"] = list(base.get("adapter_mappings") or []) + val
        else:
            base[key] = val


def compose_project(project_file: Path, *, repo_root: Path | None = None, out: Path | None = None) -> int:
    paths: ProjectPaths = load_project(project_file, repo_root=repo_root)
    if out is not None:
        paths.out_sor = out.resolve()

    # Validate inputs exist
    for label, p in [
        ("base", paths.base_sor),
        ("dbc", paths.dbc),
        ("manifest", paths.manifest),
        ("wiring", paths.wiring),
        ("req", paths.req),
    ]:
        if not p.is_file():
            print(f"error: missing {label}: {p}", file=sys.stderr)
            return 2

    with paths.base_sor.open(encoding="utf-8") as f:
        sor: dict[str, Any] = copy.deepcopy(json.load(f))

    # Normalize skeleton schema_version
    if str(sor.get("schema_version", "")).endswith("-skeleton"):
        sor["schema_version"] = "0.2.0"

    oem_overlay = import_oem(paths.dbc, paths.manifest)
    _merge_overlay(sor, oem_overlay)

    warnings = apply_wiring(
        sor, paths.wiring, repo_root=paths.repo_root, project_dir=paths.project_dir
    )

    merge_req(sor, paths.req)

    with paths.req.open(encoding="utf-8") as f:
        req = yaml.safe_load(f) or {}
    if not isinstance(req, dict):
        req = {}

    with paths.wiring.open(encoding="utf-8") as f:
        wiring = yaml.safe_load(f) or {}
    if not isinstance(wiring, dict):
        wiring = {}

    plat_errors, plat_warnings, plat_checks = merge_platform(
        sor, paths, req, wiring=wiring
    )

    report = run_lineage(sor, req)
    obs_err, obs_warn, obs_checks = validate_observability(req)
    report["project_id"] = paths.data.get("project_id") or report.get("project_id")
    report["warnings"] = list(report.get("warnings") or []) + warnings + plat_warnings + obs_warn
    report["errors"] = list(report.get("errors") or []) + plat_errors + obs_err
    report["checks"] = list(report.get("checks") or []) + plat_checks + obs_checks
    if plat_errors or obs_err:
        report["ok"] = False
    # relativize note
    report["outputs"] = {
        "sor": str(paths.out_sor),
        "lineage": str(paths.lineage_report),
    }

    write_sor(paths.out_sor, sor)
    write_lineage(paths.lineage_report, report)

    sku_cmake = paths.project_dir / "generated" / "gf_build.cmake"
    emit_build_cmake(req, sku_cmake)
    obs_json = paths.project_dir / "generated" / "observability.json"
    emit_observability_json(req, obs_json)
    report.setdefault("outputs", {})["sku_cmake"] = str(sku_cmake)
    report.setdefault("outputs", {})["observability"] = str(obs_json)
    write_lineage(paths.lineage_report, report)

    print(f"compose wrote: {paths.out_sor}")
    print(f"lineage wrote: {paths.lineage_report} (ok={report['ok']})")
    print(f"sku cmake wrote: {sku_cmake}")
    print(f"observability wrote: {obs_json}")
    if sor.get("platform_manifest"):
        keys = sorted(k for k in sor["platform_manifest"] if k != "schema_version")
        print(f"platform_manifest: {', '.join(keys)}")
    for w in report.get("warnings") or []:
        print(f"  warning: {w}")
    if not report["ok"]:
        for e in report.get("errors") or []:
            print(f"  error: {e}", file=sys.stderr)
        if paths.fail_on_error:
            return 1
    return 0
