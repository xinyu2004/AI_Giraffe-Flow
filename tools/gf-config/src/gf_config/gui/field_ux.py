"""Shared gf-config field UX: hand cursor, tooltips, bool tint, multi-select."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPaintEvent, QPolygon
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gf_config.i18n import t

# (background, text) — muted but clearly distinct; focus must not wash to white.
ColorPair = tuple[str, str]

COLORS_BOOL: dict[str, ColorPair] = {
    "true": ("#c8e6c9", "#1b5e20"),
    "false": ("#e0e0e0", "#424242"),
}
COLORS_FG_INITIAL: dict[str, ColorPair] = {
    "Off": ("#e0e0e0", "#424242"),
    "Running": ("#c8e6c9", "#1b5e20"),
    "Updating": ("#ffe082", "#6d4c00"),
}
COLORS_ON_FAILURE: dict[str, ColorPair] = {
    "log": ("#e0e0e0", "#424242"),
    "notify_sm": ("#bbdefb", "#0d47a1"),
    "restart": ("#ffccbc", "#bf360c"),
}
COLORS_DID_ACCESS: dict[str, ColorPair] = {
    "read": ("#c8e6c9", "#1b5e20"),
    "write": ("#ffe082", "#6d4c00"),
    "read_write": ("#bbdefb", "#0d47a1"),
}
COLORS_LOG_LEVEL: dict[str, ColorPair] = {
    "FATAL": ("#ffcdd2", "#b71c1c"),
    "ERROR": ("#ffccbc", "#bf360c"),
    "WARN": ("#ffe082", "#6d4c00"),
    "INFO": ("#c8e6c9", "#1b5e20"),
    "DEBUG": ("#bbdefb", "#0d47a1"),
    "VERBOSE": ("#e0e0e0", "#424242"),
}
COLORS_FORWARD: dict[str, ColorPair] = {
    "local_store": ("#e0e0e0", "#424242"),
    "cp_dem": ("#bbdefb", "#0d47a1"),
    "both": ("#c8e6c9", "#1b5e20"),
}
COLORS_ON_OFF: dict[str, ColorPair] = {
    "on": ("#c8e6c9", "#1b5e20"),
    "off": ("#e0e0e0", "#424242"),
}
COLORS_RECORD: dict[str, ColorPair] = {
    "minimal": ("#c8e6c9", "#1b5e20"),
    "sampled": ("#bbdefb", "#0d47a1"),
    "full": ("#ffe082", "#6d4c00"),
    "off": ("#e0e0e0", "#424242"),
}
COLORS_LIVE_MODE: dict[str, ColorPair] = {
    "wiring_all": ("#c8e6c9", "#1b5e20"),
    "explicit": ("#bbdefb", "#0d47a1"),
}
COLORS_PROFILE: dict[str, ColorPair] = {
    "vehicle-debug": ("#bbdefb", "#0d47a1"),
    "production-release": ("#ffccbc", "#bf360c"),
}
COLORS_TOPOLOGY: dict[str, ColorPair] = {
    "ap_only": ("#c8e6c9", "#1b5e20"),
    "ap_mcu_cp": ("#ffe082", "#6d4c00"),
}
_DEFAULT_PAIR: ColorPair = ("#f5f5f5", "#333333")

# Same blue for row-number header and selected-row combos.
_SEL_BG = "#90caf9"
_SEL_FG = "#0d47a1"
_SEL_HEADER = QColor(_SEL_BG)
_HDR_IDLE = QColor("#eeeeee")


class TintedComboBox(QComboBox):
    """QComboBox with tint stylesheet + painted chevron (stylesheet kills native arrow)."""

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        # Only paint when tinted — otherwise leave the native arrow alone.
        if not self.styleSheet():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#9a9a9a" if not self.isEnabled() else "#444444"))
        painter.setPen(Qt.PenStyle.NoPen)
        cx = self.width() - 11
        cy = self.height() // 2
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(cx - 4, cy - 2),
                    QPoint(cx + 4, cy - 2),
                    QPoint(cx, cy + 3),
                ]
            )
        )
        painter.end()


def _hand_cursor() -> QCursor:
    # Must not construct QCursor at import time (needs QGuiApplication).
    return QCursor(Qt.CursorShape.PointingHandCursor)


def tipify(widget: QWidget, tip: str) -> None:
    """Pointing-hand cursor + localized tooltip (Chinese source key → t())."""
    if tip:
        widget.setToolTip(t(tip))
    widget.setCursor(_hand_cursor())


def tipify_item(item: QTableWidgetItem, tip: str) -> None:
    if tip:
        item.setToolTip(t(tip))


def set_cell(
    table: QTableWidget, row: int, col: int, text: str, tip: str = ""
) -> None:
    item = QTableWidgetItem(text)
    tipify_item(item, tip)
    table.setItem(row, col, item)


def set_header_tips(table: QTableWidget, tips: list[str]) -> None:
    for i, tip in enumerate(tips):
        if i >= table.columnCount():
            break
        item = table.horizontalHeaderItem(i)
        if item is None:
            continue
        if tip:
            item.setToolTip(t(tip))


def _combo_stylesheet(bg: str, fg: str) -> str:
    # Tint only — hide native arrow (broken under stylesheets); TintedComboBox paints ▾.
    return f"""
QComboBox {{
  background-color: {bg};
  color: {fg};
  padding: 2px 18px 2px 8px;
  border: 1px solid #c8c8c8;
  border-radius: 3px;
  min-height: 1.4em;
}}
QComboBox:hover {{
  background-color: {bg};
  color: {fg};
  border: 1px solid #a8a8a8;
}}
QComboBox:focus, QComboBox:on {{
  background-color: {bg};
  color: {fg};
  border: 1px solid #888;
}}
QComboBox:!editable, QComboBox:!editable:on {{
  background-color: {bg};
  color: {fg};
}}
QComboBox:disabled, QComboBox:!editable:disabled {{
  background-color: #f0f0f0;
  color: #9e9e9e;
  border: 1px solid #d5d5d5;
}}
QComboBox::drop-down {{
  subcontrol-origin: padding;
  subcontrol-position: center right;
  width: 16px;
  border: none;
  background: transparent;
}}
QComboBox::down-arrow {{
  image: none;
  width: 0px;
  height: 0px;
}}
QComboBox QAbstractItemView {{
  background-color: #fafafa;
  color: #222;
  selection-background-color: {bg};
  selection-color: {fg};
  outline: 0;
}}
"""


def set_item_tips(
    cb: QComboBox,
    item_tips: dict[str, str],
    *,
    data_role: bool = False,
) -> None:
    """Per-option tooltips shown while browsing the dropdown list."""
    for i in range(cb.count()):
        if data_role:
            data = cb.itemData(i)
            key = str(data).strip() if data is not None else cb.itemText(i).strip()
        else:
            key = cb.itemText(i).strip()
        tip = item_tips.get(key)
        if tip:
            cb.setItemData(i, t(tip), Qt.ItemDataRole.ToolTipRole)


def style_enum_combo(
    cb: QComboBox,
    colors: dict[str, ColorPair],
    *,
    data_role: bool = False,
    item_tips: dict[str, str] | None = None,
) -> None:
    """Tint combo by current text (or currentData when data_role=True).

    Prefer constructing a TintedComboBox so the chevron is painted after stylesheet.
    """

    def _key() -> str:
        if data_role:
            data = cb.currentData()
            if data is not None:
                return str(data).strip()
        return cb.currentText().strip()

    def _apply(*_args: object) -> None:
        bg, fg = colors.get(_key(), _DEFAULT_PAIR)
        cb.setStyleSheet(_combo_stylesheet(bg, fg))

    # 供 load 时 blockSignals 后手动刷新（否则停在首项颜色，如 FATAL 红）
    setattr(cb, "_gf_tint_apply", _apply)
    _apply()
    if item_tips:
        set_item_tips(cb, item_tips, data_role=data_role)
    cb.currentTextChanged.connect(_apply)
    if data_role:
        cb.currentIndexChanged.connect(_apply)


def refresh_enum_combo_style(cb: QComboBox) -> None:
    """Re-apply tint after setCurrent* with signals blocked."""
    apply = getattr(cb, "_gf_tint_apply", None)
    if callable(apply):
        apply()


def style_bool_combo(
    cb: QComboBox, item_tips: dict[str, str] | None = None
) -> None:
    style_enum_combo(cb, COLORS_BOOL, item_tips=item_tips)


def make_combo(
    options: list[str],
    value: str,
    on_change: Callable[..., None],
    *,
    tip: str = "",
    bool_style: bool = False,
    enum_colors: dict[str, ColorPair] | None = None,
    item_tips: dict[str, str] | None = None,
) -> QComboBox:
    colors = enum_colors or (COLORS_BOOL if bool_style else None)
    # Colored combos need painted chevron; plain ones keep the native arrow.
    cb: QComboBox = TintedComboBox() if colors else QComboBox()
    opts = list(options)
    # Explicit empty value: keep a blank first item so the user can fill later.
    if value == "" and "" not in opts:
        opts = [""] + opts
    elif value and value not in opts:
        opts = [value] + opts
    cb.addItems(opts)
    if value in opts:
        cb.setCurrentIndex(opts.index(value))
    elif opts:
        cb.setCurrentIndex(0)
    tipify(cb, tip)
    if colors:
        style_enum_combo(cb, colors, item_tips=item_tips)
    elif item_tips:
        set_item_tips(cb, item_tips)
    cb.currentTextChanged.connect(lambda *_a: on_change())
    return cb


def _apply_combo_row_selected(cb: QComboBox, on: bool) -> None:
    """Blue-wash module combos only; skip enum-tinted ones (log level)."""
    if getattr(cb, "_gf_tint_apply", None) is not None:
        return
    cb.setStyleSheet(_combo_stylesheet(_SEL_BG, _SEL_FG) if on else "")


def _refresh_row_select_chrome(table: QTableWidget) -> None:
    selected = {idx.row() for idx in table.selectedIndexes()}
    cur = table.currentRow()
    if cur >= 0:
        selected.add(cur)
    for r in range(table.rowCount()):
        on = r in selected
        item = table.verticalHeaderItem(r)
        if item is None:
            item = QTableWidgetItem(str(r + 1))
            table.setVerticalHeaderItem(r, item)
        else:
            item.setText(str(r + 1))
        item.setBackground(_SEL_HEADER if on else _HDR_IDLE)
        item.setForeground(QColor(_SEL_FG) if on else QColor("#333333"))
        font = item.font()
        font.setBold(on)
        item.setFont(font)
        for c in range(table.columnCount()):
            w = table.cellWidget(r, c)
            if isinstance(w, QComboBox):
                _apply_combo_row_selected(w, on)
    table.verticalHeader().viewport().update()


def enable_table_row_selection(table: QTableWidget) -> None:
    """Row-number select; module washes blue; level keeps enum tint."""
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setStyleSheet(
        """
QTableWidget {
  selection-background-color: transparent;
  selection-color: palette(text);
}
QTableWidget::item:selected {
  background: transparent;
  color: palette(text);
}
"""
    )
    vh = table.verticalHeader()
    vh.setVisible(True)
    vh.setSectionsClickable(True)
    vh.setHighlightSections(True)
    vh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    vh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    vh.setMinimumWidth(28)
    vh.setStyleSheet(
        f"""
QHeaderView::section {{
  background-color: {_HDR_IDLE.name()};
  color: #333333;
  padding: 2px 4px;
  border: none;
  border-right: 1px solid #bdbdbd;
}}
QHeaderView::section:checked,
QHeaderView::section:selected {{
  background-color: {_SEL_BG};
  color: {_SEL_FG};
  font-weight: 600;
}}
"""
    )
    table.setProperty("_gf_row_select", True)
    table.itemSelectionChanged.connect(lambda: _refresh_row_select_chrome(table))
    vh.sectionClicked.connect(lambda idx: table.selectRow(idx))


def ensure_selectable_row(table: QTableWidget, row: int) -> None:
    """Placeholder items so SelectRows / selectedIndexes work under cell widgets."""
    for c in range(table.columnCount()):
        if table.item(row, c) is not None:
            continue
        it = QTableWidgetItem("")
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        table.setItem(row, c, it)


def set_combo(
    table: QTableWidget,
    row: int,
    col: int,
    options: list[str],
    value: str,
    on_change: Callable[..., None],
    *,
    tip: str = "",
    bool_style: bool = False,
    enum_colors: dict[str, ColorPair] | None = None,
    item_tips: dict[str, str] | None = None,
) -> QComboBox:
    cb_box: list[QComboBox] = []

    def _wrapped(*_a: object) -> None:
        on_change()
        if (
            table.property("_gf_row_select")
            and table.currentRow() == row
            and cb_box
            and getattr(cb_box[0], "_gf_tint_apply", None) is None
        ):
            _apply_combo_row_selected(cb_box[0], True)

    cb = make_combo(
        options,
        value,
        _wrapped,
        tip=tip,
        bool_style=bool_style,
        enum_colors=enum_colors,
        item_tips=item_tips,
    )
    cb_box.append(cb)
    ensure_selectable_row(table, row)
    table.setCellWidget(row, col, cb)
    if table.property("_gf_row_select"):
        def _sync_row(*_a: object, _t: QTableWidget = table, _r: int = row) -> None:
            if _t.currentRow() != _r:
                _t.selectRow(_r)

        cb.activated.connect(_sync_row)
        cb.installEventFilter(_ComboSelectFilter(table, row, cb))
    return cb


class _ComboSelectFilter(QObject):
    """FocusIn on a combo → select its table row."""

    def __init__(self, table: QTableWidget, row: int, cb: QComboBox) -> None:
        super().__init__(cb)
        self._table = table
        self._row = row

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.FocusIn:
            if self._table.currentRow() != self._row:
                self._table.selectRow(self._row)
        return False


def combo_text(table: QTableWidget, row: int, col: int) -> str:
    w = table.cellWidget(row, col)
    if isinstance(w, QComboBox):
        return w.currentText().strip()
    item = table.item(row, col)
    return item.text().strip() if item else ""


def cell_text(table: QTableWidget, row: int, col: int) -> str:
    w = table.cellWidget(row, col)
    if isinstance(w, MultiCheckButton):
        return ", ".join(w.selected())
    if isinstance(w, QComboBox):
        return w.currentText().strip()
    item = table.item(row, col)
    return item.text().strip() if item else ""


class MultiCheckButton(QWidget):
    """Compact multi-select: button shows summary; dialog with checkboxes."""

    changed = Signal()

    def __init__(
        self,
        selected: list[str],
        candidates_fn: Callable[[], list[str]],
        *,
        tip: str = "",
        empty_label: str = "(none)",
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._selected = [str(x) for x in selected if str(x).strip()]
        self._candidates_fn = candidates_fn
        self._empty_label = empty_label
        self._title = title or tip
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._btn = QPushButton(self._label())
        self._btn.setStyleSheet(
            """
QPushButton {
  text-align: left;
  padding: 2px 8px;
  border: 1px solid #c8c8c8;
  border-radius: 3px;
  background: #fafafa;
}
QPushButton:hover { border: 1px solid #a8a8a8; }
QPushButton:disabled {
  color: #9e9e9e;
  background: #f0f0f0;
  border: 1px solid #d5d5d5;
}
"""
        )
        tipify(self._btn, tip)
        self._btn.clicked.connect(self._edit)
        lay.addWidget(self._btn)

    def selected(self) -> list[str]:
        return list(self._selected)

    def set_selected(self, values: list[str]) -> None:
        self._selected = [str(x) for x in values if str(x).strip()]
        self._btn.setText(self._label())

    def _label(self) -> str:
        if not self._selected:
            body = self._empty_label
        elif len(self._selected) <= 2:
            body = ", ".join(self._selected)
        else:
            body = f"{self._selected[0]} +{len(self._selected) - 1}"
        return f"{body}  ▾"

    def _edit(self) -> None:
        cands = list(self._candidates_fn())
        for s in self._selected:
            if s not in cands:
                cands.append(s)
        dlg = QDialog(self)
        dlg.setWindowTitle(t(self._title) if self._title else t("选择"))
        dlg.setMinimumWidth(360)
        v = QVBoxLayout(dlg)
        hint = QLabel(t("勾选后确定；可多选。"))
        hint.setStyleSheet("color:#666;")
        v.addWidget(hint)
        lst = QListWidget()
        for name in cands:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if name in self._selected
                else Qt.CheckState.Unchecked
            )
            lst.addItem(item)
        v.addWidget(lst, stretch=1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        v.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        out: list[str] = []
        for i in range(lst.count()):
            item = lst.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                out.append(item.text())
        self._selected = out
        self._btn.setText(self._label())
        self.changed.emit()


def set_multi_check(
    table: QTableWidget,
    row: int,
    col: int,
    selected: list[str],
    candidates_fn: Callable[[], list[str]],
    on_change: Callable[..., None],
    *,
    tip: str = "",
    empty_label: str = "(none)",
    title: str = "",
) -> MultiCheckButton:
    w = MultiCheckButton(
        selected,
        candidates_fn,
        tip=tip,
        empty_label=empty_label,
        title=title or tip,
    )
    w.changed.connect(lambda: on_change())
    table.setCellWidget(row, col, w)
    return w


def multi_selected(table: QTableWidget, row: int, col: int) -> list[str]:
    w = table.cellWidget(row, col)
    if isinstance(w, MultiCheckButton):
        return w.selected()
    raw = cell_text(table, row, col).replace(",", " ")
    return [x for x in raw.split() if x]


def tipify_form_controls(*widgets: QWidget) -> None:
    """Apply hand cursor to common interactive controls (tooltip already set)."""
    hand = _hand_cursor()
    for w in widgets:
        if isinstance(w, (QAbstractButton, QComboBox, QLineEdit, QCheckBox)):
            w.setCursor(hand)
