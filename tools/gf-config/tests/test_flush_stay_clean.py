"""Open → flush editors must not mark dirty (quit-without-edit)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gf_config.core import ProjectSession  # noqa: E402
from gf_config.gui.ara_cfg_editor import AraCfgEditor  # noqa: E402
from gf_config.gui.wiring_graph import WiringGraphView  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _open(sku: str) -> ProjectSession:
    giraffe = ROOT / "projects" / sku / "giraffe.yaml"
    if not giraffe.is_file():
        pytest.skip(f"{sku} project missing")
    return ProjectSession.open(giraffe)


def _flush_both(sess: ProjectSession) -> None:
    graph = WiringGraphView()
    ara = AraCfgEditor()
    graph.set_session(sess)
    ara.set_session(sess)
    graph.flush_canvas()
    ara.flush_to_session()


@pytest.mark.parametrize("sku", ["adc", "afc"])
def test_open_flush_stay_clean(qapp: QApplication, sku: str) -> None:
    sess = _open(sku)
    assert not sess.is_dirty()
    _flush_both(sess)
    assert not sess.is_dirty(), (
        f"{sku} flush dirtied req={sess.dirty_req} wiring={sess.dirty_wiring} "
        f"ara={sorted(sess.dirty_ara_cfg or [])}"
    )


def test_afc_log_file_max_edit_dirties(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    assert "file_max_bytes" not in sess.get_ara_doc("log")
    ara._log_file_max.setValue(4096)
    assert "log" in (sess.dirty_ara_cfg or set())
    assert sess.get_ara_doc("log")["file_max_bytes"] == 4096
