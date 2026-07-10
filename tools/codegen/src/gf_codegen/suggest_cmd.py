"""gf-codegen suggest wiring (P0: print YAML hints)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from gf_codegen.compose.load_project import load_project
from gf_codegen.compose.parse_hpp import parse_hpp_file
from gf_codegen.paths import resolve_path


def suggest_wiring(project_file: Path, *, repo_root: Path | None = None) -> int:
    paths = load_project(project_file, repo_root=repo_root)
    with paths.wiring.open(encoding="utf-8") as f:
        wiring = yaml.safe_load(f) or {}

    suggestions: list[dict] = []
    for mod in wiring.get("modules") or []:
        hpp_rel = mod.get("hpp")
        if not hpp_rel:
            continue
        hpp = resolve_path(paths.project_dir, hpp_rel, repo_root=paths.repo_root)
        if not hpp.is_file():
            continue
        structs = {s["name"] for s in parse_hpp_file(hpp)}
        outputs = []
        inputs = []
        for name in sorted(structs):
            if name in ("EgoMotion",):
                inputs.append({"service": f"semantic.{name}", "type": name})
            elif name.endswith("List") or name in ("UssZones", "ParkingWorld", "SurroundWorld"):
                outputs.append({"service": f"semantic.{name}", "type": name})
        if outputs or inputs:
            suggestions.append(
                {
                    "module": mod.get("id"),
                    "inputs": inputs,
                    "outputs": outputs,
                }
            )

    doc = {
        "note": "suggested bindings — review before merging into wiring.yaml",
        "bindings": suggestions,
    }
    yaml.safe_dump(doc, sys.stdout, sort_keys=False, allow_unicode=True)
    return 0
