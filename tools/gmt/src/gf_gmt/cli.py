"""GMT CLI — architect (CI) + measure (record/tag/export) + bridge foxglove."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gf_gmt import __version__
from gf_gmt.architect import (
    dag_from_sor,
    format_dag,
    load_json,
    load_yaml,
    run_architect_lineage,
)
from gf_gmt.bridge_foxglove import main_bridge
from gf_gmt.bridge_live import main_live_bridge
from gf_gmt.measure_export import export_session_jsonl, list_mcap_topics, write_mcap
from gf_gmt.measure_ndjson import record_from_ndjson
from gf_gmt.measure_record import record_from_sil_logs
from gf_gmt.measure_tag import tag_session
from gf_gmt.measure_vcd import export_session_vcd


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
        description="Giraffe Measure Tool — architect + measure + foxglove bridge",
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

    p_dag = arch_sub.add_parser(
        "dag", help="Print process/dataflow DAG (json|mermaid|dot)"
    )
    p_dag.add_argument("--project", type=Path, default=None)
    p_dag.add_argument("--sor", type=Path, default=None)
    p_dag.add_argument(
        "--format",
        choices=("json", "mermaid", "dot"),
        default="json",
        help="Output format (default: json)",
    )

    p_meas = sub.add_parser("measure", help="Record / tag / export")
    meas_sub = p_meas.add_subparsers(dest="meas_cmd", required=True)

    p_rec = meas_sub.add_parser(
        "record", help="Build session JSONL from SIL multiproc logs (O-1)"
    )
    p_rec.add_argument(
        "--from-logs",
        type=Path,
        required=True,
        help="SIL runtime logs directory (…/runtime/logs)",
    )
    p_rec.add_argument("--out", type=Path, required=True, help="Output session.jsonl")
    p_rec.add_argument(
        "--services",
        type=str,
        default=None,
        help="Comma-separated record whitelist (short names). Empty → no events.",
    )
    p_rec.add_argument(
        "--observability",
        type=Path,
        default=None,
        help="generated/observability.json (uses record.services)",
    )

    p_tag = meas_sub.add_parser("tag", help="Clip session JSONL by time window (O-2)")
    p_tag.add_argument("--in", dest="inp", type=Path, required=True)
    p_tag.add_argument("--out", type=Path, required=True)
    p_tag.add_argument("--from-ns", type=int, default=None)
    p_tag.add_argument("--to-ns", type=int, default=None)
    p_tag.add_argument("--label", type=str, default="")
    p_tag.add_argument("--topic", action="append", default=None, help="Repeatable filter")

    p_exp = meas_sub.add_parser("export", help="Export session JSONL → MCAP or VCD")
    p_exp.add_argument("--in", dest="inp", type=Path, required=True, help="JSONL session")
    p_exp.add_argument("--out", type=Path, required=True, help="Output .mcap or .vcd")
    p_exp.add_argument(
        "--format",
        choices=("mcap", "vcd"),
        default=None,
        help="Output format (default: from --out suffix, else mcap)",
    )
    p_exp.add_argument("--topic", type=str, default="/gf/stub", help="Default topic if row omits (mcap)")

    p_nd = meas_sub.add_parser(
        "import-ndjson", help="Import iox_obs_tap NDJSON → session JSONL (G2)"
    )
    p_nd.add_argument("--in", dest="inp", type=Path, required=True)
    p_nd.add_argument("--out", type=Path, required=True)

    p_br = sub.add_parser("bridge", help="Visualization bridges")
    br_sub = p_br.add_subparsers(dest="br_cmd", required=True)
    p_fox = br_sub.add_parser("foxglove", help="Foxglove Studio helper / WS (offline + live)")
    p_fox.add_argument("--mcap", type=Path, default=None)
    p_fox.add_argument("--jsonl", type=Path, default=None)
    p_fox.add_argument("--serve", action="store_true")
    p_fox.add_argument("--ws", action="store_true")
    p_fox.add_argument(
        "--stdin",
        action="store_true",
        help="With --ws: live NDJSON from stdin (pipe from gf_iox_obs_tap)",
    )
    p_fox.add_argument("--host", default="127.0.0.1")
    p_fox.add_argument("--port", type=int, default=8765)
    p_fox.add_argument("--speed", type=float, default=1.0)
    p_fox.add_argument(
        "--synth-bev",
        action="store_true",
        help="Compose BEV from EgoMotion/Trajectory (live --stdin or --jsonl)",
    )
    p_fox.add_argument(
        "--bev-script",
        type=Path,
        default=None,
        help="Scenario JSONL (AdasDemo) → enrich BEV Image only; not published to Studio",
    )

    p_live = br_sub.add_parser(
        "live",
        help="GMT GUI live NDJSON bridge (stdin tap → WebSocket)",
    )
    p_live.add_argument(
        "--stdin",
        action="store_true",
        help="Read NDJSON from stdin (pipe from gf_iox_obs_tap)",
    )
    p_live.add_argument("--host", default="127.0.0.1")
    p_live.add_argument("--port", type=int, default=None)

    p_gui = sub.add_parser(
        "gui",
        help="Host GUI: replay timeline + order/race + animated DAG (read-only)",
    )
    p_gui.add_argument(
        "--session",
        type=Path,
        default=None,
        help="session JSONL to open",
    )
    p_gui.add_argument("--sor", type=Path, default=None, help="gf.sor.json for topology")
    p_gui.add_argument(
        "--project",
        type=Path,
        default=None,
        help="project dir / project.yaml (loads SOR if present)",
    )
    p_gui.add_argument(
        "--follow",
        action="store_true",
        help="Tail session JSONL (default build/observability/session_live.jsonl)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "gui":
        try:
            from gf_gmt.gui.main_window import run_gui
        except ImportError as exc:
            print(
                "GMT gui requires PySide6. Install: pip install 'gf-gmt[gui]' "
                f"or pip install PySide6  ({exc})",
                file=sys.stderr,
            )
            return 2
        return run_gui(
            session=args.session,
            sor=args.sor,
            project=args.project,
            follow=bool(args.follow),
        )

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
            try:
                sys.stdout.write(format_dag(dag_from_sor(sor), args.format))
            except ValueError as exc:
                print(f"GMT architect dag: {exc}", file=sys.stderr)
                return 2
            return 0

    if args.cmd == "measure":
        if args.meas_cmd == "record":
            services = None
            if args.services is not None:
                services = [s.strip() for s in args.services.split(",") if s.strip()]
            path, n = record_from_sil_logs(
                args.from_logs,
                args.out,
                services=services,
                observability_json=args.observability,
            )
            print(f"wrote {path} events={n}")
            return 0 if n > 0 else 1
        if args.meas_cmd == "tag":
            path, kept, total = tag_session(
                args.inp,
                args.out,
                from_ns=args.from_ns,
                to_ns=args.to_ns,
                label=args.label,
                topics=args.topic,
            )
            print(f"wrote {path} kept={kept}/{total}")
            return 0 if kept > 0 else 1
        if args.meas_cmd == "export":
            fmt = args.format
            if fmt is None:
                suf = args.out.suffix.lower()
                fmt = "vcd" if suf == ".vcd" else "mcap"
            if fmt == "vcd":
                if not args.inp.is_file():
                    print(f"GMT measure export: missing {args.inp}", file=sys.stderr)
                    return 2
                path, n_vars, n_ev = export_session_vcd(args.inp, args.out)
                print(f"wrote {path} vars={n_vars} events={n_ev}")
                return 0 if n_vars > 0 else 1
            if not args.inp.is_file():
                write_mcap(
                    args.out,
                    [{"log_time_ns": 0, "data": {"seq": 0, "note": "synthetic"}}],
                    topic=args.topic,
                )
                print(f"wrote synthetic {args.out}")
                return 0
            path = export_session_jsonl(args.inp, args.out, topic=args.topic)
            topics = list_mcap_topics(path)
            print(f"wrote {path} topics={topics}")
            return 0
        if args.meas_cmd == "import-ndjson":
            path, n = record_from_ndjson(args.inp, args.out)
            print(f"wrote {path} events={n}")
            return 0 if n > 0 else 1

    if args.cmd == "bridge" and args.br_cmd == "foxglove":
        # Reuse bridge module argv shape
        fox_argv: list[str] = []
        if args.mcap:
            fox_argv += ["--mcap", str(args.mcap)]
        if args.jsonl:
            fox_argv += ["--jsonl", str(args.jsonl)]
        if args.serve:
            fox_argv.append("--serve")
        if args.ws:
            fox_argv.append("--ws")
        if getattr(args, "stdin", False):
            fox_argv.append("--stdin")
        if getattr(args, "synth_bev", False):
            fox_argv.append("--synth-bev")
        if getattr(args, "bev_script", None) is not None:
            fox_argv += ["--bev-script", str(args.bev_script)]
        fox_argv += ["--host", args.host, "--port", str(args.port), "--speed", str(args.speed)]
        return main_bridge(fox_argv)

    if args.cmd == "bridge" and args.br_cmd == "live":
        from gf_gmt.bridge_live import DEFAULT_LIVE_PORT

        live_argv: list[str] = ["--stdin"]
        live_argv += ["--host", args.host]
        port = args.port if args.port is not None else DEFAULT_LIVE_PORT
        live_argv += ["--port", str(port)]
        return main_live_bridge(live_argv)

    return 2


if __name__ == "__main__":
    sys.exit(main())
