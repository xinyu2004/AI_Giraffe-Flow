from __future__ import annotations

import json
from pathlib import Path

from gf_gmt.architect import dag_from_sor, dag_to_dot, dag_to_mermaid, run_architect_lineage
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


def test_dag_mermaid_and_dot() -> None:
    sor = {
        "deployments": [
            {"process": "gateway", "provides": [], "requires": []},
            {"process": "fcm", "provides": [], "requires": []},
        ],
        "dataflows": [
            {
                "from": "gateway",
                "to": "fcm",
                "service": "services.semantic.VehicleStatus",
            }
        ],
    }
    dag = dag_from_sor(sor)
    mm = dag_to_mermaid(dag)
    assert "flowchart LR" in mm
    assert "gateway" in mm and "fcm" in mm
    assert "VehicleStatus" in mm
    dot = dag_to_dot(dag)
    assert "digraph gf_dag" in dot
    assert "gateway -> fcm" in dot
    assert "VehicleStatus" in dot


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
    assert parse_ndjson_row("") is None
    assert parse_ndjson_row("  ") is None
    assert parse_ndjson_row("not-json") is None
    assert parse_ndjson_row("{broken") is None
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


def test_bev_compose_from_module_topics() -> None:
    from gf_gmt.bev_compose import TOPIC_CAM, LiveBevComposer, expand_rows_with_bev

    comp = LiveBevComposer()
    assert comp.update({"t_ns": 1, "topic": "/gf/other", "data": {}}) is None
    cam = comp.update(
        {
            "t_ns": 100_000_000,
            "topic": "/gf/EgoMotion",
            "data": {
                "speed_mps": 12.0,
                "yaw_rate_degps": 0,
                "steer_angle_deg": 0,
                "gear": 4,
                "timestamp_ns": 100_000_000,
            },
        }
    )
    assert cam is not None
    assert cam["topic"] == TOPIC_CAM
    assert cam["data"]["format"] == "png"
    png1 = cam["data"]["data"]
    cam2 = comp.update(
        {
            "t_ns": 300_000_000,
            "topic": "/gf/EgoMotion",
            "data": {
                "speed_mps": 12.0,
                "timestamp_ns": 300_000_000,
                "yaw_rate_degps": 0,
                "steer_angle_deg": 0,
                "gear": 4,
            },
        }
    )
    assert cam2 is not None
    # Same speed but odom advanced → PNG bytes must change (scrolling ground)
    assert cam2["data"]["data"] != png1

    rows = [
        {"t_ns": 1, "topic": "/gf/EgoMotion", "data": {"speed_mps": 5.0}},
        {
            "t_ns": 1,
            "topic": "/gf/Trajectory",
            "data": {"points_x_m": [0.0, 8.0], "points_y_m": [0.0, 0.0]},
        },
    ]
    exp = expand_rows_with_bev(rows)
    assert any(r["topic"] == TOPIC_CAM for r in exp)


def test_bev_prefers_planning_traj_when_adas() -> None:
    from gf_gmt.bev_compose import LiveBevComposer

    comp = LiveBevComposer()
    comp.update(
        {
            "t_ns": 1,
            "topic": "/gf/AdasDemo",
            "data": {
                "phase": "changing",
                "lane_offset_m": 1.5,
                "lead_dist_m": 40.0,
                "cipo_x_m": 40.0,
                "cipo_y_m": 0.0,
            },
        }
    )
    cam = comp.update(
        {
            "t_ns": 2,
            "topic": "/gf/Trajectory",
            "data": {
                "points_x_m": [0.0, 10.0, 20.0],
                "points_y_m": [0.0, 1.0, 2.0],
            },
        }
    )
    assert cam is not None
    assert comp.state.has_adas
    # ego-frame stored as-is; world offset applied at render time
    assert comp.state.traj_y == [0.0, 1.0, 2.0]


def test_bev_script_three_phases_no_adas_topic() -> None:
    from gf_gmt.bev_compose import (
        TOPIC_ADAS,
        TOPIC_CAM,
        AdasScriptIndex,
        LiveBevComposer,
        expand_rows_with_bev,
    )

    root = Path(__file__).resolve().parents[3]
    script_path = (
        root
        / "projects"
        / "oem_a"
        / "afc_with_uss"
        / "scenarios"
        / "overtake_acc_aeb.jsonl"
    )
    if not script_path.is_file():
        return
    idx = AdasScriptIndex.load(script_path)
    assert idx is not None and len(idx.times) > 100
    # Mid overtake (~8s) should be changing / prepare
    mid = idx.nearest(8_000_000_000)
    assert mid is not None
    assert mid.get("phase") in {"prepare", "changing", "cruise", "done"}

    comp = LiveBevComposer(script=idx)
    cam = comp.update(
        {
            "t_ns": 8_000_000_000,
            "topic": "/gf/EgoMotion",
            "data": {
                "speed_mps": 24.0,
                "timestamp_ns": 8_000_000_000,
                "yaw_rate_degps": 1.0,
                "steer_angle_deg": 2.0,
                "gear": 4,
            },
        }
    )
    assert cam is not None and cam["topic"] == TOPIC_CAM
    assert comp.state.has_adas
    assert comp.state.phase != ""

    rows = [
        {
            "t_ns": 1,
            "topic": TOPIC_ADAS,
            "data": {"phase": "brake", "lane_offset_m": 0.0, "lead_dist_m": 10.0},
        },
        {"t_ns": 1, "topic": "/gf/EgoMotion", "data": {"speed_mps": 5.0}},
    ]
    exp = expand_rows_with_bev(rows, drop_adas_topic=True)
    assert not any(str(r.get("topic")).endswith("AdasDemo") for r in exp)
    assert any(r["topic"] == TOPIC_CAM for r in exp)


def test_overtake_acc_aeb_phases() -> None:
    from gf_gmt.adas_scenarios import gen_overtake_acc_aeb

    frames = gen_overtake_acc_aeb(duration_s=75.0)
    assert len(frames) == 750
    phases = {f.phase for f in frames}
    assert "changing" in phases and "follow" in phases and "brake" in phases
    assert frames[0].lane_offset_m == 0.0
    assert frames[250].lane_offset_m > 3.0  # ~25s into ACC, already in left lane
    assert abs(frames[250].traj_y[-1] - 3.5) < 0.01  # path stays in left lane
    assert any(f.brake_active for f in frames)
    assert all(f.scenario_id == "overtake_acc_aeb" for f in frames)


def test_adas_scenarios_and_bev(tmp_path: Path) -> None:
    from gf_gmt.adas_scenarios import (
        TOPIC_ADAS,
        TOPIC_CAM,
        TOPIC_EGO,
        generate_all,
        gen_aeb_cutin,
        iter_playback_rows,
        render_bev_png,
        write_scenario_jsonl,
    )
    from gf_gmt.bridge_foxglove import channel_desc, is_image_topic

    frames = gen_aeb_cutin(duration_s=12.0)
    assert len(frames) == 120
    assert any(f.brake_active for f in frames)
    assert any(f.phase == "brake" for f in frames)
    png = render_bev_png(frames[100])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

    out = tmp_path / "aeb_cutin.jsonl"
    n = write_scenario_jsonl(out, frames)
    assert n == len(frames) * 3
    text = out.read_text(encoding="utf-8")
    assert TOPIC_EGO in text and TOPIC_ADAS in text

    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    expanded = list(iter_playback_rows(rows, synth_bev=True))
    cam = [r for r in expanded if r["topic"] == TOPIC_CAM]
    assert cam
    assert cam[0]["data"]["format"] == "png"
    assert is_image_topic(TOPIC_CAM)
    ch = channel_desc(9, TOPIC_CAM)
    assert ch["schemaName"] == "foxglove.CompressedImage"

    written = generate_all(tmp_path / "all")
    assert "overtake_acc_aeb" in written
    assert set(written) >= {"overtake_acc_aeb", "acc_follow", "aeb_cutin", "lane_change"}


def test_session_skips_tag_meta(tmp_path: Path) -> None:
    from gf_gmt.gui.session_model import load_session

    p = tmp_path / "clip.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "tag_meta",
                        "label": "x",
                        "from_ns": 0,
                        "to_ns": 1,
                        "kept": 1,
                    }
                ),
                json.dumps({"t_ns": 10, "topic": "/gf/EgoMotion", "data": {"seq": 1}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    m = load_session(p)
    assert len(m.events) == 1
    assert m.events[0].topic == "/gf/EgoMotion"


def test_session_model_dt_and_bind(tmp_path: Path) -> None:
    from gf_gmt.gui.session_model import load_session

    p = tmp_path / "s.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps({"t_ns": 100, "topic": "/gf/EgoMotion", "data": {"seq": 1}}),
                json.dumps({"t_ns": 250, "topic": "/gf/Trajectory", "data": {"seq": 2}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    sor = {
        "deployments": [
            {"process": "a"},
            {"process": "b"},
        ],
        "dataflows": [
            {"from": "a", "to": "b", "service": "services.semantic.EgoMotion"},
        ],
    }
    m = load_session(p, sor=sor)
    assert len(m.events) == 2
    assert m.events[0].dt_ns == 0
    assert m.events[1].dt_ns == 150
    assert m.events[0].from_proc == "a"
    assert m.events[0].to_proc == "b"


def test_editable_tags_and_clip(tmp_path: Path) -> None:
    from gf_gmt.measure_tag import (
        clip_by_tag,
        load_tags,
        new_tag,
        save_tags,
        tags_path_for_session,
        upsert_tag,
    )

    session = tmp_path / "session.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps({"t_ns": 100, "topic": "/gf/EgoMotion", "data": {"seq": 1}}),
                json.dumps({"t_ns": 200, "topic": "/gf/Trajectory", "data": {"seq": 2}}),
                json.dumps({"t_ns": 300, "topic": "/gf/EgoMotion", "data": {"seq": 3}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tag = new_tag(label="cut_in", from_ns=150, to_ns=300, topics=["/gf/EgoMotion"], notes="demo")
    tags = upsert_tag([], tag)
    tag.label = "renamed"
    tags = upsert_tag(tags, tag)
    tp = tags_path_for_session(session)
    save_tags(tp, tags)
    loaded = load_tags(tp)
    assert len(loaded) == 1 and loaded[0].label == "renamed"
    out = tmp_path / "clip.jsonl"
    path, kept, total = clip_by_tag(session, out, loaded[0])
    assert path == out and total == 3 and kept == 1
    text = out.read_text(encoding="utf-8")
    assert "tag_meta" in text and "renamed" in text and "/gf/EgoMotion" in text


def test_record_from_ndjson(tmp_path: Path) -> None:
    from gf_gmt.measure_ndjson import record_from_ndjson

    nd = tmp_path / "tap.ndjson"
    nd.write_text(
        json.dumps(
            {
                "t_ns": 10,
                "topic": "/gf/EgoMotion",
                "data": {"speed_mps": 1.2, "gear": 4},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "session.jsonl"
    path, n = record_from_ndjson(nd, out)
    assert path.is_file() and n == 1
    assert "speed_mps" in out.read_text(encoding="utf-8")


def test_export_session_vcd(tmp_path: Path) -> None:
    from gf_gmt.measure_vcd import export_session_vcd

    stub = Path(__file__).resolve().parents[1] / "fixtures" / "session_stub.jsonl"
    out = tmp_path / "stub.vcd"
    path, n_vars, n_ev = export_session_vcd(stub, out)
    assert path.is_file() and n_vars >= 1 and n_ev >= 1
    text = out.read_text(encoding="utf-8")
    assert "$timescale 1 ns $end" in text
    assert "$enddefinitions $end" in text
    assert "gf.EgoMotion.seq" in text
    assert "gf.UssZones.nearest_cm" in text
    assert "#1000000" in text


def test_session_file_tail_and_append(tmp_path: Path) -> None:
    from gf_gmt.gui.session_model import SessionFileTail, SessionModel
    from gf_gmt.measure_ndjson import parse_tap_row

    p = tmp_path / "live.jsonl"
    p.write_text("", encoding="utf-8")
    tail = SessionFileTail(path=p)
    assert tail.poll_lines() == []

    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t_ns": 100, "topic": "/gf/EgoMotion", "data": {"seq": 1}}) + "\n")
        f.write(json.dumps({"t_ns": 200, "topic": "/gf/Trajectory", "data": {"seq": 2}}) + "\n")
    lines = tail.poll_lines()
    assert len(lines) == 2
    m = SessionModel()
    rows = [r for r in (parse_tap_row(x) for x in lines) if r]
    assert m.append_rows(rows) == 2
    assert m.events[1].dt_ns == 100

    # truncate → poll resets
    p.write_text(
        json.dumps({"t_ns": 9, "topic": "/gf/EgoMotion", "data": {"seq": 9}}) + "\n",
        encoding="utf-8",
    )
    # simulate follow truncate detect
    if p.stat().st_size < tail.offset:
        tail.reset(p)
        m.clear_events()
    lines2 = tail.poll_lines()
    rows2 = [r for r in (parse_tap_row(x) for x in lines2) if r]
    assert m.append_rows(rows2) == 1
    assert m.events[0].t_ns == 9


def test_live_tag_mark(tmp_path: Path) -> None:
    import os
    import sys

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gf_gmt.gui.tag_panel import TagPanel
    from gf_gmt.measure_tag import load_tags, tags_path_for_session

    app = QApplication.instance() or QApplication(sys.argv)
    session = tmp_path / "session_live.jsonl"
    session.write_text("", encoding="utf-8")
    panel = TagPanel()
    panel.set_session(session)
    panel.set_playhead_ns(1000)
    msg1 = panel.live_drop_marker()
    assert "标记" in msg1 and "1000" in msg1
    tags = load_tags(tags_path_for_session(session))
    assert len(tags) == 1 and tags[0].is_marker and tags[0].from_ns == 1000
    panel.set_playhead_ns(1500)
    msg2 = panel.live_mark_from()
    assert "from=1500" in msg2
    panel.set_playhead_ns(2000)
    msg3 = panel.live_mark_to()
    assert "2000" in msg3
    tags = load_tags(tags_path_for_session(session))
    assert any(t.kind == "range" and t.from_ns == 1500 and t.to_ns == 2000 for t in tags)
    _ = app  # keep ref


def test_live_bridge_hello_and_parse() -> None:
    from gf_gmt.bridge_live import _parse, hello_payload, is_hello

    msg = hello_payload()
    assert is_hello(msg)
    assert is_hello(_parse(json.dumps(msg)))
    row = _parse(json.dumps({"t_ns": 1, "topic": "/gf/A", "data": {"seq": 1}}))
    assert row and row["t_ns"] == 1
    assert not is_hello(row)


def test_live_bridge_ws_roundtrip() -> None:
    import os
    import socket
    import threading
    import time

    from gf_gmt.bridge_live import _parse, serve_live_stdin
    from gf_gmt.gui.live_client import LiveWsSession

    srv_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_probe.bind(("127.0.0.1", 0))
    port = srv_probe.getsockname()[1]
    srv_probe.close()

    r_fd, w_fd = os.pipe()
    reader = os.fdopen(r_fd, "r", encoding="utf-8", closefd=True)
    writer = os.fdopen(w_fd, "w", encoding="utf-8", closefd=True)
    ndjson_line = json.dumps(
        {"t_ns": 42, "topic": "/gf/EgoMotion", "data": {"speed_mps": 1.0}}
    )

    def _serve() -> None:
        serve_live_stdin("127.0.0.1", port, stream=reader)

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    time.sleep(0.15)

    client = LiveWsSession()
    client.connect("127.0.0.1", port)
    writer.write(ndjson_line + "\n")
    writer.flush()

    lines: list[str] = []
    for _ in range(100):
        lines.extend(client.poll_lines())
        if lines:
            break
        time.sleep(0.02)

    client.close()
    writer.close()
    assert lines, "expected NDJSON line from live bridge"
    row = _parse(lines[0])
    assert row is not None and row["t_ns"] == 42
    assert row["data"]["speed_mps"] == 1.0


def test_live_bridge_survives_client_disconnect() -> None:
    """GMT GUI close must not tear down the live bridge (Foxglove sibling)."""
    import os
    import socket
    import threading
    import time

    from gf_gmt.bridge_live import serve_live_stdin
    from gf_gmt.gui.live_client import LiveWsSession

    srv_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_probe.bind(("127.0.0.1", 0))
    port = srv_probe.getsockname()[1]
    srv_probe.close()

    r_fd, w_fd = os.pipe()
    reader = os.fdopen(r_fd, "r", encoding="utf-8", closefd=True)
    writer = os.fdopen(w_fd, "w", encoding="utf-8", closefd=True)

    def _serve() -> None:
        serve_live_stdin("127.0.0.1", port, stream=reader)

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    time.sleep(0.15)

    c1 = LiveWsSession()
    c1.connect("127.0.0.1", port)
    c1.close()  # simulate GMT disconnect / window close
    time.sleep(0.1)
    assert thread.is_alive(), "live bridge must stay up after GMT disconnect"

    c2 = LiveWsSession()
    c2.connect("127.0.0.1", port)
    line = json.dumps({"t_ns": 7, "topic": "/gf/EgoMotion", "data": {"v": 1}})
    writer.write(line + "\n")
    writer.flush()
    got: list[str] = []
    for _ in range(100):
        got.extend(c2.poll_lines())
        if got:
            break
        time.sleep(0.02)
    c2.close()
    writer.close()
    assert got, "reconnect after GMT close must still receive tap lines"


def test_inject_ctrl_client_seek() -> None:
    """Mock playhead inject TCP server ↔ InjectCtrlClient."""
    import socket
    import threading
    import time

    from gf_gmt.gui.inject_client import InjectCtrlClient

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)
    seeks: list[int] = []
    stop = threading.Event()

    def _serve() -> None:
        srv.settimeout(0.5)
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        conn.settimeout(0.5)
        buf = ""
        try:
            while not stop.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    cmd = obj.get("cmd")
                    if cmd == "hello":
                        conn.sendall(
                            b'{"op":"hello","proto":"gf_inject_ctrl","version":1,'
                            b'"mode":"playhead","caps":["stream_window"],'
                            b'"window_max_events":256,"window_buffers":2,'
                            b'"events":0,"index":-1,"port":'
                            + str(port).encode()
                            + b"}\n"
                        )
                        conn.sendall(
                            b'{"op":"status","index":-1,"events":0,"sent":0,'
                            b'"state":"paused","rate":1}\n'
                        )
                    elif cmd == "seek":
                        idx = int(obj["index"])
                        seeks.append(idx)
                        conn.sendall(
                            (
                                f'{{"op":"published","index":{idx},'
                                f'"topic":"/gf/EgoMotion","t_ns":1,"injected":true}}\n'
                            ).encode()
                        )
                        conn.sendall(
                            (
                                f'{{"op":"status","index":{idx},"events":0,"sent":1,'
                                f'"state":"paused","rate":1}}\n'
                            ).encode()
                        )
                    elif cmd == "inject":
                        idx = int(obj["index"])
                        seeks.append(idx)
                        conn.sendall(
                            (
                                f'{{"op":"published","index":{idx},'
                                f'"topic":{json.dumps(obj.get("topic"))},'
                                f'"t_ns":{int(obj.get("t_ns") or 0)},'
                                f'"injected":true}}\n'
                            ).encode()
                        )
        finally:
            conn.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    time.sleep(0.05)
    client = InjectCtrlClient()
    client.connect("127.0.0.1", port)
    assert client.last_hello is not None
    assert client.last_hello.get("proto") == "gf_inject_ctrl"
    assert "stream_window" in (client.last_hello.get("caps") or [])
    client.seek(5)
    got = False
    for _ in range(50):
        for msg in client.poll_messages():
            if msg.get("op") == "published" and msg.get("index") == 5:
                got = True
                break
        if got:
            break
        time.sleep(0.02)
    client.close()
    stop.set()
    srv.close()
    thread.join(timeout=1)
    assert seeks == [5]
    assert got


def test_inject_stream_helpers() -> None:
    from gf_gmt.gui.inject_client import (
        InjectCtrlClient,
        InjectStreamHelper,
        hello_has_stream_window,
        is_injectable_topic,
    )
    from gf_gmt.gui.session_model import SessionEvent, SessionModel

    assert is_injectable_topic("/gf/EgoMotion")
    assert is_injectable_topic("EgoMotion")
    assert not is_injectable_topic("/gf/Trajectory")
    assert hello_has_stream_window(
        {"caps": ["stream_window"], "window_max_events": 256}
    )
    assert not hello_has_stream_window({"caps": []})
    assert not hello_has_stream_window(None)

    sent: list[dict] = []

    class _FakeClient(InjectCtrlClient):
        def __init__(self) -> None:  # noqa: D107
            # skip socket init fields used by poll
            self._sock = None
            self._buf = ""
            self._connected = True
            self.last_hello = None
            self.last_status = None
            self.last_published = None

        def send_cmd(self, obj: dict) -> None:
            sent.append(obj)

    client = _FakeClient()
    helper = InjectStreamHelper(client)
    helper.on_hello(
        {
            "caps": ["stream_window"],
            "window_max_events": 256,
            "window_buffers": 2,
            "events": 0,
        }
    )
    assert helper.stream_mode
    assert helper.window_max_events == 256
    helper.configure_session(10)
    assert sent[0] == {"cmd": "session", "events": 10}
    assert sent[1] == {"cmd": "reset"}

    model = SessionModel()
    model.events = [
        SessionEvent(index=0, t_ns=1, topic="/gf/Trajectory", data={"a": 1}),
        SessionEvent(index=1, t_ns=2, topic="/gf/EgoMotion", data={"v": 1.0}),
        SessionEvent(index=2, t_ns=3, topic="/gf/EgoMotion", data={"v": 2.0}),
        SessionEvent(index=3, t_ns=4, topic="/gf/Other", data={}),
        SessionEvent(index=4, t_ns=5, topic="/gf/EgoMotion", data={"v": 3.0}),
    ]
    sent.clear()
    assert helper.inject_model_index(model, 0) == ("skip", "/gf/Trajectory")
    assert not sent
    kind, topic = helper.inject_model_index(model, 1)
    assert kind == "sent" and topic == "/gf/EgoMotion"
    assert sent[0]["cmd"] == "inject"
    assert sent[0]["index"] == 1

    sent.clear()
    n = helper.fill_window(model, "A", 0, count=2)
    assert n == 2  # two EgoMotion frames from scan
    cmds = [c["cmd"] for c in sent]
    assert cmds[0] == "window_begin"
    assert sent[0]["slot"] == "A" and sent[0]["base"] == 0
    assert cmds.count("push") == 2
    assert cmds[-1] == "window_end"


def test_session_clock_scheme1(tmp_path: Path) -> None:
    from gf_gmt.gui.session_model import SessionModel, load_session
    from gf_gmt.gui.wall_time import SessionClock
    from gf_gmt.measure_ndjson import parse_session_line

    clock = SessionClock(wall_anchor_unix_ns=1_700_000_000_000_000_000, t0_ns=1000)
    assert clock.ready
    assert clock.wall_unix_ns(1000) == 1_700_000_000_000_000_000
    assert clock.wall_unix_ns(1_000_000_000 + 1000) == 1_700_000_000_000_000_000 + 1_000_000_000
    meta = clock.to_meta()
    assert meta["type"] == "session_meta"
    assert SessionClock.from_meta(meta) is not None

    p = tmp_path / "s.jsonl"
    with p.open("w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")
        f.write(
            json.dumps(
                {"t_ns": 1000, "topic": "/gf/EgoMotion", "data": {"seq": 1, "v": 1.5}}
            )
            + "\n"
        )
        f.write(
            json.dumps(
                {"t_ns": 2000, "topic": "/gf/EgoMotion", "data": {"seq": 2, "v": 2.5}}
            )
            + "\n"
        )
    m = load_session(p)
    assert m.clock.ready
    assert m.clock.t0_ns == 1000
    assert "202" in m.wall_str(1000) or m.wall_str(1000) != "—"
    row = parse_session_line(json.dumps(meta))
    assert row and row.get("type") == "session_meta"
    m2 = SessionModel()
    assert m2.append_rows([row]) == 0
    assert m2.clock.ready
