"""SKU / req.yaml editor — thin ① switches (apps folded under 高级)."""

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
            "B 页 external MCU 节点 ≠ ap_mcu_cp。"
            "后者才是异构 CP gateway 拓扑。"
        )
        topo_hint.setWordWrap(True)
        topo_hint.setStyleSheet("color:#666; font-size:11px;")
        meta_f.addRow("", topo_hint)
        root.addWidget(meta)

        caps = QGroupBox("capabilities（自由标签 · 不假装穷尽客户能力）")
        caps_l = QVBoxLayout(caps)
        caps_hint = QLabel(
            "写入 req 供交付/文档标记；不驱动 compose 裁剪。"
            "客户专有标签直接写，不必进平台清单。"
        )
        caps_hint.setWordWrap(True)
        caps_hint.setStyleSheet("color:#666;")
        caps_l.addWidget(caps_hint)
        self._caps = QPlainTextEdit()
        self._caps.setPlaceholderText("每行一个，如 front_camera / uss / driving / oem_xxx")
        self._caps.setMaximumHeight(90)
        self._caps.textChanged.connect(self._on_any)
        caps_l.addWidget(self._caps)
        root.addWidget(caps)

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

        binds = QGroupBox("bindings（通信栈开关）")
        binds_l = QHBoxLayout(binds)
        for name in KNOWN_BINDINGS:
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_any)
            self._binding_boxes[name] = cb
            binds_l.addWidget(cb)
        binds_l.addStretch(1)
        root.addWidget(binds)

        obs = QGroupBox("observability（粗开关；细级别在 C·日志）")
        obs_f = QFormLayout(obs)
        self._record = QComboBox()
        self._record.setEditable(True)
        self._record.addItems(["full", "minimal", "off"])
        self._trace = QComboBox()
        self._trace.setEditable(True)
        self._trace.addItems(["on", "off"])
        self._record.currentTextChanged.connect(self._on_any)
        self._trace.currentTextChanged.connect(self._on_any)
        obs_f.addRow("record", self._record)
        obs_f.addRow("trace_export", self._trace)
        root.addWidget(obs)

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

        self._apps_toggle = QToolButton()
        self._apps_toggle.setText("▶ 高级 · apps（参考 / SIL 列表）")
        self._apps_toggle.setCheckable(True)
        self._apps_toggle.setChecked(False)
        self._apps_toggle.setStyleSheet("QToolButton { text-align: left; border: none; }")
        self._apps_panel = QWidget()
        apps_l = QVBoxLayout(self._apps_panel)
        apps_l.setContentsMargins(8, 0, 0, 0)
        self._apps = QPlainTextEdit()
        self._apps.setPlaceholderText("每行一个，如 simulators/uss_feed")
        self._apps.setMaximumHeight(80)
        self._apps.textChanged.connect(self._on_any)
        apps_l.addWidget(self._apps)
        self._apps_panel.setVisible(False)

        def _toggle_apps(on: bool) -> None:
            self._apps_panel.setVisible(on)
            self._apps_toggle.setText(
                ("▼" if on else "▶") + " 高级 · apps（参考 / SIL 列表）"
            )

        self._apps_toggle.toggled.connect(_toggle_apps)
        root.addWidget(self._apps_toggle)
        root.addWidget(self._apps_panel)

        hint = QLabel(
            "A = SKU 开关（要不要）。B = 信号连线。C = 平台清单（仅显示已勾选模块）。"
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
        if isinstance(obs, dict):
            self._record.setCurrentText(str(obs.get("record") or "full"))
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
        self.modules_changed.emit(self.selected_modules())

    def _set_topology(self, value: str) -> None:
        idx = self._topology.findData(value)
        if idx < 0:
            # unknown legacy value — show as-is without inventing options
            self._topology.blockSignals(True)
            self._topology.addItem(f"{value}（未识别）", value)
            self._topology.blockSignals(False)
            idx = self._topology.findData(value)
        self._topology.setCurrentIndex(max(0, idx))

    def _on_any(self, *_args: object) -> None:
        if self._loading or not self._session:
            return
        req = self._session.req
        req["variant"] = self._variant.text().strip()
        topo = self._topology.currentData()
        req["topology"] = str(topo) if topo else "ap_only"
        # keep wiring metadata in sync (compose uses req; wiring 也有同名字段)
        if self._session.wiring.get("topology") != req["topology"]:
            self._session.wiring["topology"] = req["topology"]
            self._session.dirty_wiring = True
        req["product"] = self._product.text().strip()
        req["capabilities"] = _lines_to_list(self._caps.toPlainText())

        modules = self.selected_modules()
        prev = list(req.get("runtime_modules") or [])
        req["runtime_modules"] = modules
        req["bindings"] = [n for n, cb in self._binding_boxes.items() if cb.isChecked()]
        req["observability"] = {
            "record": self._record.currentText().strip() or "full",
            "trace_export": self._trace.currentText().strip() or "on",
        }
        req["apps"] = _lines_to_list(self._apps.toPlainText())
        req["acceptance"] = {
            "description": self._acc_desc.text().strip(),
            "lineage_required": self._acc_lineage.isChecked(),
            "required_services": _lines_to_list(self._acc_svcs.toPlainText()),
        }
        self._session.dirty_req = True
        self.changed.emit()
        if modules != prev:
            self.modules_changed.emit(modules)
