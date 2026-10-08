"""gf-codegen suggest wiring (P0: print YAML hints)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from gf_codegen.compose.load_project import load_project
from gf_codegen.compose.types_store import load_types_yaml


def suggest_wiring(project_file: Path, *, repo_root: Path | None = None) -> int:
    paths = load_project(project_file, repo_root=repo_root)
    types = load_types_yaml(paths.types_yaml)
    names = {
        str(t.get("id") or "").rsplit(".", 1)[-1]
        for t in types
        if isinstance(t, dict) and t.get("id")
    }
    names.discard("")

    outputs = []
    inputs = []
    for name in sorted(names):
        if name in ("EgoMotion",):
            inputs.append({"service": f"semantic.{name}", "type": name})
        elif name.endswith("List") or name in (
            "UssZones",
            "ParkingWorld",
            "SurroundWorld",
        ):
            outputs.append({"service": f"semantic.{name}", "type": name})

    doc = {
        "note": "suggested bindings — review before merging into wiring.yaml",
        "bindings": (
            [{"module": "(from cfg/types.yaml)", "inputs": inputs, "outputs": outputs}]
            if outputs or inputs
            else []
        ),
    }
    yaml.safe_dump(doc, sys.stdout, sort_keys=False, allow_unicode=True)
    return 0
