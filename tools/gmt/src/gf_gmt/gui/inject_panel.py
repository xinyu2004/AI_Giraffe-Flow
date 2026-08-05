"""GMT inject panel — results only while TCP inject is connected + driving."""

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
    """Playhead sync + inject *result* table. Not a live session mirror."""

    seek_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        tip = QLabel(
            t(
                "未连接时此表为空。顶栏「回灌 tcp」连接后，"
                "勾选 Follow playhead 并回放/单步，结果才会出现。"
            )
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#555;")

        tools = QHBoxLayout()
        self.follow_playhead = QCheckBox(t("Follow playhead"))
        self.follow_playhead.setChecked(False)
        self.follow_playhead.setToolTip(
            t("开：时间轴 seek/播放/单步 → inject 发对应帧；关：只保持 TCP 连接")
        )
        tools.addWidget(self.follow_playhead)
        self.loop_at_end = QCheckBox(t("Loop at end"))
        self.loop_at_end.setChecked(True)
        self.loop_at_end.setToolTip(
            t(
                "播放到结尾自动从 #0 再灌（无限循环）："
                "重置板端 A/B、清空结果表。取消勾选则停在结尾。"
            )
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
            QHeaderView.ResizeMode.Interactive
        )
        self._table.horizontalHeader().setStretchLastSection(True)
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
        # index → {injected, topic, reason, t_ns}
        self._results: dict[int, dict[str, Any]] = {}

    def set_connected(self, on: bool, *, detail: str = "") -> None:
        """TCP link state only (not per-frame inject success)."""
        self._connected = on
        if on:
            self.state.setText(t("Inject: connected"))
            self.state.setStyleSheet("color:#2e7d32; font-weight:700;")
            self.follow_playhead.setChecked(True)
        else:
            self.state.setText(t("Inject: disconnected"))
            self.state.setStyleSheet("color:#555; font-weight:600;")
            self.follow_playhead.setChecked(False)
            self._results.clear()
            self._table.setRowCount(0)
            self.detail.setText(
                t("未连接 — 连接回灌并回放后才显示结果")
            )
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
        self._table.setRowCount(0)

    def set_model(self, model: SessionModel | None) -> None:
        """Keep model for wall-time lookup; do not mirror session into the table."""
        self._model = model
        if not self._connected:
            self._table.setRowCount(0)

    def append_events(self, model: SessionModel, *, from_index: int = 0) -> None:
        """Live appends must NOT fill this table — only inject results do."""
        self._model = model
        _ = from_index

    def record_result(
        self,
        index: int,
        *,
        injected: bool,
        topic: str = "",
        reason: str = "",
        t_ns: int | None = None,
    ) -> None:
        if not self._connected:
            return
        self._results[int(index)] = {
            "injected": bool(injected),
            "topic": topic,
            "reason": reason,
            "t_ns": t_ns,
        }
        self._upsert_result_row(int(index))

    def highlight_upto(self, index: int) -> None:
        if not self._connected or not self._results:
            return
        # Select the result row whose event index matches playhead, if present.
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is not None and item.text() == str(index):
                self._table.blockSignals(True)
                self._table.selectRow(row)
                self._table.blockSignals(False)
                self._table.scrollToItem(item)
                return

    def _upsert_result_row(self, index: int) -> None:
        if self._model is None or index < 0 or index >= len(self._model.events):
            return
        # Find existing row for this index
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is not None and item.text() == str(index):
                self._fill_row(row, index)
                return
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._fill_row(row, index)
        self._table.scrollToBottom()

    def _fill_row(self, row: int, index: int) -> None:
        if self._model is None or index < 0 or index >= len(self._model.events):
            return
        ev = self._model.events[index]
        res = self._results.get(index)
        if res is None:
            return
        if res.get("injected"):
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
            res.get("topic") or ev.topic or ev.service_short,
            result_txt,
            reason,
        ]
        for c, text in enumerate(vals):
            item = QTableWidgetItem(str(text))
            if c in (0, 2):
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            item.setBackground(bg)
            self._table.setItem(row, c, item)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        if not self._connected:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        try:
            self.seek_requested.emit(int(item.text()))
        except ValueError:
            pass
