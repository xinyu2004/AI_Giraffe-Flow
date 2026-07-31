"""GMT OTA sheet — select package, drive DoIP → board UCM (SIL)."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.doip_client import DoipClient
from gf_gmt.i18n import t


class _OtaWorker(QThread):
    finished_ok = Signal(str)
    finished_err = Signal(str)
    log_line = Signal(str)

    def __init__(
        self,
        host: str,
        port: int,
        package_id: str,
        artifact: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._host = host
        self._port = port
        self._package_id = package_id
        self._artifact = artifact

    def run(self) -> None:
        client = DoipClient()
        try:
            self.log_line.emit(f"connect {self._host}:{self._port}")
            client.connect(self._host, self._port)
            client.routing_activation()
            self.log_line.emit("RoutingActivation OK")
            tp = client.tester_present()
            self.log_line.emit(f"TesterPresent → {tp.hex()}")
            resp = client.start_ota(self._package_id, self._artifact)
            self.log_line.emit(f"startRoutine → {resp.hex()}")
            if len(resp) >= 5 and resp[0] == 0x71 and resp[4] == 0x00:
                self.finished_ok.emit(t("OTA Activate 成功"))
            else:
                self.finished_err.emit(t("OTA 失败（见板端 Collector ota_failed）"))
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.finished_err.emit(str(exc))
        finally:
            client.close()


class OtaPanel(QWidget):
    """Host DoIP OTA: package select / progress log / result."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: _OtaWorker | None = None

        tip = QLabel(
            t(
                "经 DoIP TCP 驱动板端/SIL 的 UCM（gf_doip_ota_server）。"
                "非真刷写；失败事件进 Collector。"
            )
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#555;")

        form = QFormLayout()
        self.host = QLineEdit("127.0.0.1")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(13400)
        self.pkg_id = QLineEdit("pkg.demo")
        self.artifact = QLineEdit("/tmp/gf_demo.swu")
        form.addRow(t("DoIP Host"), self.host)
        form.addRow(t("DoIP Port"), self.port)
        form.addRow(t("Package id"), self.pkg_id)
        form.addRow(t("Artifact path"), self.artifact)

        row = QHBoxLayout()
        self.btn_start = QPushButton(t("Start OTA"))
        self.btn_start.clicked.connect(self._on_start)
        self.status = QLabel("—")
        row.addWidget(self.btn_start)
        row.addWidget(self.status, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(220)

        root = QVBoxLayout(self)
        root.addWidget(tip)
        root.addLayout(form)
        root.addLayout(row)
        root.addWidget(self.log)

    def _on_start(self) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "OTA", t("OTA 进行中"))
            return
        self.log.clear()
        self.status.setText(t("运行中…"))
        self.btn_start.setEnabled(False)
        self._worker = _OtaWorker(
            self.host.text().strip() or "127.0.0.1",
            int(self.port.value()),
            self.pkg_id.text().strip() or "pkg.demo",
            self.artifact.text().strip() or "/tmp/gf_demo.swu",
            self,
        )
        self._worker.log_line.connect(self.log.append)
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.finished_err.connect(self._on_err)
        self._worker.start()

    def _on_ok(self, msg: str) -> None:
        self.status.setText(msg)
        self.log.append(msg)
        self.btn_start.setEnabled(True)

    def _on_err(self, msg: str) -> None:
        self.status.setText(msg)
        self.log.append("ERR: " + msg)
        self.btn_start.setEnabled(True)
