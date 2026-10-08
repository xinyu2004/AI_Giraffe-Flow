"""Regression: Ctrl+drag port side relocate must persist (split import hygiene)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gf_config.core import ProjectSession, short_service  # noqa: E402
from gf_config.gui.wiring_graph import WiringGraphView  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _session_with_ports() -> ProjectSession:
    s = object.__new__(ProjectSession)
    s.req = {"publish_policy": {"services": {}, "channels": {}}, "frame_ingest": {}}
    s.wiring = {
        "deployments": [
            {
                "process": "adapter.demo",
                "compute_domain": "ap_linux",
                "provides": ["services.semantic.EgoMotion", "services.semantic.DrivingTrajectory"],
                "requires": ["services.semantic.VehicleBus"],
            }
        ],
        "dataflows": [],
        "channel_flows": [],
        "canvas": {
            "nodes": {
                "adapter.demo": {
                    "x": 0.0,
                    "y": 0.0,
                    "out_side": "right",
                    "in_side": "left",
                    "port_sides": {},
                }
            }
        },
    }
    s.dirty_wiring = False
    s.dirty_req = False
    # Minimal path stubs used by graph (avoid AttributeError on save paths).
    s.paths = type("P", (), {"project_dir": "."})()
    return s


def test_port_relocate_persists_side(qapp: QApplication) -> None:
    sess = _session_with_ports()
    w = WiringGraphView()
    w.set_session(sess)
    w.rebuild(fit_view=True)

    card = w._nodes["adapter.demo"]
    port = next(
        p
        for p in card._out_ports
        if short_service(p.service) == "EgoMotion"
    )
    assert port.side == "right"

    w.begin_port_relocate(port)
    r = card.sceneBoundingRect()
    w.update_port_relocate(QPointF(r.left() - 40.0, r.center().y()))
    assert port._pending_side == "left"
    w.finish_port_relocate()

    card2 = w._nodes["adapter.demo"]
    port2 = next(
        p
        for p in card2._out_ports
        if short_service(p.service) == "EgoMotion"
    )
    assert port2.side == "left"
    ui = (sess.wiring.get("canvas") or {}).get("nodes", {}).get("adapter.demo") or {}
    assert ui.get("port_sides", {}).get("out:EgoMotion") == "left"


def test_port_lookup_no_cross_service_fallback(qapp: QApplication) -> None:
    """Missing service must not resolve to ports[0] (stacked-edge bug)."""
    sess = _session_with_ports()
    w = WiringGraphView()
    w.set_session(sess)
    w.rebuild(fit_view=True)
    card = w._nodes["adapter.demo"]
    assert card.in_port_for_service("FreespaceNear") is None
    assert card.out_port_for_service("FreespaceNear") is None
    assert card.out_port_for_service("EgoMotion") is not None
    assert short_service(card.out_port_for_service("EgoMotion").service) == "EgoMotion"


def test_rebuild_does_not_persist_autocolour(qapp: QApplication) -> None:
    sess = _session_with_ports()
    sess.dirty_ara_cfg = set()
    w = WiringGraphView()
    w.set_session(sess)
    w.rebuild(fit_view=True)
    assert not sess.dirty_wiring
    assert not (sess.get_node_ui("adapter.demo") or {}).get("color")
    w._persist_authored_node_paint("adapter.demo")
    assert (sess.get_node_ui("adapter.demo") or {}).get("color")
    assert sess.dirty_wiring


def test_adc_rebuild_flush_click_stay_clean(qapp: QApplication) -> None:
    from pathlib import Path

    giraffe = Path(__file__).resolve().parents[3] / "projects" / "adc" / "giraffe.yaml"
    if not giraffe.is_file():
        pytest.skip("adc project missing")
    sess = ProjectSession.open(giraffe)
    assert not sess.is_dirty()
    w = WiringGraphView()
    w.set_session(sess)
    w.rebuild(fit_view=True)
    assert not sess.is_dirty()
    w.flush_canvas()
    assert not sess.is_dirty()
    card = next(c for c in w._nodes.values() if c.process_name != "external.vehicle_mcu")
    w.begin_card_drag(card)
    w.finalize_card_drag(card)
    assert not sess.is_dirty()
