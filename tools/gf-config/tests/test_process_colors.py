"""Canvas process colours: anti-adjacent hues + stable fallback."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsSimpleTextItem  # noqa: E402

from gf_config.gui.wiring_graph_items import (  # noqa: E402
    _hue_dist,
    assign_process_colors,
    build_process_color_adjacency,
    deconflict_edge_labels,
    parse_canvas_color,
    process_color,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_assign_neighbours_prefer_large_hue_gap() -> None:
    names = ["perception.surround", "planning.parking", "perception.fcm"]
    # Clique: all adjacent — no shared colour, large min gap.
    adj = {
        "perception.surround": {"planning.parking", "perception.fcm"},
        "planning.parking": {"perception.surround", "perception.fcm"},
        "perception.fcm": {"perception.surround", "planning.parking"},
    }
    colors = assign_process_colors(names, adj)
    assert len({c.name() for c in colors.values()}) == 3
    pairs = [
        ("perception.surround", "planning.parking"),
        ("perception.surround", "perception.fcm"),
        ("planning.parking", "perception.fcm"),
    ]
    for a, b in pairs:
        assert _hue_dist(colors[a], colors[b]) >= 0.12


def test_assign_unique_when_board_fits_palette() -> None:
    """ADC-sized board: non-adjacent processes must still not reuse colours."""
    names = [
        "adapter.vehicle_can_gateway",
        "perception.fcm",
        "perception.surround",
        "planning.driving_plus",
        "planning.parking",
        "mode.drive_park",
        "host.frame_ingest",
    ]
    # Sparse conflict graph (only gateway hub) — old greedy would collide.
    adj = {
        "adapter.vehicle_can_gateway": {
            "perception.fcm",
            "perception.surround",
            "planning.driving_plus",
            "planning.parking",
            "mode.drive_park",
        },
        "perception.fcm": {"adapter.vehicle_can_gateway", "planning.driving_plus"},
        "perception.surround": {
            "adapter.vehicle_can_gateway",
            "planning.parking",
            "planning.driving_plus",
        },
        "planning.driving_plus": {
            "adapter.vehicle_can_gateway",
            "perception.fcm",
            "perception.surround",
        },
        "planning.parking": {
            "adapter.vehicle_can_gateway",
            "perception.surround",
            "mode.drive_park",
        },
        "mode.drive_park": {"adapter.vehicle_can_gateway", "planning.parking"},
        "host.frame_ingest": set(),
    }
    colors = assign_process_colors(names, adj)
    assert len({c.name().lower() for c in colors.values()}) == len(names)
    # Classic screenshot collisions must be gone.
    assert colors["planning.parking"].name() != colors["planning.driving_plus"].name()
    assert colors["perception.fcm"].name() != colors["mode.drive_park"].name()


def test_k_nearest_links_far_canvas_coords() -> None:
    names = ["a", "b", "c"]
    flows: list[dict] = []
    # ADC-like large coords: absolute near_px alone would miss a↔b at 444px.
    positions = {"a": (0.0, 0.0), "b": (444.0, 0.0), "c": (5000.0, 0.0)}
    adj = build_process_color_adjacency(
        names, flows=flows, positions=positions, near_px=100.0, k_nearest=1
    )
    assert "b" in adj["a"]
    assert "c" not in adj["a"] or "b" in adj["a"]


def test_process_color_map_overrides_hash(qapp: QApplication) -> None:
    class G:
        _process_color_map = {"demo.proc": QColor("#e74c3c")}

    assert process_color("demo.proc", G()).name() == QColor("#e74c3c").name()
    # Without map: still a valid palette colour
    c = process_color("demo.proc", None)
    assert c.isValid()


def test_deconflict_edge_labels_separates_boxes(qapp: QApplication) -> None:
    class FakeEdge:
        def __init__(self, src: str, dst: str, svc: str, x: float, y: float) -> None:
            self.src = type("S", (), {"process_name": src})()
            self.dst = type("D", (), {"process_name": dst})()
            self.service = svc
            self._label = QGraphicsSimpleTextItem(svc)
            self._label.setPos(x, y)
            self._label_anchor = QPointF(x, y)

    # Same anchor → would overlap without deconflict
    e1 = FakeEdge("s", "d", "SurroundWorld", 100.0, 100.0)
    e2 = FakeEdge("s", "d", "FreespaceNear", 100.0, 100.0)
    deconflict_edge_labels([e1, e2])
    r1 = e1._label.boundingRect().translated(e1._label.pos())
    r2 = e2._label.boundingRect().translated(e2._label.pos())
    assert not r1.intersects(r2)


def test_label_stagger_separates_parallel_corridor(qapp: QApplication) -> None:
    """Same src→dst edges must get non-zero opposite stagger (survives update_path)."""
    from gf_config.gui.wiring_graph_items import EdgeCurve, ProcessCard

    src = ProcessCard("perception.surround", ["SurroundWorld", "FreespaceNear"], [], 0, 0)
    dst = ProcessCard(
        "planning.parking",
        [],
        ["SurroundWorld", "FreespaceNear"],
        0,
        200,
    )
    e1 = EdgeCurve(src, dst, "SurroundWorld", {}, 0, 1)
    e2 = EdgeCurve(src, dst, "FreespaceNear", {}, 0, 1)
    s1 = e1._label_stagger()
    s2 = e2._label_stagger()
    assert s1.x() != s2.x() or s1.y() != s2.y()
    # Opposite sides of the midpoint for a 2-edge corridor
    assert s1.x() == -s2.x()
    assert s1.y() == -s2.y()
    assert abs(s1.x()) >= 40.0


def test_parse_canvas_color() -> None:
    assert parse_canvas_color("#e74c3c").name().lower() == "#e74c3c"
    assert parse_canvas_color("5dade2").name().lower() == "#5dade2"
    assert parse_canvas_color("") is None
    assert parse_canvas_color("not-a-color") is None


def test_assign_keeps_user_lock_and_avoids_its_hue() -> None:
    names = ["a", "b", "c"]
    adj = {"a": {"b"}, "b": {"a"}, "c": set()}
    locked = {"a": QColor("#e74c3c")}
    colors = assign_process_colors(names, adj, locked=locked)
    assert colors["a"].name().lower() == "#e74c3c"
    assert colors["b"].name().lower() != "#e74c3c"
    assert colors["c"].name().lower() != "#e74c3c"
    assert len({c.name().lower() for c in colors.values()}) == 3


def test_assign_preferred_sticky_until_clash() -> None:
    names = ["a", "b"]
    adj = {"a": {"b"}, "b": {"a"}}
    pref = {"a": QColor("#5dade2"), "b": QColor("#5dade2")}  # clash
    colors = assign_process_colors(names, adj, preferred=pref)
    # One may keep preferred; the other must differ.
    assert colors["a"].name().lower() != colors["b"].name().lower()
    # Non-clashing preferred sticks.
    colors2 = assign_process_colors(
        names,
        {"a": set(), "b": set()},
        preferred={"a": QColor("#f5b041"), "b": QColor("#9b59b6")},
    )
    assert colors2["a"].name().lower() == "#f5b041"
    assert colors2["b"].name().lower() == "#9b59b6"
