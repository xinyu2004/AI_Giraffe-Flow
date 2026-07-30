"""Export SOR process/dataflow as Graphviz .dot / SVG (host-only, no DAG GUI)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _dag_to_dot(sor: dict[str, Any]) -> str:
    try:
        from gf_gmt.architect import dag_from_sor, dag_to_dot

        return dag_to_dot(dag_from_sor(sor))
    except ImportError:
        # Minimal fallback if gf_gmt not installed
        lines = [
            "digraph gf_dag {",
            "  rankdir=LR;",
            '  node [shape=box, style=rounded];',
        ]
        seen: set[str] = set()

        def nid(name: str) -> str:
            return "".join(c if c.isalnum() or c == "_" else "_" for c in name) or "node"

        for d in sor.get("deployments") or []:
            if not isinstance(d, dict) or not d.get("process"):
                continue
            proc = str(d["process"])
            pid = nid(proc)
            if pid in seen:
                continue
            seen.add(pid)
            label = proc.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'  {pid} [label="{label}"];')
        for flow in sor.get("dataflows") or []:
            if not isinstance(flow, dict):
                continue
            src, dst = flow.get("from"), flow.get("to")
            if not src or not dst:
                continue
            sid, did = nid(str(src)), nid(str(dst))
            svc = str(flow.get("service") or "")
            short = svc.rsplit(".", 1)[-1] if svc else ""
            if short:
                esc = short.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'  {sid} -> {did} [label="{esc}"];')
            else:
                lines.append(f"  {sid} -> {did};")
        lines.append("}")
        return "\n".join(lines) + "\n"


def load_sor(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"SOR must be a JSON object: {path}")
    return data


def write_dot(sor: dict[str, Any], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_dag_to_dot(sor), encoding="utf-8")
    return out


def write_svg_via_dot(dot_path: Path, svg_path: Path) -> Path:
    """Render SVG with system `dot` (Graphviz). Raises RuntimeError if missing."""
    exe = shutil.which("dot")
    if not exe:
        raise RuntimeError(
            "未找到 Graphviz 的 `dot`。请安装 graphviz 后重试，"
            "或先导出 .dot 再本机运行: dot -Tsvg -o out.svg in.dot"
        )
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [exe, "-Tsvg", "-o", str(svg_path), str(dot_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not svg_path.is_file():
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"dot 渲染失败: {err}")
    return svg_path


def export_sor_graph(
    sor_path: Path,
    *,
    dot_out: Path | None = None,
    svg_out: Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Write .dot and/or .svg from gf.sor.json. Returns (dot_path, svg_path)."""
    sor = load_sor(sor_path)
    wrote_dot: Path | None = None
    wrote_svg: Path | None = None
    if dot_out is not None:
        wrote_dot = write_dot(sor, dot_out)
    if svg_out is not None:
        # need a .dot file for the renderer
        tmp_dot = dot_out if dot_out is not None else svg_out.with_suffix(".dot")
        if wrote_dot is None:
            wrote_dot = write_dot(sor, tmp_dot)
        wrote_svg = write_svg_via_dot(wrote_dot, svg_out)
    return wrote_dot, wrote_svg
