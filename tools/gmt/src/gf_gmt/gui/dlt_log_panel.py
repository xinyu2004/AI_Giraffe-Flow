"""GMT Logging — live DLT TCP client (standard protocol, not log files)."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.dlt_client import DEFAULT_DLT_PORT, DltMessage, DltTcpReader
from gf_gmt.i18n import t


class DltLogPanel(QWidget):
    """Connect to dlt-daemon (default :3490); show parsed verbose log lines."""

    _msg_signal = Signal(object)
    _status_signal = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reader: DltTcpReader | None = None
        self._host_fn = lambda: "127.0.0.1"
        self._pending: list[DltMessage] = []

        self._msg_signal.connect(self._on_msg)
        self._status_signal.connect(self._on_status)

        lay = QVBoxLayout(self)
        hint = QLabel(
            t(
                "Logging（DLT）：连接板端/SIL 的 dlt-daemon（标准协议 TCP）。"
                "不读 log 文件。也可用 dlt-viewer / dlt-receive。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        row = QHBoxLayout()
        self._host = QLineEdit("127.0.0.1")
        self._host.setMaximumWidth(140)
        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(DEFAULT_DLT_PORT)
        self._btn = QPushButton(t("连接"))
        self._btn.setCheckable(True)
        self._btn.toggled.connect(self._on_toggle)
        self._filter = QLineEdit()
        self._filter.setPlaceholderText(t("过滤 APP/CTX/文本（如 RUNT,Offer）"))
        self._auto = QCheckBox(t("自动滚屏"))
        self._auto.setChecked(True)
        self._clear = QPushButton(t("清空"))
        self._clear.clicked.connect(lambda: self._view.clear())
        row.addWidget(QLabel(t("Host")))
        row.addWidget(self._host)
        row.addWidget(QLabel(t("Port")))
        row.addWidget(self._port)
        row.addWidget(self._btn)
        row.addWidget(self._filter, stretch=1)
        row.addWidget(self._auto)
        row.addWidget(self._clear)
        lay.addLayout(row)

        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self._view.setFont(font)
        lay.addWidget(self._view, stretch=1)

        self._status = QLabel(t("未连接"))
        self._status.setStyleSheet("color:#666;")
        lay.addWidget(self._status)

        self._flush = QTimer(self)
        self._flush.setInterval(100)
        self._flush.timeout.connect(self._flush_pending)
        self._flush.start()

    def set_host_provider(self, fn) -> None:
        """Optional: sync Host from GMT top bar when connecting."""
        self._host_fn = fn

    def sync_host_from_bar(self) -> None:
        try:
            h = (self._host_fn() or "").strip()
        except Exception:
            h = ""
        if h:
            self._host.setText(h)

    def _on_toggle(self, on: bool) -> None:
        if on:
            self.sync_host_from_bar()
            host = self._host.text().strip() or "127.0.0.1"
            port = int(self._port.value())
            self._btn.setText(t("断开"))
            self._reader = DltTcpReader(
                on_message=lambda m: self._msg_signal.emit(m),
                on_status=lambda s: self._status_signal.emit(s),
            )
            self._reader.start(host, port)
        else:
            self._btn.setText(t("连接"))
            if self._reader is not None:
                self._reader.stop()
                self._reader = None
            self._status.setText(t("未连接"))

    def _on_status(self, s: str) -> None:
        self._status.setText(s)
        if s.startswith("connect failed") or s == "disconnected":
            self._btn.blockSignals(True)
            self._btn.setChecked(False)
            self._btn.setText(t("连接"))
            self._btn.blockSignals(False)

    def _on_msg(self, msg: object) -> None:
        if isinstance(msg, DltMessage):
            self._pending.append(msg)
            # Bound pending queue
            if len(self._pending) > 2000:
                del self._pending[:1000]

    def _accept(self, msg: DltMessage) -> bool:
        q = self._filter.text().strip()
        if not q:
            return True
        blob = f"{msg.app_id} {msg.ctx_id} {msg.level} {msg.text}"
        return all(part.lower() in blob.lower() for part in q.replace(",", " ").split())

    def _flush_pending(self) -> None:
        if not self._pending:
            return
        batch = self._pending
        self._pending = []
        lines = [m.display() for m in batch if self._accept(m)]
        if not lines:
            return
        at_bottom = (
            self._view.verticalScrollBar().value()
            >= self._view.verticalScrollBar().maximum() - 4
        )
        self._view.appendPlainText("\n".join(lines))
        if self._auto.isChecked() or at_bottom:
            self._view.moveCursor(QTextCursor.MoveOperation.End)

    def shutdown(self) -> None:
        if self._reader is not None:
            self._reader.stop()
            self._reader = None
