"""Session rules: frame_ingest not in deployments; default channel_flows seed."""

from __future__ import annotations

from gf_config.core import ProjectSession


def _session() -> ProjectSession:
    # Minimal in-memory session without loading giraffe.yaml
    s = object.__new__(ProjectSession)
    s.req = {
        "frame_ingest": {
            "active_source": "isp",
            "camera_slots": [
                {"id": "front", "w": 640, "h": 480},
                {"id": "fl", "w": 640, "h": 480},
                {"id": "fr", "w": 640, "h": 480},
            ],
        }
    }
    s.wiring = {
        "deployments": [
            {"process": "perception.fcm", "provides": [], "requires": []},
            {"process": "perception.surround", "provides": [], "requires": []},
            {"process": "host.frame_ingest", "provides": [], "requires": []},
        ],
        "dataflows": [],
        "channel_flows": [],
        "canvas": {"nodes": {}},
    }
    s.dirty_wiring = False
    s.dirty_req = False
    return s


def test_scrub_frame_ingest_from_deployments() -> None:
    s = _session()
    s.scrub_frame_ingest_from_deployments()
    names = {str(d.get("process")) for d in s.deployments()}
    assert "host.frame_ingest" not in names
    assert "perception.fcm" in names


def test_upsert_refuses_frame_ingest() -> None:
    s = _session()
    s.scrub_frame_ingest_from_deployments()
    s.upsert_deployment("host.frame_ingest", provides=[], requires=[])
    names = {str(d.get("process")) for d in s.deployments()}
    assert "host.frame_ingest" not in names


def test_seed_default_channel_flows() -> None:
    s = _session()
    s.scrub_frame_ingest_from_deployments()
    s.seed_default_channel_flows()
    flows = {(f.get("slot"), f.get("to")) for f in s.channel_flows()}
    assert ("gf.channel.front", "perception.fcm") in flows
    assert ("gf.channel.fl", "perception.surround") in flows
    assert ("gf.channel.fr", "perception.surround") in flows
    # idempotent
    s.seed_default_channel_flows()
    assert len(s.channel_flows()) == 3
