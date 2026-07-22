"""SKU / req.yaml editor — thin ① switches (apps/capabilities folded under 高级)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession

# Frozen topologies (DESIGN §6 / heterogeneous-compute)
KNOWN_TOPOLOGIES = [
    ("ap_only", "ap_only — 控制在 AP；无 MCU CP gateway"),
    ("ap_mcu_cp", "ap_mcu_cp — MCU=AUTOSAR CP；AP 上 mcu.cp_gateway"),
]

KNOWN_MODULES = ["core", "com", "log", "osal", "exec", "phm", "sm", "ucm", "diag", "trace"]
KNOWN_BINDINGS = ["iceoryx", "someip", "dds", "cross_domain_ipc"]
KNOWN_PROFILES = [
    ("vehicle-debug", "vehicle-debug — SIL/调试（可开 live tap）"),
    ("production-release", "production-release — 量产（强制关 tap，不编调试探针）"),
]

# A 勾选 → C 子页显示（sm 并入 exec.yaml，勾 sm 也显示「执行」）
PLATFORM_MODULE_KEYS = frozenset({"exec", "phm", "sm", "diag", "log", "ucm"})


def _lines_to_list(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _list_to_lines(values: list | None) -> str:
    return "\n".join(str(x) for x in (values or []))


class ReqEditor(QWidget):
    changed = Signal()
    """Emitted when runtime_modules change — C 页据此过滤子导航。"""
    modules_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._module_boxes: dict[str, QCheckBox] = {}
        self._binding_boxes: dict[str, QCheckBox] = {}
        self._loading = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        root = QVBoxLayout(inner)

        meta = QGroupBox("SKU 标识")
        meta_f = QFormLayout(meta)
        self._variant = QLineEdit()
        self._variant.textChanged.connect(self._on_any)
        self._topology = QComboBox()
        for value, label in KNOWN_TOPOLOGIES:
            self._topology.addItem(label, value)
        self._topology.currentIndexChanged.connect(self._on_any)
        self._product = QLineEdit()
        self._product.textChanged.connect(self._on_any)
        meta_f.addRow("variant", self._variant)
        meta_f.addRow("topology", self._topology)
        meta_f.addRow("product", self._product)
        topo_hint = QLabel(
            "B 页 external MCU ≠ ap_mcu_cp；后者才是异构 CP gateway 拓扑。"
        )
        topo_hint.setWordWrap(True)
        topo_hint.setStyleSheet("color:#666; font-size:11px;")
        meta_f.addRow("", topo_hint)
        root.addWidget(meta)

        # profile + observability together (debug/release gate)
        stage = QGroupBox("运行剖面与观测（profile 裁剪调试能力）")
        stage_l = QVBoxLayout(stage)
        stage_f = QFormLayout()
        self._profile = QComboBox()
        for value, label in KNOWN_PROFILES:
            self._profile.addItem(label, value)
        self._profile.currentIndexChanged.connect(self._on_profile_or_any)
        stage_f.addRow("profile", self._profile)
        self._live_en = QCheckBox("live_tap.enabled（iceoryx → Foxglove）")
        self._live_en.toggled.connect(self._on_profile_or_any)
        self._live_svcs = QPlainTextEdit()
        self._live_svcs.setPlaceholderText(
            "live 白名单，每行一个 semantic 服务（如 EgoMotion / Trajectory）"
        )
        self._live_svcs.setMaximumHeight(70)
        self._live_svcs.textChanged.connect(self._on_any)
        self._record_mode = QComboBox()
        self._record_mode.addItems(["minimal", "sampled", "full", "off"])
        self._record_mode.currentTextChanged.connect(self._on_profile_or_any)
        self._record_svcs = QPlainTextEdit()
        self._record_svcs.setPlaceholderText(
            "record/MCAP 白名单（必填，除非 mode=off），每行一个服务"
        )
        self._record_svcs.setMaximumHeight(70)
        self._record_svcs.textChanged.connect(self._on_any)
        self._trace = QComboBox()
        self._trace.setEditable(True)
        self._trace.addItems(["on", "off"])
        self._trace.currentTextChanged.connect(self._on_profile_or_any)
        stage_f.addRow("", self._live_en)
        stage_f.addRow("live_tap.services", self._live_svcs)
        stage_f.addRow("record.mode", self._record_mode)
        stage_f.addRow("record.services", self._record_svcs)
        stage_f.addRow("trace_export", self._trace)
        stage_l.addLayout(stage_f)
        self._obs_hint = QLabel("")
        self._obs_hint.setWordWrap(True)
        self._obs_hint.setStyleSheet("color:#666; font-size:11px;")
        stage_l.addWidget(self._obs_hint)
        root.addWidget(stage)

        mods = QGroupBox("runtime_modules（① 编进镜像 · 勾选后才在 C 页出现对应清单）")
        mods_l = QVBoxLayout(mods)
        mod_row = QHBoxLayout()
        for i, name in enumerate(KNOWN_MODULES):
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_any)
            self._module_boxes[name] = cb
            mod_row.addWidget(cb)
            if (i + 1) % 5 == 0:
                mods_l.addLayout(mod_row)
                mod_row = QHBoxLayout()
        if mod_row.count():
            mods_l.addLayout(mod_row)
        mods_note = QLabel(
            "C 页映射：exec/sm→执行 · phm→健康 · diag→诊断 · log→日志 · ucm→OTA"
        )
        mods_note.setWordWrap(True)
        mods_note.setStyleSheet("color:#666; font-size:11px;")
        mods_l.addWidget(mods_note)
        root.addWidget(mods)

        binds = QGroupBox("bindings（产品通信栈 · 与 profile 正交）")
        binds_l = QVBoxLayout(binds)
        binds_hint = QLabel(
            "勾选 = 镜像可链接该栈（如 iceoryx 主链、dds 产品互通）。"
            "profile=production-release 裁剪调试观测（live/record/trace），"
            "不会自动去掉 bindings 里的 dds。"
        )
        binds_hint.setWordWrap(True)
        binds_hint.setStyleSheet("color:#666; font-size:11px;")
        binds_l.addWidget(binds_hint)
        bind_row = QHBoxLayout()
        for name in KNOWN_BINDINGS:
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_any)
            self._binding_boxes[name] = cb
            bind_row.addWidget(cb)
        bind_row.addStretch(1)
        binds_l.addLayout(bind_row)
        root.addWidget(binds)

        acc = QGroupBox("acceptance（lineage 门禁）")
        acc_f = QFormLayout(acc)
        self._acc_desc = QLineEdit()
        self._acc_desc.textChanged.connect(self._on_any)
        self._acc_lineage = QCheckBox("lineage_required")
        self._acc_lineage.toggled.connect(self._on_any)
        self._acc_svcs = QPlainTextEdit()
        self._acc_svcs.setPlaceholderText("required_services，每行一个（可写短名 EgoMotion）")
        self._acc_svcs.setMaximumHeight(100)
        self._acc_svcs.textChanged.connect(self._on_any)
        acc_f.addRow("description", self._acc_desc)
        acc_f.addRow("", self._acc_lineage)
        acc_f.addRow("required_services", self._acc_svcs)
        root.addWidget(acc)

        self._adv_toggle = QToolButton()
        self._adv_toggle.setText("▶ 高级 · capabilities / apps")
        self._adv_toggle.setCheckable(True)
        self._adv_toggle.setChecked(False)
        self._adv_toggle.setStyleSheet("QToolButton { text-align: left; border: none; }")
        self._adv_panel = QWidget()
        adv_l = QVBoxLayout(self._adv_panel)
        adv_l.setContentsMargins(8, 0, 0, 0)
        caps_hint = QLabel(
            "capabilities：交付/文档自由标签，不驱动 compose 裁剪（可空）。"
        )
        caps_hint.setWordWrap(True)
        caps_hint.setStyleSheet("color:#666; font-size:11px;")
        adv_l.addWidget(caps_hint)
        self._caps = QPlainTextEdit()
        self._caps.setPlaceholderText("每行一个，如 front_camera / uss / driving（可选）")
        self._caps.setMaximumHeight(70)
        self._caps.textChanged.connect(self._on_any)
        adv_l.addWidget(self._caps)
        apps_hint = QLabel("apps：SIL/参考进程列表（live tap 由 profile 自动加减）。")
        apps_hint.setWordWrap(True)
        apps_hint.setStyleSheet("color:#666; font-size:11px;")
        adv_l.addWidget(apps_hint)
        self._apps = QPlainTextEdit()
        self._apps.setPlaceholderText("每行一个，如 simulators/uss_feed")
        self._apps.setMaximumHeight(80)
        self._apps.textChanged.connect(self._on_any)
        adv_l.addWidget(self._apps)
        self._adv_panel.setVisible(False)

        def _toggle_adv(on: bool) -> None:
            self._adv_panel.setVisible(on)
            self._adv_toggle.setText(
                ("▼" if on else "▶") + " 高级 · capabilities / apps"
            )

        self._adv_toggle.toggled.connect(_toggle_adv)
        root.addWidget(self._adv_toggle)
        root.addWidget(self._adv_panel)

        hint = QLabel(
            "A = SKU 开关。B = 信号连线（Ctrl+Z/Y 撤销重做）。C = 平台清单。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        root.addWidget(hint)
        root.addStretch(1)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.addWidget(scroll)

    def selected_modules(self) -> list[str]:
        return [n for n, cb in self._module_boxes.items() if cb.isChecked()]

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        if session is None:
            return
        self._loading = True
        req = session.req
        self._set_profile(str(req.get("profile") or "vehicle-debug"))
        self._variant.setText(str(req.get("variant") or ""))
        self._set_topology(str(req.get("topology") or "ap_only"))
        self._product.setText(str(req.get("product") or ""))
        self._caps.setPlainText(_list_to_lines(req.get("capabilities")))

        selected_m = set(req.get("runtime_modules") or [])
        for name, cb in self._module_boxes.items():
            cb.setChecked(name in selected_m)

        selected_b = set(req.get("bindings") or [])
        for name, cb in self._binding_boxes.items():
            cb.setChecked(name in selected_b)

        obs = req.get("observability") or {}
        if not isinstance(obs, dict):
            obs = {}
        live = obs.get("live_tap") if isinstance(obs.get("live_tap"), dict) else {}
        self._live_en.setChecked(bool(live.get("enabled")))
        self._live_svcs.setPlainText(_list_to_lines(live.get("services")))
        rec = obs.get("record")
        if isinstance(rec, dict):
            self._record_mode.setCurrentText(str(rec.get("mode") or "minimal"))
            self._record_svcs.setPlainText(_list_to_lines(rec.get("services")))
        else:
            self._record_mode.setCurrentText(str(rec or "minimal"))
            self._record_svcs.clear()
        self._trace.setCurrentText(str(obs.get("trace_export") or "on"))
        self._apps.setPlainText(_list_to_lines(req.get("apps")))

        acc = req.get("acceptance") or {}
        if isinstance(acc, dict):
            self._acc_desc.setText(str(acc.get("description") or ""))
            self._acc_lineage.setChecked(bool(acc.get("lineage_required")))
            self._acc_svcs.setPlainText(_list_to_lines(acc.get("required_services")))
        else:
            self._acc_desc.clear()
            self._acc_lineage.setChecked(False)
            self._acc_svcs.clear()

        self._loading = False
        self._apply_profile_ui()
        self.modules_changed.emit(self.selected_modules())

    def _set_profile(self, value: str) -> None:
        idx = self._profile.findData(value)
        if idx < 0:
            self._profile.blockSignals(True)
            self._profile.addItem(f"{value}（未识别）", value)
            self._profile.blockSignals(False)
            idx = self._profile.findData(value)
        self._profile.setCurrentIndex(max(0, idx))

    def _set_topology(self, value: str) -> None:
        idx = self._topology.findData(value)
        if idx < 0:
            self._topology.blockSignals(True)
            self._topology.addItem(f"{value}（未识别）", value)
            self._topology.blockSignals(False)
            idx = self._topology.findData(value)
        self._topology.setCurrentIndex(max(0, idx))

    def _apply_profile_ui(self) -> None:
        release = str(self._profile.currentData() or "") == "production-release"
        live_on = self._live_en.isChecked() and not release
        record_off = self._record_mode.currentText().strip() == "off"

        self._live_en.setEnabled(not release)
        self._live_svcs.setEnabled(live_on)
        # mode=off → 灰掉白名单；release 下 compose 视 record/trace 为 off，一并灰掉
        self._record_mode.setEnabled(not release)
        self._record_svcs.setEnabled(not release and not record_off)
        self._trace.setEnabled(not release)

        if release:
            self._obs_hint.setText(
                "production-release：live_tap / record / trace_export 强制关闭（灰调不可改）；"
                "不编 iox_obs_tap。bindings（含 dds）仍是产品栈，不会被本剖面自动去掉。"
            )
            self._obs_hint.setStyleSheet("color:#a04000; font-size:11px;")
        elif record_off or not live_on:
            bits = []
            if not live_on:
                bits.append("live 关 → services 灰调")
            if record_off:
                bits.append("record.mode=off → services 灰调")
            self._obs_hint.setText(
                "；".join(bits) + "。"
                "live / record 均为 semantic 服务白名单。"
            )
            self._obs_hint.setStyleSheet("color:#666; font-size:11px;")
        else:
            self._obs_hint.setText(
                "live / record 均为 semantic 服务白名单。"
                "vehicle-debug + live 开 → compose 自动加入 tools/iox_obs_tap。"
            )
            self._obs_hint.setStyleSheet("color:#666; font-size:11px;")

    def _on_profile_or_any(self, *_args: object) -> None:
        if not self._loading:
            self._apply_profile_ui()
        self._on_any()

    def _on_any(self, *_args: object) -> None:
        if self._loading or not self._session:
            return
        req = self._session.req
        prof = self._profile.currentData()
        req["profile"] = str(prof) if prof else "vehicle-debug"
        req["variant"] = self._variant.text().strip()
        topo = self._topology.currentData()
        req["topology"] = str(topo) if topo else "ap_only"
        if self._session.wiring.get("topology") != req["topology"]:
            self._session.wiring["topology"] = req["topology"]
            self._session.dirty_wiring = True
        req["product"] = self._product.text().strip()
        req["capabilities"] = _lines_to_list(self._caps.toPlainText())

        modules = self.selected_modules()
        prev = list(req.get("runtime_modules") or [])
        req["runtime_modules"] = modules
        req["bindings"] = [n for n, cb in self._binding_boxes.items() if cb.isChecked()]
        live_on = self._live_en.isChecked() and req["profile"] == "vehicle-debug"
        req["observability"] = {
            "live_tap": {
                "enabled": live_on,
                "services": _lines_to_list(self._live_svcs.toPlainText()),
            },
            "record": {
                "mode": self._record_mode.currentText().strip() or "minimal",
                "services": _lines_to_list(self._record_svcs.toPlainText()),
            },
            "trace_export": self._trace.currentText().strip() or "on",
        }
        req["apps"] = _lines_to_list(self._apps.toPlainText())
        prev_acc = req.get("acceptance") if isinstance(req.get("acceptance"), dict) else {}
        acceptance: dict = {
            "description": self._acc_desc.text().strip(),
            "lineage_required": self._acc_lineage.isChecked(),
            "required_services": _lines_to_list(self._acc_svcs.toPlainText()),
        }
        if prev_acc.get("sor_golden"):
            acceptance["sor_golden"] = prev_acc["sor_golden"]
        req["acceptance"] = acceptance
        self._session.dirty_req = True
        self.changed.emit()
        if modules != prev:
            self.modules_changed.emit(modules)
