"""Platform tab shell widgets + small table/int helpers."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gf_config.gui.field_ux import ColorPair, combo_text, set_cell, set_combo


class CurrentPageStack(QStackedWidget):
    """Use only the visible page for size hints so a tall page can't lock window height."""

    def minimumSizeHint(self):  # noqa: N802 — Qt API
        w = self.currentWidget()
        return w.minimumSizeHint() if w is not None else super().minimumSizeHint()

    def sizeHint(self):  # noqa: N802 — Qt API
        w = self.currentWidget()
        return w.sizeHint() if w is not None else super().sizeHint()


class PlatformScrollPage(QScrollArea):
    """Scroll page that does not advertise tall content as the shell's preferred height."""

    def __init__(self, inner: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(inner)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setMinimumHeight(0)

    def sizeHint(self):  # noqa: N802 — Qt API
        return QSize(480, 360)

    def minimumSizeHint(self):  # noqa: N802 — Qt API
        return QSize(240, 160)


def make_collapsible(
    title: str, *, expanded: bool = True, parent: QWidget | None = None
) -> tuple[QWidget, QWidget]:
    """Shell + body; put fields into body. Header arrow toggles body visibility."""
    shell = QFrame(parent)
    shell.setObjectName(f"gf_collapse:{title[:32]}")
    shell.setFrameShape(QFrame.Shape.StyledPanel)
    outer = QVBoxLayout(shell)
    outer.setContentsMargins(8, 4, 8, 8)
    outer.setSpacing(4)

    hdr = QToolButton(shell)
    hdr.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    hdr.setArrowType(
        Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
    )
    hdr.setText(title)
    hdr.setCheckable(True)
    hdr.setChecked(expanded)
    hdr.setAutoRaise(True)
    hdr.setCursor(Qt.CursorShape.PointingHandCursor)
    hdr.setStyleSheet(
        "QToolButton { border: none; font-weight: 600; padding: 2px 0; }"
    )

    body = QWidget(shell)
    body.setVisible(expanded)

    def _toggle(checked: bool) -> None:
        body.setVisible(checked)
        hdr.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    hdr.toggled.connect(_toggle)
    outer.addWidget(hdr)
    outer.addWidget(body)
    return shell, body


def int_or_none(text: str) -> int | None:
    raw = text.strip()
    if not raw or raw.lower() in ("null", "none", "-"):
        return None
    return int(raw, 0)


def int_or_default(text: str, default: int) -> int:
    try:
        v = int_or_none(text)
    except ValueError:
        return default
    return default if v is None else v


def cell(table: QTableWidget, row: int, col: int) -> str:
    item = table.item(row, col)
    return item.text().strip() if item else ""


def set_table_cell(
    table: QTableWidget, row: int, col: int, text: str, tip: str = ""
) -> None:
    set_cell(table, row, col, text, tip)


def combo_cell_text(table: QTableWidget, row: int, col: int) -> str:
    return combo_text(table, row, col)


def set_table_combo(
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
) -> None:
    set_combo(
        table,
        row,
        col,
        options,
        value,
        on_change,
        tip=tip,
        bool_style=bool_style,
        enum_colors=enum_colors,
        item_tips=item_tips,
    )


# Compat aliases matching former private names in ara_cfg_editor.
_CurrentPageStack = CurrentPageStack
_PlatformScrollPage = PlatformScrollPage
_make_collapsible = make_collapsible
_int_or_none = int_or_none
_int_or_default = int_or_default
_cell = cell
_set_cell = set_table_cell
_combo_text = combo_cell_text
_set_combo = set_table_combo
