"""GMT Collector sheet — file store or DoIP/UDS RID F201 (same table)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.doip_client import DoipClient
from gf_gmt.i18n import t


def default_collector_store(project_dir: Path | None = None) -> Path:
    env = (os.environ.get("GF_COLLECTOR_STORE") or "").strip()
    if env:
        return Path(env)
    cand = Path.cwd() / "build" / "iox_multiproc_logs" / "collector_shared.ndjson"
    if cand.is_file():
        return cand
    if project_dir is not None:
        alt = Path.cwd() / "build" / "iox_multiproc_logs" / "collector_shared.ndjson"
        if alt.is_file():
            return alt
    return cand


class CollectorPanel(QWidget):
    """Read-only Event Collector view — local NDJSON or remote UDS (via OTA/UDS DoIP)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_dir: Path | None = None
        self._mtime: float | None = None
        self._size: int | None = None
        self._client_fn: Callable[[], DoipClient | None] | None = None
        self._uds_log_fn: Callable[[str], None] | None = None

        lay = QVBoxLayout(self)
        hint = QLabel(
            t(
                "Event Collector：本机 NDJSON（同机 SIL）或 UDS RID F201（板端）。"
                "DoIP 在上方连接；UDS 步骤写入下方日志。DTC 请切 DEM。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        src_row = QHBoxLayout()
        self._src_file = QRadioButton(t("本机文件"))
        self._src_uds = QRadioButton(t("UDS（板端）"))
        self._src_file.setChecked(True)
        self._src_group = QButtonGroup(self)
        self._src_group.addButton(self._src_file)
        self._src_group.addButton(self._src_uds)
        self._src_file.toggled.connect(self._on_source_changed)
        src_row.addWidget(self._src_file)
        src_row.addWidget(self._src_uds)
        src_row.addStretch(1)
        lay.addLayout(src_row)

        self._file_row = QWidget()
        row = QHBoxLayout(self._file_row)
        row.setContentsMargins(0, 0, 0, 0)
        self._path = QLineEdit()
        self._path.setPlaceholderText("…/collector_shared.ndjson")
        self._path.setText(str(default_collector_store()))
        browse = QPushButton(t("浏览…"))
        browse.clicked.connect(self._browse)
        refresh = QPushButton(t("刷新"))
        refresh.clicked.connect(self.reload)
        self._auto = QCheckBox(t("自动刷新"))
        self._auto.setChecked(True)
        self._auto.toggled.connect(self._on_auto)
        row.addWidget(QLabel(t("Store")), stretch=0)
        row.addWidget(self._path, stretch=1)
        row.addWidget(browse)
        row.addWidget(refresh)
        row.addWidget(self._auto)
        lay.addWidget(self._file_row)

        self._uds_row = QWidget()
        urow = QHBoxLayout(self._uds_row)
        urow.setContentsMargins(0, 0, 0, 0)
        self._btn_uds = QPushButton(t("从 UDS 读取"))
        self._btn_uds.setToolTip(
            t("使用已连接的 DoIP：0x31 01 F201 拉取环缓事件")
        )
        self._btn_uds.clicked.connect(self._load_uds)
        urow.addWidget(self._btn_uds)
        urow.addWidget(QLabel(t("需先连接 DoIP；步骤见下方 UDS 日志")))
        urow.addStretch(1)
        self._uds_row.setVisible(False)
        lay.addWidget(self._uds_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#555;")
        lay.addWidget(self._status)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["t_ns", "source", "id", "detail", "pid"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self._table, stretch=1)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def bind_doip(
        self,
        client_fn: Callable[[], DoipClient | None],
        uds_log_fn: Callable[[str], None],
    ) -> None:
        """Wire shared DoIP client + log sink from OTA/UDS panel."""
        self._client_fn = client_fn
        self._uds_log_fn = uds_log_fn

    def set_project_dir(self, project_dir: Path | None) -> None:
        self._project_dir = project_dir
        cur = self._path.text().strip()
        default = str(default_collector_store(project_dir))
        if not cur or cur == str(default_collector_store(None)):
            self._path.setText(default)
        if self._src_file.isChecked():
            self.reload()

    def _on_source_changed(self, *_a: object) -> None:
        file_mode = self._src_file.isChecked()
        self._file_row.setVisible(file_mode)
        self._uds_row.setVisible(not file_mode)
        if file_mode:
            if self._auto.isChecked():
                self._timer.start()
            self.reload()
        else:
            self._timer.stop()
            self._status.setText(t("切换到 UDS：点「从 UDS 读取」（先连 DoIP）"))

    def _on_auto(self, on: bool) -> None:
        if on and self._src_file.isChecked():
            self._timer.start()
        else:
            self._timer.stop()

    def _browse(self) -> None:
        start = self._path.text().strip() or str(Path.cwd() / "build")
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("打开 Collector NDJSON"),
            start,
            "NDJSON (*.ndjson *.jsonl);;All (*)",
        )
        if path:
            self._path.setText(path)
            self.reload()

    def _poll(self) -> None:
        if not self._auto.isChecked() or not self._src_file.isChecked():
            return
        path = Path(self._path.text().strip())
        if not path.is_file():
            return
        try:
            st = path.stat()
        except OSError:
            return
        if self._mtime == st.st_mtime and self._size == st.st_size:
            return
        self.reload()

    def _fill_table(self, rows: list[dict[str, Any]], *, status: str) -> None:
        if len(rows) > 2000:
            rows = rows[-2000:]
        self._table.setRowCount(len(rows))
        for i, rec in enumerate(rows):
            vals = [
                str(rec.get("t_ns", "")),
                str(rec.get("source", "")),
                str(rec.get("id", "")),
                str(rec.get("detail", "")),
                str(rec.get("pid", "")),
            ]
            for c, v in enumerate(vals):
                self._table.setItem(i, c, QTableWidgetItem(v))
        if rows:
            self._table.scrollToBottom()
        self._status.setText(status)

    def reload(self) -> None:
        if self._src_uds.isChecked():
            self._load_uds()
            return
        path = Path(self._path.text().strip())
        self._table.setRowCount(0)
        if not path.is_file():
            self._status.setText(t("文件不存在（先跑 SIL / 设置 GF_COLLECTOR_STORE）"))
            self._mtime = None
            self._size = None
            return
        rows: list[dict[str, Any]] = []
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    rows.append(rec)
            st = path.stat()
            self._mtime = st.st_mtime
            self._size = st.st_size
        except OSError as exc:
            self._status.setText(str(exc))
            return
        self._fill_table(
            rows, status=t("已加载 {n} 条 · {path}").format(n=len(rows), path=path)
        )

    def _load_uds(self) -> None:
        client = self._client_fn() if self._client_fn else None
        if client is None:
            QMessageBox.information(
                self,
                t("Collector"),
                t("请先连接 DoIP，再读取。"),
            )
            self._status.setText(t("未连接 DoIP"))
            return

        def _log(line: str) -> None:
            if self._uds_log_fn is not None:
                self._uds_log_fn(line)

        try:
            rows = client.read_collector_events(offset=0, max_n=200, on_step=_log)
        except Exception as exc:  # noqa: BLE001
            _log(f"Collector UDS ERR: {exc}")
            self._status.setText(str(exc))
            QMessageBox.warning(self, t("Collector"), str(exc))
            return
        self._fill_table(
            rows,
            status=t("UDS 已加载 {n} 条（RID F201）").format(n=len(rows)),
        )
