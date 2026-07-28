"""Order / race view: event table with Δt (default GMT debug view)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.gui.session_model import SessionModel
from gf_gmt.i18n import t


class OrderRaceView(QWidget):
    seek_requested = Signal(int)  # event index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hint = QLabel(
            t("Order: events by time (Δt). Click to seek; yellow = same t_ns.")
        )
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color:#555;")
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["#", t("Wall"), "t_ns", "Δt_ns", "topic", "from → to", "seq"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.cellClicked.connect(self._on_cell_clicked)
        lay = QVBoxLayout(self)
        lay.addWidget(self._hint)
        lay.addWidget(self._table)

    def set_model(self, model: SessionModel | None) -> None:
        self._table.setRowCount(0)
        if model is None or model.empty:
            return
        # mark concurrent timestamps (race hint)
        counts: dict[int, int] = {}
        for ev in model.events:
            counts[ev.t_ns] = counts.get(ev.t_ns, 0) + 1
        for ev in model.events:
            r = self._table.rowCount()
            self._table.insertRow(r)
            route = ""
            if ev.from_proc and ev.to_proc:
                route = f"{ev.from_proc} → {ev.to_proc}"
            seq = ev.data.get("seq", "")
            vals = [
                str(ev.index),
                model.wall_str(ev.t_ns, compact=True),
                str(ev.t_ns),
                str(ev.dt_ns),
                ev.topic or ev.service_short,
                route,
                str(seq),
            ]
            concurrent = counts.get(ev.t_ns, 0) > 1
            for c, text in enumerate(vals):
                item = QTableWidgetItem(text)
                if c in (0, 2, 3):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if concurrent:
                    item.setBackground(Qt.GlobalColor.yellow)
                self._table.setItem(r, c, item)

    def highlight_upto(self, index: int) -> None:
        """Select row at playback cursor."""
        if index < 0 or index >= self._table.rowCount():
            self._table.clearSelection()
            return
        self._table.blockSignals(True)
        self._table.selectRow(index)
        self._table.blockSignals(False)
        item = self._table.item(index, 0)
        if item is not None:
            self._table.scrollToItem(item)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        if row >= 0:
            self.seek_requested.emit(row)
