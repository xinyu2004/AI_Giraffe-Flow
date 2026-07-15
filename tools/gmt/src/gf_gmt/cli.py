"""GMT CLI — architect (CI) + measure export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gf_gmt import __version__
from gf_gmt.architect import dag_from_sor, load_json, load_yaml, run_architect_lineage
from gf_gmt.measure_export import export_session_jsonl, write_mcap


def _resolve_project(project: Path) -> tuple[dict, dict | None, Path | None]:
    """Return (sor, req, report_path) from project.yaml directory."""
    proj_dir = project.parent if project.name == "project.yaml" else project
    if project.suffix in {".yaml", ".yml"} and project.name == "project.yaml":
        proj_dir = project.parent
    sor_path = proj_dir / "gf.sor.json"
    req_path = proj_dir / "req.yaml"
    report = proj_dir / "reports" / "signal_lineage_report.yaml"
    if not sor_path.is_file():
        raise FileNotFoundError(
            f"missing {sor_path}; save in gf-config (auto Compose) or: "
            f"python -m gf_codegen.compose --project {proj_dir}/project.yaml"
        )
    sor = load_json(sor_path)
    req = load_yaml(req_path) if req_path.is_file() else None
    return sor, req, report if report.is_file() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="GMT",
        description="Giraffe Measure Tool — architect (CI) + measure export",
    )
    parser.add_argument("--version", action="version", version=f"GMT {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_arch = sub.add_parser("architect", help="Read-only architecture checks")
    arch_sub = p_arch.add_subparsers(dest="arch_cmd", required=True)

    p_lin = arch_sub.add_parser("lineage", help="Run / verify signal lineage (CI)")
    p_lin.add_argument("--project", type=Path, default=None)
    p_lin.add_argument("--sor", type=Path, default=None)
    p_lin.add_argument("--req", type=Path, default=None)
    p_lin.add_argument("--report", type=Path, default=None, help="Optional existing report")
    p_lin.add_argument("--json", action="store_true", help="Print full report JSON")

    p_dag = arch_sub.add_parser("dag", help="Print process/dataflow DAG as JSON")
    p_dag.add_argument("--project", type=Path, default=None)
    p_dag.add_argument("--sor", type=Path, default=None)

    p_meas = sub.add_parser("measure", help="Measurement / export")
    meas_sub = p_meas.add_subparsers(dest="meas_cmd", required=True)
    p_exp = meas_sub.add_parser("export", help="Export session JSONL → MCAP 雏形")
    p_exp.add_argument("--in", dest="inp", type=Path, required=True, help="JSONL session")
    p_exp.add_argument("--out", type=Path, required=True, help="Output .mcap")
    p_exp.add_argument("--topic", type=str, default="/gf/stub")

    args = parser.parse_args(argv)

    if args.cmd == "architect":
        if args.arch_cmd == "lineage":
            req = None
            if args.project:
                sor, req, _rp = _resolve_project(args.project)
            elif args.sor:
                sor = load_json(args.sor)
                if args.req:
                    req = load_yaml(args.req)
            else:
                print("GMT architect lineage: need --project or --sor", file=sys.stderr)
                return 2

            report = run_architect_lineage(sor=sor, req=req)
            ok = bool(report.get("ok", False))
            if args.json:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                status = "PASS" if ok else "FAIL"
                print(f"GMT architect lineage: {status}")
                for e in report.get("errors") or []:
                    print(f"  error: {e}", file=sys.stderr)
                for w in report.get("warnings") or []:
                    print(f"  warn: {w}")
            return 0 if ok else 1

        if args.arch_cmd == "dag":
            if args.project:
                sor, _, _ = _resolve_project(args.project)
            elif args.sor:
                sor = load_json(args.sor)
            else:
                print("GMT architect dag: need --project or --sor", file=sys.stderr)
                return 2
            print(json.dumps(dag_from_sor(sor), indent=2, ensure_ascii=False))
            return 0

    if args.cmd == "measure" and args.meas_cmd == "export":
        if not args.inp.is_file():
            write_mcap(
                args.out,
                [{"log_time_ns": 0, "data": {"seq": 0, "note": "synthetic"}}],
                topic=args.topic,
            )
            print(f"wrote synthetic {args.out}")
            return 0
        path = export_session_jsonl(args.inp, args.out, topic=args.topic)
        print(f"wrote {path}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
