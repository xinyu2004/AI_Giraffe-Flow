"""Lineage report viewer with red/green check highlighting."""

from __future__ import annotations

from typing import Any

import yaml
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LineageView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._summary = QLabel("Compose 后显示 lineage 检查结果")
        self._summary.setWordWrap(True)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self._summary.setFont(font)

        self._checks = QTextEdit()
        self._checks.setReadOnly(True)
        self._raw = QPlainTextEdit()
        self._raw.setReadOnly(True)
        self._raw.setPlaceholderText("原始 signal_lineage_report.yaml …")

        split = QSplitter()
        split.setOrientation(Qt.Orientation.Vertical)
        top = QWidget()
        top_l = QVBoxLayout(top)
        top_l.setContentsMargins(0, 0, 0, 0)
        top_l.addWidget(self._summary)
        top_l.addWidget(self._checks)
        split.addWidget(top)
        split.addWidget(self._raw)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(split)

    def set_placeholder(self, text: str) -> None:
        self._summary.setText(text)
        self._summary.setStyleSheet("color:#666;")
        self._checks.clear()
        self._raw.clear()

    def set_report_text(self, text: str) -> None:
        self._raw.setPlainText(text or "")
        if not text.strip():
            self.set_placeholder("（无报告内容）")
            return
        try:
            data = yaml.safe_load(text) or {}
        except Exception:  # noqa: BLE001
            self._summary.setText("报告不是合法 YAML，见下方原文")
            self._summary.setStyleSheet("color:#c0392b;")
            self._checks.setPlainText(text)
            return
        if not isinstance(data, dict):
            self._summary.setText("报告格式异常")
            self._summary.setStyleSheet("color:#c0392b;")
            self._checks.setPlainText(text)
            return
        self._render(data)

    def _render(self, data: dict[str, Any]) -> None:
        ok = bool(data.get("ok"))
        errors = [str(e) for e in (data.get("errors") or [])]
        warnings = [str(w) for w in (data.get("warnings") or [])]
        checks = [c for c in (data.get("checks") or []) if isinstance(c, dict)]

        if ok:
            self._summary.setText(f"Lineage PASS · {len(checks)} 项检查通过")
            self._summary.setStyleSheet("color:#1e8449;")
        else:
            self._summary.setText(
                f"Lineage FAIL · {len(errors)} 个错误 · {len(warnings)} 个警告"
            )
            self._summary.setStyleSheet("color:#c0392b;")

        self._checks.clear()
        cursor = self._checks.textCursor()

        def write(text: str, *, color: str | None = None, bold: bool = False) -> None:
            fmt = QTextCharFormat()
            if color:
                fmt.setForeground(QColor(color))
            if bold:
                font = fmt.font()
                font.setBold(True)
                fmt.setFont(font)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)

        if errors:
            write("错误\n", color="#c0392b", bold=True)
            for e in errors:
                write(f"  ✗ {e}\n", color="#c0392b")
            write("\n")
        if warnings:
            write("警告\n", color="#d68910", bold=True)
            for w in warnings:
                write(f"  ! {w}\n", color="#d68910")
            write("\n")

        write("检查项\n", bold=True)
        for c in checks:
            cid = str(c.get("id") or "?")
            status = str(c.get("status") or "")
            if status == "pass":
                write(f"  ✓ {cid}\n", color="#1e8449")
            elif status == "fail":
                write(f"  ✗ {cid}\n", color="#c0392b", bold=True)
                for key in ("missing", "detail", "conflicts"):
                    if c.get(key):
                        write(f"      {key}: {c.get(key)}\n", color="#922b21")
            else:
                write(f"  · {cid} ({status})\n", color="#566573")

        self._checks.setTextCursor(QTextCursor(self._checks.document()))
