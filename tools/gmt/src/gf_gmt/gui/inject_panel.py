"""GMT inject panel — playhead sync + event result table (order-view style)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.gui.session_model import SessionModel
from gf_gmt.i18n import t


class InjectPanel(QWidget):
    """Playhead sync + inject result table. Connect is on the top bar."""

    seek_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        tip = QLabel(
            t("Inject via top bar tcp:8767. Follow-playhead drives EgoMotion frames.")
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#555;")

        tools = QHBoxLayout()
        self.follow_playhead = QCheckBox(t("Follow playhead"))
        self.follow_playhead.setChecked(True)
        self.follow_playhead.setToolTip(
            t("开：时间轴 seek/播放/单步 → inject 发对应帧；关：只保持 TCP 连接")
        )
        tools.addWidget(self.follow_playhead)
        self.loop_at_end = QCheckBox(t("Loop at end"))
        self.loop_at_end.setChecked(False)
        self.loop_at_end.setToolTip(
            t("板端 eof 时弹窗：继续则 seek 0 并清空结果表；停止则保持在结尾")
        )
        tools.addWidget(self.loop_at_end)
        tools.addStretch(1)

        self.state = QLabel(t("Inject: disconnected"))
        self.state.setStyleSheet("color:#555; font-weight:600;")
        self.detail = QLabel("—")
        self.detail.setWordWrap(True)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["#", t("Wall"), "t_ns", "topic", t("Result"), t("Note")]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.cellClicked.connect(self._on_cell_clicked)

        lay = QVBoxLayout(self)
        lay.addWidget(tip)
        lay.addLayout(tools)
        lay.addWidget(self.state)
        lay.addWidget(self.detail)
        lay.addWidget(self._table, stretch=1)

        self._connected = False
        self._model: SessionModel | None = None
        # index → {injected, topic, reason}
        self._results: dict[int, dict[str, Any]] = {}

    def set_connected(self, on: bool, *, detail: str = "") -> None:
        self._connected = on
        if on:
            self.state.setText(t("Inject: connected (playhead)"))
            self.state.setStyleSheet("color:#2e7d32; font-weight:700;")
        else:
            self.state.setText(t("Inject: disconnected"))
            self.state.setStyleSheet("color:#555; font-weight:600;")
            self._results.clear()
            self._refill_table()
        if detail:
            self.detail.setText(detail)

    def set_detail(self, text: str) -> None:
        self.detail.setText(text)

    def wants_playhead_sync(self) -> bool:
        return self.follow_playhead.isChecked() and self._connected

    def wants_loop_confirm(self) -> bool:
        return self.loop_at_end.isChecked()

    def clear_results(self) -> None:
        self._results.clear()
        self._refill_table()

    def set_model(self, model: SessionModel | None) -> None:
        self._model = model
        self._refill_table()

    def record_result(
        self,
        index: int,
        *,
        injected: bool,
        topic: str = "",
        reason: str = "",
        t_ns: int | None = None,
    ) -> None:
        self._results[int(index)] = {
            "injected": bool(injected),
            "topic": topic,
            "reason": reason,
            "t_ns": t_ns,
        }
        self._update_row(int(index))

    def highlight_upto(self, index: int) -> None:
        if index < 0 or index >= self._table.rowCount():
            self._table.clearSelection()
            return
        self._table.blockSignals(True)
        self._table.selectRow(index)
        self._table.blockSignals(False)
        item = self._table.item(index, 0)
        if item is not None:
            self._table.scrollToItem(item)

    def _refill_table(self) -> None:
        self._table.setRowCount(0)
        if self._model is None or self._model.empty:
            return
        for ev in self._model.events:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._fill_row(r, ev.index)

    def _update_row(self, index: int) -> None:
        if self._model is None or index < 0 or index >= self._table.rowCount():
            if self._model is not None and not self._model.empty:
                self._refill_table()
            return
        self._fill_row(index, index)

    def _fill_row(self, row: int, index: int) -> None:
        if self._model is None or index < 0 or index >= len(self._model.events):
            return
        ev = self._model.events[index]
        res = self._results.get(index)
        if res is None:
            result_txt, reason, bg = "—", "", None
        elif res.get("injected"):
            result_txt, reason = t("Published"), str(res.get("reason") or "")
            bg = QColor("#c8e6c9")
        else:
            result_txt = t("Skipped")
            reason = str(res.get("reason") or t("非可灌 / injected=false"))
            bg = QColor("#ffcdd2")
        wall = self._model.wall_str(ev.t_ns, compact=True)
        vals = [
            str(ev.index),
            wall,
            str(ev.t_ns),
            (res or {}).get("topic") or ev.topic or ev.service_short,
            result_txt,
            reason,
        ]
        for c, text in enumerate(vals):
            item = QTableWidgetItem(str(text))
            if c in (0, 2):
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            if bg is not None:
                item.setBackground(bg)
            self._table.setItem(row, c, item)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        if row >= 0:
            self.seek_requested.emit(row)
