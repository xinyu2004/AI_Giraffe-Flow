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


def _mermaid_id(name: str) -> str:
    """Safe Mermaid node id (alphanumeric / underscore)."""
    out = []
    for ch in str(name):
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    return "".join(out) or "node"


def _short_service(service: Any) -> str:
    s = str(service or "")
    if "." in s:
        return s.rsplit(".", 1)[-1]
    return s


def dag_to_mermaid(dag: dict[str, Any]) -> str:
    """Render process/dataflow DAG as Mermaid flowchart."""
    lines = ["flowchart LR"]
    seen: set[str] = set()
    for n in dag.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        proc = n.get("process")
        if not proc:
            continue
        pid = _mermaid_id(str(proc))
        if pid in seen:
            continue
        seen.add(pid)
        label = str(proc).replace('"', "'")
        lines.append(f'  {pid}["{label}"]')
    for e in dag.get("edges") or []:
        if not isinstance(e, dict):
            continue
        src, dst = e.get("from"), e.get("to")
        if not src or not dst:
            continue
        sid, did = _mermaid_id(str(src)), _mermaid_id(str(dst))
        if sid not in seen:
            seen.add(sid)
            lines.append(f'  {sid}["{str(src).replace(chr(34), chr(39))}"]')
        if did not in seen:
            seen.add(did)
            lines.append(f'  {did}["{str(dst).replace(chr(34), chr(39))}"]')
        svc = _short_service(e.get("service"))
        if svc:
            lines.append(f"  {sid} -->|{svc}| {did}")
        else:
            lines.append(f"  {sid} --> {did}")
    return "\n".join(lines) + "\n"


def dag_to_dot(dag: dict[str, Any]) -> str:
    """Render process/dataflow DAG as Graphviz DOT."""
    lines = [
        "digraph gf_dag {",
        "  rankdir=LR;",
        '  node [shape=box, style=rounded];',
    ]
    seen: set[str] = set()
    for n in dag.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        proc = n.get("process")
        if not proc:
            continue
        pid = _mermaid_id(str(proc))
        if pid in seen:
            continue
        seen.add(pid)
        label = str(proc).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  {pid} [label="{label}"];')
    for e in dag.get("edges") or []:
        if not isinstance(e, dict):
            continue
        src, dst = e.get("from"), e.get("to")
        if not src or not dst:
            continue
        sid, did = _mermaid_id(str(src)), _mermaid_id(str(dst))
        if sid not in seen:
            seen.add(sid)
            label = str(src).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'  {sid} [label="{label}"];')
        if did not in seen:
            seen.add(did)
            label = str(dst).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'  {did} [label="{label}"];')
        svc = _short_service(e.get("service"))
        if svc:
            esc = svc.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'  {sid} -> {did} [label="{esc}"];')
        else:
            lines.append(f"  {sid} -> {did};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def format_dag(dag: dict[str, Any], fmt: str = "json") -> str:
    """Serialize DAG as json | mermaid | dot."""
    key = (fmt or "json").lower().strip()
    if key == "json":
        return json.dumps(dag, indent=2, ensure_ascii=False) + "\n"
    if key == "mermaid":
        return dag_to_mermaid(dag)
    if key == "dot":
        return dag_to_dot(dag)
    raise ValueError(f"unsupported DAG format: {fmt!r} (want json|mermaid|dot)")
