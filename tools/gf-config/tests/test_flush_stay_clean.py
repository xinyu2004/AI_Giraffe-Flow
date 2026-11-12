"""Open → flush editors must not mark dirty (quit-without-edit)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

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


def test_tsync_page_flush_does_not_invent_network(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    keys = [
        ara._nav.item(i).data(Qt.ItemDataRole.UserRole) for i in range(ara._nav.count())
    ]
    assert "tsync" in keys
    ara.flush_to_session()
    assert "tsync" not in (sess.dirty_ara_cfg or set())
    assert "network" not in sess.get_ara_doc("tsync")
    assert sess.get_ara_doc("tsync")["backend"] == "osal_monotonic"
    assert sess.get_ara_doc("tsync")["pretend_synchronized"] is True


def test_tsync_gate_row_roundtrip(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    ara._add_tsync_gate_row(80, 0x80)
    net = sess.get_ara_doc("tsync")["network"]
    assert net["profile"] == "gates_only"
    assert net["cycle_us"] == 1000
    assert net["gate_list"] == [{"interval_us": 80, "gate_states": 0x80}]
    assert sess.get_ara_doc("tsync")["backend"] == "osal_monotonic"
    assert sess.dirty_ara_cfg is not None and "tsync" in sess.dirty_ara_cfg
    sess.dirty_ara_cfg.clear()
    ara.set_session(sess)
    ara.flush_to_session()
    assert not sess.dirty_ara_cfg
    assert sess.get_ara_doc("tsync")["network"]["gate_list"] == [
        {"interval_us": 80, "gate_states": 0x80}
    ]
    ara._tsync_gates.selectRow(0)
    ara._del_tsync_gate_rows()
    assert "network" not in sess.get_ara_doc("tsync")


def test_tsync_short_cycle_is_marked_on_the_nav(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    ara._add_tsync_gate_row(80, 0x80)
    assert "还差 920" in ara._tsync_sum.text()
    assert "最后一行" in ara._tsync_sum.text()
    title = _tsync_nav_text(ara)
    assert "周期未对齐" in title
    net = sess.get_ara_doc("tsync")["network"]
    assert "preemptable_mask" not in net
    assert "max_sdu" not in net
    ara._fill_tsync_demo()
    assert "周期未对齐" not in _tsync_nav_text(ara)
    assert "等于周期" in ara._tsync_sum.text()


def test_tsync_preempt_and_sdu_roundtrip(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    ara._add_tsync_gate_row(1000, 0x20)
    ara._tsync_preempt[2].setChecked(True)
    ara._tsync_sdu[5].setValue(1500)
    net = sess.get_ara_doc("tsync")["network"]
    assert net["preemptable_mask"] == 0x04
    assert net["max_sdu"] == [{"queue": 5, "bytes": 1500}]
    sess.dirty_ara_cfg.clear()
    ara.set_session(sess)
    ara.flush_to_session()
    assert not sess.dirty_ara_cfg
    ara._tsync_preempt[2].setChecked(False)
    ara._tsync_sdu[5].setValue(0)
    net = sess.get_ara_doc("tsync")["network"]
    assert net["gate_list"]
    assert "preemptable_mask" not in net
    assert "max_sdu" not in net


def test_tsync_stream_filter_and_meter_roundtrip(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    ara._add_tsync_meter_row()
    ara._add_tsync_filter_row(5, 1500, "m1")
    wrap = ara._tsync_meters.cellWidget(0, 5)
    assert wrap is not None
    drop = wrap.findChild(QCheckBox)
    assert drop is not None
    drop.setChecked(False)
    net = sess.get_ara_doc("tsync")["network"]
    assert net["stream_filters"] == [{"pcp": 5, "max_sdu": 1500, "meter": "m1"}]
    assert net["flow_meters"] == [
        {"name": "m1", "cir_kbps": 1000, "cbs_bytes": 2000, "drop_on_yellow": False}
    ]
    assert "preemptable_mask" not in net
    assert "max_sdu" not in net
    sess.dirty_ara_cfg.clear()
    ara.set_session(sess)
    ara.flush_to_session()
    assert not sess.dirty_ara_cfg
    assert "流过滤 1 条" in ara._tsync_psfp.text()
    wrap = ara._tsync_meters.cellWidget(0, 5)
    assert wrap is not None and wrap.findChild(QCheckBox).isChecked() is False
    drop = wrap.findChild(QCheckBox)
    assert drop is not None
    drop.setChecked(True)
    assert "drop_on_yellow" not in sess.get_ara_doc("tsync")["network"]["flow_meters"][0]
    ara._tsync_filters.selectRow(0)
    ara._del_tsync_filter_rows()
    ara._tsync_meters.selectRow(0)
    ara._del_tsync_meter_rows()
    assert "network" not in sess.get_ara_doc("tsync")


def test_tsync_missing_meter_is_marked_on_the_nav(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    ara._add_tsync_filter_row(5, 256, "missing")
    assert "不存在" in ara._tsync_psfp.text()
    assert "流过滤未对齐" in _tsync_nav_text(ara)
    assert sess.get_ara_doc("tsync")["network"]["stream_filters"] == [
        {"pcp": 5, "max_sdu": 256, "meter": "missing"}
    ]
    assert "flow_meters" not in sess.get_ara_doc("tsync")["network"]


def _tsync_nav_text(ara: AraCfgEditor) -> str:
    for index in range(ara._nav.count()):
        item = ara._nav.item(index)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == "tsync":
            return item.text()
    raise AssertionError("tsync nav item missing")


def test_afc_log_file_max_edit_dirties(qapp: QApplication) -> None:
    sess = _open("afc")
    ara = AraCfgEditor()
    ara.set_session(sess)
    assert "file_max_bytes" not in sess.get_ara_doc("log")
    ara._log_file_max.setValue(4096)
    assert "log" in (sess.dirty_ara_cfg or set())
    assert sess.get_ara_doc("log")["file_max_bytes"] == 4096
