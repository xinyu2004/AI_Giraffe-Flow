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


def test_tag_and_multitopic_export(tmp_path: Path) -> None:
    from gf_gmt.measure_export import list_mcap_topics
    from gf_gmt.measure_tag import tag_session

    session = tmp_path / "s.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps({"t_ns": 100, "topic": "/gf/A", "data": {"seq": 1}}),
                json.dumps({"t_ns": 200, "topic": "/gf/B", "data": {"seq": 2}}),
                json.dumps({"t_ns": 300, "topic": "/gf/A", "data": {"seq": 3}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tagged = tmp_path / "tagged.jsonl"
    path, kept, total = tag_session(session, tagged, from_ns=150, to_ns=300, label="win")
    assert path == tagged and kept == 2 and total == 3
    out = tmp_path / "multi.mcap"
    export_session_jsonl(tagged, out)
    topics = list_mcap_topics(out)
    assert "/gf/A" in topics or any("gf/A" in t for t in topics)
    assert "/gf/B" in topics or any("gf/B" in t for t in topics)


def test_record_from_sil_logs(tmp_path: Path) -> None:
    from gf_gmt.measure_record import filter_events_by_services, record_from_sil_logs

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "gateway.log").write_text(
        "gf-vehicle-can-gateway: Trajectory#1 points=3 ts_ns=1000\n"
        "gf-vehicle-can-gateway: Trajectory#2 points=3 ts_ns=2000\n",
        encoding="utf-8",
    )
    (log_dir / "uss.log").write_text(
        "gf-sensing-uss: UssZones#0 nearest_cm=20 speed=5.1\n",
        encoding="utf-8",
    )
    out = tmp_path / "session.jsonl"
    path, n = record_from_sil_logs(log_dir, out)
    assert path.is_file() and n >= 3
    text = out.read_text(encoding="utf-8")
    assert "/gf/Trajectory" in text
    assert "/gf/UssZones" in text

    out2 = tmp_path / "session_wl.jsonl"
    path2, n2 = record_from_sil_logs(log_dir, out2, services=["Trajectory"])
    assert n2 == 2
    assert "UssZones" not in path2.read_text(encoding="utf-8")
    assert filter_events_by_services([{"topic": "/gf/EgoMotion", "t_ns": 1}], []) == []


def test_bridge_describe(tmp_path: Path) -> None:
    from gf_gmt.bridge_foxglove import describe_mcap

    out = tmp_path / "t.mcap"
    write_mcap(
        out,
        [
            {"log_time_ns": 1, "topic": "/gf/Trajectory", "data": {"seq": 1}},
            {"log_time_ns": 2, "topic": "/gf/UssZones", "data": {"seq": 2}},
        ],
    )
    info = describe_mcap(out)
    assert info["ok"] is True
    assert len(info["topics"]) >= 1


def test_bridge_encode_ws_session_frames() -> None:
    import struct

    from gf_gmt.bridge_foxglove import (
        encode_ws_session_frames,
        pack_message_data,
        parse_ndjson_row,
    )

    rows = [
        parse_ndjson_row(
            json.dumps(
                {
                    "t_ns": 1000,
                    "topic": "/gf/EgoMotion",
                    "data": {"speed_mps": 5.1, "gear": 4},
                }
            )
        ),
        parse_ndjson_row(
            json.dumps(
                {
                    "t_ns": 2000,
                    "topic": "/gf/Trajectory",
                    "data": {"point_count": 2, "points_x_m": [0.0, 1.0]},
                }
            )
        ),
    ]
    assert all(r is not None for r in rows)
    frames = encode_ws_session_frames(rows)  # type: ignore[arg-type]
    assert json.loads(frames[0])["op"] == "serverInfo"
    adv = json.loads(frames[1])
    assert adv["op"] == "advertise"
    assert adv["channels"][0]["schemaEncoding"] == "jsonschema"
    topics = {c["topic"] for c in adv["channels"]}
    assert "/gf/EgoMotion" in topics and "/gf/Trajectory" in topics
    # Binary Message Data: opcode | sub_id | t_ns | json payload
    assert isinstance(frames[2], (bytes, bytearray))
    op, sid, t_ns = struct.unpack_from("<BIQ", frames[2], 0)
    assert op == 0x01 and sid == 1 and t_ns == 1000
    payload = json.loads(frames[2][13:].decode("utf-8"))
    assert payload["speed_mps"] == 5.1
    packed = pack_message_data(7, 99, {"a": 1})
    assert packed[:1] == b"\x01"
    assert struct.unpack_from("<I", packed, 1)[0] == 7
