"""Canvas edge_label_font_pt preference (persist + default)."""

from __future__ import annotations

from gf_config.core import ProjectSession


def test_edge_label_font_default_and_clamp() -> None:
    s = object.__new__(ProjectSession)
    s.wiring = {}
    s.dirty_wiring = False
    assert s.get_edge_label_font_pt() == ProjectSession.DEFAULT_EDGE_LABEL_FONT_PT

    s.set_edge_label_font_pt(12)
    assert s.dirty_wiring
    assert s.wiring["canvas"]["edge_label_font_pt"] == 12
    assert s.get_edge_label_font_pt() == 12

    s.set_edge_label_font_pt(99)
    assert s.get_edge_label_font_pt() == 18
    s.set_edge_label_font_pt(1)
    assert s.get_edge_label_font_pt() == 7
