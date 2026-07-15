"""Read-only architecture checks for CI (wraps SOR lineage)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_architect_lineage(
    *,
    sor: dict[str, Any],
    req: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run lineage checks. Returns report dict with ok bool."""
    from gf_codegen.compose.lineage import run_lineage

    return run_lineage(sor, req)


def dag_from_sor(sor: dict[str, Any]) -> dict[str, Any]:
    """Process / dataflow DAG as plain JSON (no GUI)."""
    nodes = []
    for d in sor.get("deployments") or []:
        if not isinstance(d, dict):
            continue
        nodes.append(
            {
                "process": d.get("process"),
                "provides": list(d.get("provides") or []),
                "requires": list(d.get("requires") or []),
            }
        )
    edges = []
    for flow in sor.get("dataflows") or []:
        if not isinstance(flow, dict):
            continue
        edges.append(
            {
                "from": flow.get("from"),
                "to": flow.get("to"),
                "service": flow.get("service"),
            }
        )
    return {"nodes": nodes, "edges": edges}
