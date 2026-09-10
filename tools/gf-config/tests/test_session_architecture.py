"""Session layer rules: topology, node_ui None-skip, normalize_after_open."""

from __future__ import annotations

from gf_config.core import ProjectSession


def _session() -> ProjectSession:
    s = object.__new__(ProjectSession)
    s.req = {"topology": "ap_only"}
    s.wiring = {
        "topology": "ap_mcu_cp",  # legacy dual key
        "deployments": [],
        "dataflows": [],
        "channel_flows": [],
        "canvas": {"nodes": {"host.gateway": {"x": 1.0, "kind": "process"}}},
    }
    s.dirty_wiring = False
    s.dirty_req = False
    s.dirty_ara_cfg = set()
    return s


def test_normalize_drops_wiring_topology_without_dirty_when_req_has_it() -> None:
    s = _session()
    s.normalize_after_open()
    assert "topology" not in s.wiring
    assert s.topology() == "ap_only"
    assert not s.dirty_wiring
    assert not s.dirty_req


def test_normalize_lifts_wiring_topology_into_req() -> None:
    s = _session()
    del s.req["topology"]
    s.normalize_after_open()
    assert s.topology() == "ap_mcu_cp"
    assert s.dirty_req
    assert "topology" not in s.wiring


def test_set_topology_single_source() -> None:
    s = _session()
    s.wiring.pop("topology", None)
    s.set_topology("ap_mcu_cp")
    assert s.req["topology"] == "ap_mcu_cp"
    assert s.dirty_req
    assert "topology" not in s.wiring


def test_set_node_ui_none_skips_not_deletes() -> None:
    s = _session()
    s.set_node_ui("host.gateway", kind=None, label=None, x=2.0)
    ui = s.get_node_ui("host.gateway")
    assert ui.get("kind") == "process"
    assert ui.get("x") == 2.0


def test_get_node_ui_does_not_create() -> None:
    s = _session()
    assert s.get_node_ui("missing.proc") == {}
    nodes = (s.wiring.get("canvas") or {}).get("nodes") or {}
    assert "missing.proc" not in nodes


def test_update_ara_doc_marks_only_that_key() -> None:
    s = _session()
    s.ara_cfg = {}
    s.dirty_ara_cfg = set()
    assert s.update_ara_doc("log", default_level="DEBUG", sinks=["console"]) is True
    assert s.get_ara_doc("log")["default_level"] == "DEBUG"
    assert s.get_ara_doc("log")["schema_version"] == "0.1"
    assert s.dirty_ara_cfg == {"log"}
    s.dirty_ara_cfg.clear()
    assert s.update_ara_doc("log", default_level="DEBUG", sinks=["console"]) is False
    assert s.dirty_ara_cfg == set()
