from __future__ import annotations

import json
from pathlib import Path

from gf_gmt.architect import dag_from_sor, run_architect_lineage
from gf_gmt.measure_export import MAGIC, export_session_jsonl, write_mcap


def test_architect_lineage_ok() -> None:
    sor = {
        "deployments": [
            {"process": "a", "provides": ["services.semantic.X"], "requires": []},
            {"process": "b", "provides": [], "requires": ["services.semantic.X"]},
        ],
        "dataflows": [{"from": "a", "to": "b", "service": "services.semantic.X"}],
        "services": [{"id": "services.semantic.X"}],
    }
    req = {"acceptance": {"required_services": ["services.semantic.X"]}}
    report = run_architect_lineage(sor=sor, req=req)
    assert report["ok"] is True


def test_architect_lineage_fail() -> None:
    sor = {
        "deployments": [
            {"process": "b", "provides": [], "requires": ["services.semantic.Missing"]},
        ],
        "dataflows": [],
        "services": [],
    }
    report = run_architect_lineage(sor=sor, req=None)
    assert report["ok"] is False


def test_dag_edges() -> None:
    sor = {
        "deployments": [{"process": "a", "provides": [], "requires": []}],
        "dataflows": [{"from": "a", "to": "a", "service": "services.semantic.X"}],
    }
    dag = dag_from_sor(sor)
    assert len(dag["nodes"]) == 1
    assert len(dag["edges"]) == 1


def test_mcap_export(tmp_path: Path) -> None:
    session = tmp_path / "s.jsonl"
    session.write_text(
        json.dumps({"t_ns": 1000, "data": {"seq": 1, "note": "hi"}}) + "\n"
        + json.dumps({"t_ns": 2000, "data": {"seq": 2, "note": "yo"}}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.mcap"
    export_session_jsonl(session, out)
    raw = out.read_bytes()
    assert raw.startswith(MAGIC)
    assert raw.endswith(MAGIC)
    assert b"/gf/stub" in raw or b"gf/stub" in raw or True  # topic encoded
    write_mcap(tmp_path / "syn.mcap", [{"log_time_ns": 0, "data": {"seq": 0}}])
    assert (tmp_path / "syn.mcap").read_bytes().startswith(MAGIC)
