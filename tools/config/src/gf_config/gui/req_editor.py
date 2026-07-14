"""SKU / req.yaml editor tab."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession

KNOWN_MODULES = ["core", "com", "log", "osal", "exec", "phm", "sm", "ucm", "diag", "trace"]
KNOWN_BINDINGS = ["iceoryx", "someip", "dds", "cross_domain_ipc"]


class ReqEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._module_boxes: dict[str, QCheckBox] = {}
        self._binding_boxes: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)

        meta = QFormLayout()
        self._variant = QLineEdit()
        self._topology = QLineEdit()
        self._product = QLineEdit()
        for w in (self._variant, self._topology, self._product):
            w.textChanged.connect(self._on_meta)
        meta.addRow("variant", self._variant)
        meta.addRow("topology", self._topology)
        meta.addRow("product", self._product)
        root.addLayout(meta)

        mods = QGroupBox("runtime_modules（按 SKU 裁中间件）")
        mods_l = QVBoxLayout(mods)
        for name in KNOWN_MODULES:
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_lists)
            self._module_boxes[name] = cb
            mods_l.addWidget(cb)
        root.addWidget(mods)

        binds = QGroupBox("bindings")
        binds_l = QVBoxLayout(binds)
        for name in KNOWN_BINDINGS:
            cb = QCheckBox(name)
            cb.toggled.connect(self._on_lists)
            self._binding_boxes[name] = cb
            binds_l.addWidget(cb)
        root.addWidget(binds)

        self._hint = QLabel("打开 project.yaml 后编辑；保存或 Compose 时写回 req.yaml")
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)
        root.addStretch(1)

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        if session is None:
            return
        req = session.req
        self._variant.blockSignals(True)
        self._topology.blockSignals(True)
        self._product.blockSignals(True)
        self._variant.setText(str(req.get("variant") or ""))
        self._topology.setText(str(req.get("topology") or ""))
        self._product.setText(str(req.get("product") or ""))
        self._variant.blockSignals(False)
        self._topology.blockSignals(False)
        self._product.blockSignals(False)

        selected_m = set(req.get("runtime_modules") or [])
        for name, cb in self._module_boxes.items():
            cb.blockSignals(True)
            cb.setChecked(name in selected_m)
            cb.blockSignals(False)

        selected_b = set(req.get("bindings") or [])
        for name, cb in self._binding_boxes.items():
            cb.blockSignals(True)
            cb.setChecked(name in selected_b)
            cb.blockSignals(False)

    def _on_meta(self) -> None:
        if not self._session:
            return
        self._session.req["variant"] = self._variant.text().strip()
        self._session.req["topology"] = self._topology.text().strip()
        self._session.req["product"] = self._product.text().strip()
        self._session.dirty_req = True
        self.changed.emit()

    def _on_lists(self) -> None:
        if not self._session:
            return
        self._session.set_list_field(
            "runtime_modules",
            [n for n, cb in self._module_boxes.items() if cb.isChecked()],
        )
        self._session.set_list_field(
            "bindings",
            [n for n, cb in self._binding_boxes.items() if cb.isChecked()],
        )
        self.changed.emit()
