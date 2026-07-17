"""SKU / req.yaml editor — full SKU fields used by compose / lineage / (later) CMake trim."""

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
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession

KNOWN_MODULES = ["core", "com", "log", "osal", "exec", "phm", "sm", "ucm", "diag", "trace"]
KNOWN_BINDINGS = ["iceoryx", "someip", "dds", "cross_domain_ipc"]
KNOWN_CAPABILITIES = ["front_camera", "uss", "driving", "parking", "surround"]


def _lines_to_list(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _list_to_lines(values: list | None) -> str:
    return "\n".join(str(x) for x in (values or []))


class ReqEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._module_boxes: dict[str, QCheckBox] = {}
        self._binding_boxes: dict[str, QCheckBox] = {}
        self._cap_boxes: dict[str, QCheckBox] = {}
        self._loading = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        root = QVBoxLayout(inner)

        meta = QGroupBox("SKU 标识")
        meta_f = QFormLayout(meta)
        self._variant = QLineEdit()
        self._topology = QLineEdit()
        self._product = QLineEdit()
        for w in (self._variant, self._topology, self._product):
            w.textChanged.connect(self._on_any)
        meta_f.addRow("variant", self._variant)
        meta_f.addRow("topology", self._topology)
        meta_f.addRow("product", self._product)
        root.addWidget(meta)

        caps = QGroupBox("capabilities（产品能力标签）")
        caps_l = QVBoxLayout(caps)
        row = QHBoxLayout()
        for name in KNOWN_CAPABILITIES:
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_any)
            self._cap_boxes[name] = cb
            row.addWidget(cb)
        caps_l.addLayout(row)
        self._cap_extra = QPlainTextEdit()
        self._cap_extra.setPlaceholderText("额外 capability，每行一个")
        self._cap_extra.setMaximumHeight(60)
        self._cap_extra.textChanged.connect(self._on_any)
        caps_l.addWidget(self._cap_extra)
        root.addWidget(caps)

        mods = QGroupBox("runtime_modules（按 SKU 裁中间件 → 后续 F 轨 CMake）")
        mods_l = QVBoxLayout(mods)
        for name in KNOWN_MODULES:
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_any)
            self._module_boxes[name] = cb
            mods_l.addWidget(cb)
        root.addWidget(mods)

        binds = QGroupBox("bindings（通信栈裁剪）")
        binds_l = QVBoxLayout(binds)
        for name in KNOWN_BINDINGS:
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_any)
            self._binding_boxes[name] = cb
            binds_l.addWidget(cb)
        root.addWidget(binds)

        obs = QGroupBox("observability")
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

        apps = QGroupBox("apps（参考 / SIL 应用列表）")
        apps_l = QVBoxLayout(apps)
        self._apps = QPlainTextEdit()
        self._apps.setPlaceholderText("每行一个，如 simulators/uss_feed")
        self._apps.setMaximumHeight(80)
        self._apps.textChanged.connect(self._on_any)
        apps_l.addWidget(self._apps)
        root.addWidget(apps)

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

        hint = QLabel(
            "req.yaml = SKU / 交付契约（裁什么、验什么）。\n"
            "wiring.yaml = 本车型集成连线（谁提供/订阅、dataflow）。\n"
            "保存或 Verify 时写回；不上板。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        root.addWidget(hint)
        root.addStretch(1)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.addWidget(scroll)

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        if session is None:
            return
        self._loading = True
        req = session.req
        self._variant.setText(str(req.get("variant") or ""))
        self._topology.setText(str(req.get("topology") or ""))
        self._product.setText(str(req.get("product") or ""))

        caps = [str(x) for x in (req.get("capabilities") or [])]
        known = set(self._cap_boxes)
        for name, cb in self._cap_boxes.items():
            cb.setChecked(name in caps)
        extra = [c for c in caps if c not in known]
        self._cap_extra.setPlainText(_list_to_lines(extra))

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

    def _on_any(self, *_args: object) -> None:
        if self._loading or not self._session:
            return
        req = self._session.req
        req["variant"] = self._variant.text().strip()
        req["topology"] = self._topology.text().strip()
        req["product"] = self._product.text().strip()

        caps = [n for n, cb in self._cap_boxes.items() if cb.isChecked()]
        caps.extend(_lines_to_list(self._cap_extra.toPlainText()))
        # de-dupe preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for c in caps:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        req["capabilities"] = uniq

        req["runtime_modules"] = [n for n, cb in self._module_boxes.items() if cb.isChecked()]
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
