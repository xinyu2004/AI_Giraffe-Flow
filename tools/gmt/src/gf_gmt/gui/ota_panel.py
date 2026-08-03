"""GMT OTA sheet — select package, drive DoIP → board UCM (SIL)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QSettings, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
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

from gf_gmt.doip_client import (
    OTA_MODE_FILE,
    DoipClient,
    format_uds_step,
)
from gf_gmt.i18n import t

_SETTINGS_ORG = "GiraffeFlow"
_SETTINGS_APP = "GMT"
_KEY_SEC_PLUGIN = "ota/sec_plugin"
_KEY_ARTIFACT = "ota/artifact_path"
_KEY_PKG_ID = "ota/package_id"
_KEY_HOST = "ota/host"
_KEY_PORT = "ota/port"

_STYLE_IDLE = "color:#555; min-width: 4.5em;"
_STYLE_OK = "color:#1b5e20; font-weight:600; min-width: 4.5em;"
_STYLE_ERR = "color:#b71c1c; font-weight:600; min-width: 4.5em;"

# Display labels for diag.yaml ota_transfer.mode (must match gf-config).
_MODE_LABELS: dict[str, str] = {
    "request_file_transfer": "0x38 · RequestFileTransfer",
    "request_download": "0x34 · RequestDownload",
    "routine_sil": "0x31 · RoutineControl (SIL)",
}

def _load_diag_bundle(project_dir: Path | None) -> dict[str, Any]:
    """iso flags + timing + ota_transfer + doip port from project diag.yaml."""
    out: dict[str, Any] = {
        "iso14229": True,
        "iso13400": True,
        "ota_mode": OTA_MODE_FILE,
        "require_programming": True,
        "require_security": True,
        "max_block": 1024,
        "s3_ms": 5000,
        "tp_period_ms": 2000,
        "p2_star_ms": 5000,
        "security_delay_ms": 10000,
        "tcp_port": 13400,
        "tester_address": 0x0E80,
        "logical_address": 0x0E00,
    }
    if project_dir is None:
        return out
    proj = project_dir / "project.yaml"
    diag = project_dir / "platform" / "diag.yaml"
    if proj.is_file():
        try:
            raw = yaml.safe_load(proj.read_text(encoding="utf-8")) or {}
            plat = raw.get("platform") if isinstance(raw, dict) else None
            if isinstance(plat, dict) and plat.get("diag"):
                diag = project_dir / str(plat["diag"]).strip()
        except Exception:  # noqa: BLE001
            pass
    if not diag.is_file():
        return out
    try:
        data: dict[str, Any] = yaml.safe_load(diag.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return out
    standards = data.get("standards") if isinstance(data.get("standards"), dict) else {}
    doip = data.get("doip") if isinstance(data.get("doip"), dict) else {}
    timing = data.get("timing") if isinstance(data.get("timing"), dict) else {}
    xfer = data.get("ota_transfer") if isinstance(data.get("ota_transfer"), dict) else {}
    iso14229 = bool(standards.get("iso_14229_uds", True))
    iso13400 = bool(standards.get("iso_13400_doip", doip.get("enabled", False)))
    if iso13400 and not iso14229:
        iso14229 = True
    out["iso14229"] = iso14229
    out["iso13400"] = iso13400 and iso14229
    out["ota_mode"] = str(xfer.get("mode") or OTA_MODE_FILE)
    out["require_programming"] = bool(xfer.get("require_programming_session", True))
    out["require_security"] = bool(xfer.get("require_security", True))
    try:
        out["max_block"] = int(xfer.get("max_block_length") or 1024)
    except (TypeError, ValueError):
        out["max_block"] = 1024
    try:
        out["s3_ms"] = int(timing.get("s3_server_ms") or 5000)
        out["tp_period_ms"] = int(timing.get("tester_present_period_ms") or 2000)
        out["p2_star_ms"] = int(timing.get("p2_star_server_ms") or 5000)
        out["security_delay_ms"] = int(timing.get("security_delay_ms") or 10000)
    except (TypeError, ValueError):
        pass
    try:
        if doip.get("tcp_port") is not None:
            out["tcp_port"] = int(doip["tcp_port"])
        if doip.get("tester_address") is not None:
            out["tester_address"] = int(str(doip["tester_address"]), 0)
        if doip.get("logical_address") is not None:
            out["logical_address"] = int(str(doip["logical_address"]), 0)
    except (TypeError, ValueError):
        pass
    return out


class _ConnectWorker(QThread):
    finished_ok = Signal(object)  # DoipClient
    finished_err = Signal(str)
    log_line = Signal(str)

    def __init__(
        self,
        host: str,
        port: int,
        *,
        tester: int,
        entity: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._host = host
        self._port = port
        self._tester = tester
        self._entity = entity

    def run(self) -> None:
        client = DoipClient()
        client.tester = self._tester & 0xFFFF
        client.entity = self._entity & 0xFFFF
        try:
            client.connect(self._host, self._port)
            self.log_line.emit(f"DoIP TCP connect {self._host}:{self._port}  [OK]")
            client.routing_activation()
            self.log_line.emit(
                f"DoIP RoutingActivation tester=0x{client.tester:04X}  [OK]"
            )
            req = bytes([0x3E, 0x00])
            resp = client.tester_present()
            self.log_line.emit(format_uds_step(req, resp))
            self.finished_ok.emit(client)
        except Exception as exc:  # noqa: BLE001
            client.close()
            self.finished_err.emit(str(exc))


class _OtaWorker(QThread):
    finished_ok = Signal(str)
    finished_err = Signal(str)
    log_line = Signal(str)

    def __init__(
        self,
        client: DoipClient,
        package_id: str,
        artifact: str,
        *,
        mode: str,
        max_block: int,
        require_programming: bool,
        require_security: bool,
        close_after: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._package_id = package_id
        self._artifact = artifact
        self._mode = mode
        self._max_block = max_block
        self._require_programming = require_programming
        self._require_security = require_security
        self._close_after = close_after

    def run(self) -> None:
        try:
            self.log_line.emit(
                f"OTA begin  mode={self._mode}  package={self._package_id}  "
                f"artifact={self._artifact}"
            )
            resp = self._client.run_ota_sequence(
                self._package_id,
                self._artifact,
                mode=self._mode,
                max_block=self._max_block,
                require_programming=self._require_programming,
                require_security=self._require_security,
                on_step=self.log_line.emit,
            )
            ok = False
            if self._mode.strip().lower() in ("routine_sil", "0x31", "31", "sil"):
                ok = len(resp) >= 5 and resp[0] == 0x71 and resp[4] == 0x00
            else:
                ok = bool(resp) and resp[0] == 0x77
            if ok:
                self.finished_ok.emit(t("OTA 序列完成（传输/Activate OK）"))
            else:
                self.finished_err.emit(t("OTA 失败（见板端 Collector ota_failed）"))
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc))
        finally:
            if self._close_after:
                self._client.close()


class OtaPanel(QWidget):
    """Host DoIP OTA: compact controls; ISO / transfer mode from project diag.yaml."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: QThread | None = None
        self._client: DoipClient | None = None
        self._project_dir: Path | None = None
        self._cfg = _load_diag_bundle(None)
        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)

        iso_row = QWidget()
        iso_l = QHBoxLayout(iso_row)
        iso_l.setContentsMargins(0, 0, 0, 0)
        self.iso_14229 = QCheckBox(t("ISO 14229"))
        self.iso_13400 = QCheckBox(t("ISO 13400 DoIP"))
        for cb in (self.iso_14229, self.iso_13400):
            cb.setChecked(True)
            cb.setEnabled(False)
            cb.setToolTip(t("只读：在 gf-config 诊断页配置"))
        iso_l.addWidget(self.iso_14229)
        iso_l.addWidget(self.iso_13400)
        iso_l.addStretch(1)

        self.mode_label = QLabel("—")
        self.mode_label.setStyleSheet("color:#555;")
        self.timing_label = QLabel("—")
        self.timing_label.setStyleSheet("color:#555; font-size:11px;")

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        host_port = QWidget()
        hp = QHBoxLayout(host_port)
        hp.setContentsMargins(0, 0, 0, 0)
        hp.setSpacing(6)
        hp.addWidget(QLabel("Host"))
        self.host = QLineEdit(
            str(self._settings.value(_KEY_HOST, "127.0.0.1") or "127.0.0.1")
        )
        self.host.setMaximumWidth(140)
        self.host.setToolTip(
            t("SIL / 板端 DoIP 地址（本机 127.0.0.1；远端填局域网 IP）")
        )
        hp.addWidget(self.host)
        hp.addWidget(QLabel("│ DoIP tcp"))
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(self._settings.value(_KEY_PORT, 13400) or 13400))
        self.port.setMaximumWidth(72)
        self.port.setToolTip(
            t("DoIP TCP 端口（默认 13400，与 diag.yaml / GF_DOIP_PORT 一致）")
        )
        hp.addWidget(self.port)
        self.btn_connect = QPushButton(t("连接"))
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_disconnect = QPushButton(t("断开"))
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.btn_disconnect.setToolTip(t("断开 DoIP TCP；停止 0x3E keep-alive"))
        self.conn_status = QLabel(t("空闲"))
        self.conn_status.setStyleSheet(_STYLE_IDLE)
        hp.addWidget(self.btn_connect)
        hp.addWidget(self.btn_disconnect)
        hp.addWidget(self.conn_status)
        hp.addStretch(1)

        self.pkg_id = QLineEdit(
            str(self._settings.value(_KEY_PKG_ID, "pkg.demo") or "pkg.demo")
        )
        self.pkg_id.setToolTip(
            t(
                "UCM 包逻辑名（PackageInfo.id）。"
                "0x38/0x34 路径随传输元数据下发；routine_sil 随 0x31 发给板端。"
                "与磁盘 Artifact 路径分开，便于同一文件换不同包名做 SIL。"
            )
        )

        art_row = QWidget()
        art_l = QHBoxLayout(art_row)
        art_l.setContentsMargins(0, 0, 0, 0)
        self.artifact = QLineEdit(
            str(
                self._settings.value(_KEY_ARTIFACT, "/tmp/gf_demo.swu")
                or "/tmp/gf_demo.swu"
            )
        )
        self.artifact.setToolTip(
            t(
                "主机侧产物路径。0x38/0x34 模式会按块经 DoIP 下发；"
                "SIL 可用 bash scripts/make_sil_swu.sh 生成假包（magic GFSW）。"
                "真 RAUC 刷写 → P3z。"
            )
        )
        art_browse = QPushButton(t("浏览…"))
        art_browse.clicked.connect(self._browse_artifact)
        art_browse.setToolTip(t("选择 OTA 产物文件"))
        art_l.addWidget(self.artifact, stretch=1)
        art_l.addWidget(art_browse)

        plugin_row = QWidget()
        plugin_l = QHBoxLayout(plugin_row)
        plugin_l.setContentsMargins(0, 0, 0, 0)
        self.sec_plugin = QLineEdit(
            str(self._settings.value(_KEY_SEC_PLUGIN, "") or "")
        )
        self.sec_plugin.setPlaceholderText(t("空=板端用内置 SIL stub；按 OEM 记本地路径"))
        self.sec_plugin.setToolTip(
            t(
                "只保存在 GMT 本地设置，不写 diag.yaml。"
                "板端/SIL 启动时可用环境变量 GF_DIAG_SEC_PLUGIN 指向同一路径。"
            )
        )
        self.sec_plugin.editingFinished.connect(self._persist_settings)
        plug_browse = QPushButton(t("浏览…"))
        plug_browse.clicked.connect(self._browse_plugin)
        plugin_l.addWidget(self.sec_plugin, stretch=1)
        plugin_l.addWidget(plug_browse)

        form.addRow(t("Standards"), iso_row)
        form.addRow(t("传输模式"), self.mode_label)
        form.addRow(t("会话时序"), self.timing_label)
        form.addRow(t("连接"), host_port)
        form.addRow(t("Package id"), self.pkg_id)
        form.addRow(t("Artifact path"), art_row)
        form.addRow(t("0x27/0x29 插件"), plugin_row)

        self.host.editingFinished.connect(self._persist_settings)
        self.port.editingFinished.connect(self._persist_settings)
        self.pkg_id.editingFinished.connect(self._persist_settings)
        self.artifact.editingFinished.connect(self._persist_settings)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_start = QPushButton(t("Start OTA"))
        self.btn_start.setFixedWidth(96)
        self.btn_start.clicked.connect(self._on_start)
        self.status = QLabel("—")
        row.addWidget(self.btn_start)
        row.addWidget(self.status, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText(
            t("DoIP / UDS 过程日志（0x10 → 0x27 → 0x38/0x34 → 0x36 → 0x37）")
        )

        hint = QLabel(
            t(
                "配置在 gf-config（diag.yaml）；本页只读跟从传输模式与时序。"
                "流程：run_sil（起 DoIP）→ 加载项目 → 连接 → Start OTA。"
                "非真刷写；失败进 Collector ota_failed。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666; font-size:11px;")

        root = QVBoxLayout(self)
        root.addWidget(hint)
        root.addLayout(form)
        root.addLayout(row)
        root.addWidget(self.log, stretch=1)

        self._tp_timer = QTimer(self)
        self._tp_timer.timeout.connect(self._on_tester_present_tick)

        self._apply_cfg_labels()
        self._refresh_actions()

    def set_project_dir(self, project_dir: Path | None) -> None:
        self._project_dir = project_dir
        self._cfg = _load_diag_bundle(project_dir)
        self.iso_14229.setChecked(bool(self._cfg["iso14229"]))
        self.iso_13400.setChecked(bool(self._cfg["iso13400"]))
        # Prefer project tcp_port when not mid-connection
        if self._client is None:
            self.port.setValue(int(self._cfg["tcp_port"]))
        self._apply_cfg_labels()
        self._refresh_actions()

    def _apply_cfg_labels(self) -> None:
        mode = str(self._cfg.get("ota_mode") or OTA_MODE_FILE)
        label = _MODE_LABELS.get(mode, mode)
        self.mode_label.setText(label)
        self.mode_label.setToolTip(
            t(
                "只读：gf-config → diag.yaml → ota_transfer.mode\n"
                "• request_file_transfer = 0x38→0x36→0x37（推荐）\n"
                "• request_download = 0x34→0x36→0x37\n"
                "• routine_sil = 0x31 F100 捷径（无字节管道）"
            )
        )
        s3 = int(self._cfg.get("s3_ms") or 5000)
        tp = int(self._cfg.get("tp_period_ms") or 2000)
        p2s = int(self._cfg.get("p2_star_ms") or 5000)
        warn = ""
        if tp >= s3:
            warn = " ⚠ TP≥S3"
        self.timing_label.setText(
            f"S3={s3} ms · 0x3E={tp} ms · P2*={p2s} ms{warn}"
        )
        self.timing_label.setToolTip(
            t(
                "只读：diag.yaml timing。\n"
                "连接后 GMT 按 tester_present_period_ms 发 0x3E keep-alive；"
                "周期须小于 s3_server_ms。P2* 用作收包超时。"
            )
        )

    def _has_project(self) -> bool:
        return self._project_dir is not None

    def _refresh_actions(self) -> None:
        has_proj = self._has_project()
        connected = self._client is not None
        busy = self._busy()
        iso13400 = self.iso_13400.isChecked()

        self.host.setEnabled(has_proj and not connected)
        self.port.setEnabled(has_proj and not connected)
        self.btn_connect.setEnabled(
            has_proj and iso13400 and not connected and not busy
        )
        self.btn_disconnect.setEnabled(connected and not busy)
        self.btn_start.setEnabled(has_proj and connected and not busy)

        if not has_proj:
            self.btn_connect.setToolTip(t("请先加载项目（与 Live/回灌相同）"))
            self.btn_start.setToolTip(t("请先加载项目，再连接 DoIP"))
            if not connected:
                self.conn_status.setText(t("需加载项目"))
                self.conn_status.setStyleSheet(_STYLE_IDLE)
        elif not iso13400:
            tip = t("项目未启用 ISO 13400 DoIP（请在 gf-config 诊断页打开）")
            self.btn_connect.setToolTip(tip)
            self.btn_start.setToolTip(tip)
        elif not connected:
            self.btn_connect.setToolTip(t("连 SIL gf_doip_ota_server（需先 run_sil）"))
            self.btn_start.setToolTip(t("请先连接 DoIP"))
        else:
            self.btn_connect.setToolTip(t("连 SIL gf_doip_ota_server（需先 run_sil）"))
            self.btn_start.setToolTip(
                t(
                    "按 diag.yaml 传输模式发 UDS（过程写在下方日志）：\n"
                    "默认 0x10 → 0x27 → 0x38/0x34 → 0x36… → 0x37 → Activate"
                )
            )

    def _persist_settings(self) -> None:
        self._settings.setValue(_KEY_HOST, self.host.text().strip() or "127.0.0.1")
        self._settings.setValue(_KEY_PORT, int(self.port.value()))
        self._settings.setValue(
            _KEY_PKG_ID, self.pkg_id.text().strip() or "pkg.demo"
        )
        self._settings.setValue(_KEY_ARTIFACT, self.artifact.text().strip())
        self._settings.setValue(_KEY_SEC_PLUGIN, self.sec_plugin.text().strip())

    def _set_conn_ui(self, *, connected: bool, text: str, err: bool = False) -> None:
        self.conn_status.setText(text)
        if err:
            self.conn_status.setStyleSheet(_STYLE_ERR)
        elif connected:
            self.conn_status.setStyleSheet(_STYLE_OK)
        else:
            self.conn_status.setStyleSheet(_STYLE_IDLE)
        self._refresh_actions()
        if connected:
            self._start_tp_timer()
        else:
            self._tp_timer.stop()

    def _start_tp_timer(self) -> None:
        period = max(200, int(self._cfg.get("tp_period_ms") or 2000))
        self._tp_timer.start(period)

    def _on_tester_present_tick(self) -> None:
        if self._client is None or self._busy():
            return
        try:
            # suppressPosRsp — keep S3 alive without log spam
            self._client.tester_present(suppress=True)
        except Exception:  # noqa: BLE001
            self._disconnect()
            self._set_conn_ui(connected=False, text=t("连接丢失"), err=True)

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _on_connect(self) -> None:
        if self._busy() or self._client is not None:
            return
        if not self._has_project():
            QMessageBox.information(
                self, "OTA", t("请先加载项目（与 Live/回灌相同）")
            )
            return
        if not self.iso_13400.isChecked():
            QMessageBox.information(
                self,
                "OTA",
                t("项目未启用 ISO 13400 DoIP（请在 gf-config 诊断页打开）"),
            )
            return
        self._persist_settings()
        self.btn_connect.setEnabled(False)
        self.conn_status.setText(t("连接中…"))
        self.conn_status.setStyleSheet(_STYLE_IDLE)
        host = self.host.text().strip() or "127.0.0.1"
        port = int(self.port.value())
        w = _ConnectWorker(
            host,
            port,
            tester=int(self._cfg.get("tester_address") or 0x0E80),
            entity=int(self._cfg.get("logical_address") or 0x0E00),
            parent=self,
        )
        self._worker = w
        w.log_line.connect(self.log.append)
        w.finished_ok.connect(self._on_connect_ok)
        w.finished_err.connect(self._on_connect_err)
        w.start()

    def _on_disconnect(self) -> None:
        if self._busy():
            return
        self._disconnect()

    def _on_connect_ok(self, client: object) -> None:
        self._client = client if isinstance(client, DoipClient) else None
        self._worker = None
        if self._client is None:
            self._set_conn_ui(connected=False, text=t("空闲"), err=True)
            return
        self._set_conn_ui(connected=True, text=t("已连接"))
        p2s = max(0.5, int(self._cfg.get("p2_star_ms") or 5000) / 1000.0)
        self._client.set_response_timeout(p2s)
        self.log.append(
            f"0x3E keep-alive every {int(self._cfg.get('tp_period_ms') or 2000)} ms "
            f"(S3={int(self._cfg.get('s3_ms') or 5000)} ms, P2*={int(p2s * 1000)} ms)"
        )

    def _on_connect_err(self, msg: str) -> None:
        self._client = None
        self._worker = None
        self._set_conn_ui(connected=False, text=t("连接失败"), err=True)
        self.log.append(f"DoIP connect ERR: {msg}")

    def _disconnect(self) -> None:
        self._tp_timer.stop()
        if self._client is not None:
            self._client.close()
            self._client = None
        self._set_conn_ui(connected=False, text=t("空闲"))
        self.log.append("DoIP disconnected")

    def _browse_artifact(self) -> None:
        start = self.artifact.text().strip() or (
            str(self._project_dir) if self._project_dir else ""
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("选择 OTA 产物文件"),
            start,
            t("软件包 (*.swu *.zip *.bin);;所有文件 (*)"),
        )
        if path:
            self.artifact.setText(path)
            self._persist_settings()

    def _browse_plugin(self) -> None:
        start = self.sec_plugin.text().strip() or (
            str(self._project_dir) if self._project_dir else ""
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("选择 0x27/0x29 安全插件（.so / .dll）"),
            start,
            t("动态库 (*.so *.dll);;所有文件 (*)"),
        )
        if path:
            self.sec_plugin.setText(path)
            self._persist_settings()

    def _on_start(self) -> None:
        if self._busy():
            QMessageBox.information(self, "OTA", t("OTA 进行中"))
            return
        if not self._has_project():
            QMessageBox.information(
                self, "OTA", t("请先加载项目（与 Live/回灌相同）")
            )
            return
        if not self.iso_14229.isChecked():
            QMessageBox.warning(
                self,
                "OTA",
                t("项目未启用 ISO 14229（请在 gf-config 诊断页打开）"),
            )
            return
        if not self.iso_13400.isChecked():
            QMessageBox.information(
                self,
                "OTA",
                t("项目未启用 ISO 13400 DoIP（请在 gf-config 诊断页打开）"),
            )
            return
        if self._client is None:
            QMessageBox.information(
                self, "OTA", t("请先连接 DoIP（Host:Port 旁「连接」）")
            )
            return
        self._persist_settings()
        self.status.setText(t("运行中…"))
        self.btn_start.setEnabled(False)
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(False)
        # Pause keep-alive during transfer (activity from 0x36 also refreshes S3)
        self._tp_timer.stop()
        w = _OtaWorker(
            self._client,
            self.pkg_id.text().strip() or "pkg.demo",
            self.artifact.text().strip() or "/tmp/gf_demo.swu",
            mode=str(self._cfg.get("ota_mode") or OTA_MODE_FILE),
            max_block=int(self._cfg.get("max_block") or 1024),
            require_programming=bool(self._cfg.get("require_programming", True)),
            require_security=bool(self._cfg.get("require_security", True)),
            close_after=False,
            parent=self,
        )
        self._worker = w
        w.log_line.connect(self.log.append)
        w.finished_ok.connect(self._on_ok)
        w.finished_err.connect(self._on_err)
        w.start()

    def _on_ok(self, msg: str) -> None:
        self.status.setText(msg)
        self.log.append(msg)
        self._worker = None
        self._set_conn_ui(connected=self._client is not None, text=t("已连接"))

    def _on_err(self, msg: str) -> None:
        self.status.setText(msg)
        self.log.append("ERR: " + msg)
        self._worker = None
        if self._client is not None:
            try:
                self._client.tester_present()
                self._set_conn_ui(connected=True, text=t("已连接"))
            except Exception:  # noqa: BLE001
                self._disconnect()
                self._set_conn_ui(connected=False, text=t("连接丢失"), err=True)
        else:
            self._set_conn_ui(connected=False, text=t("空闲"))
