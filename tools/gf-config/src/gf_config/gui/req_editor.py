"""SKU / req.yaml editor — thin ① on tab 1 (runtime_modules live on tab 2)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession
from gf_config.i18n import t

# Frozen topologies (DESIGN §6 / heterogeneous-compute)
KNOWN_TOPOLOGIES = [
    ("ap_only", "ap_only"),
    ("ap_mcu_cp", "ap_mcu_cp"),
]

KNOWN_BINDINGS = ["iceoryx", "someip", "dds", "cross_domain_ipc"]
KNOWN_PROFILES = [
    ("vehicle-debug", "vehicle-debug"),
    ("production-release", "production-release"),
]

TAP_APP = "tools/iox_obs_tap"
INJECT_APP = "tools/iox_obs_inject"
_AUTO_APPS = frozenset({TAP_APP, INJECT_APP})


def _lines_to_list(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _list_to_lines(values: list | None) -> str:
    return "\n".join(str(x) for x in (values or []))


def _strip_tap_apps(values: list | None) -> list[str]:
    return [
        str(x).strip()
        for x in (values or [])
        if str(x).strip() and str(x).strip() not in _AUTO_APPS
    ]


class ReqEditor(QWidget):
    """Thin SKU fields for tab 1. Does not own runtime_modules or apps/capabilities UI."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._binding_boxes: dict[str, QCheckBox] = {}
        self._loading = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root = QVBoxLayout(inner)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        def _form() -> QFormLayout:
            f = QFormLayout()
            f.setContentsMargins(4, 4, 4, 4)
            f.setHorizontalSpacing(6)
            f.setVerticalSpacing(4)
            f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            return f

        meta = QGroupBox("SKU")
        meta_f = _form()
        meta.setLayout(meta_f)
        self._variant = QLineEdit()
        self._variant.textChanged.connect(self._on_any)
        self._topology = QComboBox()
        self._topology.setToolTip(t("ap_only=无 CP；ap_mcu_cp=MCU CP gateway"))
        for value, label in KNOWN_TOPOLOGIES:
            self._topology.addItem(label, value)
        self._topology.currentIndexChanged.connect(self._on_any)
        self._product = QLineEdit()
        self._product.textChanged.connect(self._on_any)
        meta_f.addRow("variant", self._variant)
        meta_f.addRow("topology", self._topology)
        meta_f.addRow("product", self._product)
        root.addWidget(meta)

        stage = QGroupBox(t("剖面 / 观测"))
        stage_l = QVBoxLayout(stage)
        stage_l.setContentsMargins(4, 4, 4, 4)
        stage_l.setSpacing(4)
        stage_f = _form()
        self._profile = QComboBox()
        self._profile.setToolTip(
            t("vehicle-debug 可开 live；production-release 强制关")
        )
        for value, label in KNOWN_PROFILES:
            self._profile.addItem(label, value)
        self._profile.currentIndexChanged.connect(self._on_profile_or_any)
        stage_f.addRow("profile", self._profile)
        self._live_en = QCheckBox("live_tap")
        self._live_en.setToolTip(
            t(
                "开启后 Verify/compile_sil 自动加入 tools/iox_obs_tap；"
                "run_sil 自动接 Foxglove WS。"
            )
        )
        self._live_en.toggled.connect(self._on_profile_or_any)
        self._live_mode = QComboBox()
        self._live_mode.addItem(t("wiring_all（推荐）"), "wiring_all")
        self._live_mode.addItem("explicit", "explicit")
        self._live_mode.currentIndexChanged.connect(self._on_profile_or_any)
        self._live_svcs = QPlainTextEdit()
        self._live_svcs.setPlaceholderText(t("explicit：每行一服务"))
        self._live_svcs.setMaximumHeight(48)
        self._live_svcs.setTabChangesFocus(True)
        self._live_svcs.textChanged.connect(self._on_profile_or_any)
        self._record_mode = QComboBox()
        self._record_mode.addItems(["minimal", "sampled", "full", "off"])
        self._record_mode.currentTextChanged.connect(self._on_profile_or_any)
        self._record_svcs = QPlainTextEdit()
        self._record_svcs.setPlaceholderText(t("record 白名单，每行一个"))
        self._record_svcs.setMaximumHeight(48)
        self._record_svcs.setTabChangesFocus(True)
        self._record_svcs.textChanged.connect(self._on_any)
        self._trace = QComboBox()
        self._trace.setEditable(True)
        self._trace.addItems(["on", "off"])
        self._trace.currentTextChanged.connect(self._on_profile_or_any)
        stage_f.addRow("", self._live_en)
        stage_f.addRow("mode", self._live_mode)
        stage_f.addRow("live svcs", self._live_svcs)
        stage_f.addRow("record", self._record_mode)
        stage_f.addRow("rec svcs", self._record_svcs)
        stage_f.addRow("trace", self._trace)
        stage_l.addLayout(stage_f)
        self._obs_hint = QLabel("")
        self._obs_hint.setWordWrap(True)
        self._obs_hint.setStyleSheet("color:#666; font-size:10px;")
        stage_l.addWidget(self._obs_hint)
        root.addWidget(stage)

        binds = QGroupBox("bindings")
        binds_l = QVBoxLayout(binds)
        binds_l.setContentsMargins(4, 4, 4, 4)
        binds_l.setSpacing(2)
        bind_grid = QVBoxLayout()
        bind_grid.setSpacing(2)
        row = QHBoxLayout()
        for i, name in enumerate(KNOWN_BINDINGS):
            cb = QCheckBox(name)
            cb.setStyleSheet("font-size:11px;")
            cb.toggled.connect(self._on_any)
            self._binding_boxes[name] = cb
            row.addWidget(cb)
            if (i + 1) % 2 == 0:
                row.addStretch(1)
                bind_grid.addLayout(row)
                row = QHBoxLayout()
        if row.count():
            row.addStretch(1)
            bind_grid.addLayout(row)
        binds_l.addLayout(bind_grid)
        root.addWidget(binds)

        acc = QGroupBox("acceptance")
        acc_f = _form()
        acc.setLayout(acc_f)
        self._acc_desc = QLineEdit()
        self._acc_desc.textChanged.connect(self._on_any)
        self._acc_lineage = QCheckBox("lineage_required")
        self._acc_lineage.toggled.connect(self._on_any)
        self._acc_svcs = QPlainTextEdit()
        self._acc_svcs.setPlaceholderText(t("required_services，每行一个"))
        self._acc_svcs.setMaximumHeight(56)
        self._acc_svcs.setTabChangesFocus(True)
        self._acc_svcs.textChanged.connect(self._on_any)
        acc_f.addRow("desc", self._acc_desc)
        acc_f.addRow("", self._acc_lineage)
        acc_f.addRow("services", self._acc_svcs)
        root.addWidget(acc)

        hint = QLabel(t("runtime_modules → 页 2"))
        hint.setStyleSheet("color:#888; font-size:10px;")
        root.addWidget(hint)
        root.addStretch(1)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

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

        selected_b = set(req.get("bindings") or [])
        for name, cb in self._binding_boxes.items():
            cb.setChecked(name in selected_b)

        obs = req.get("observability") or {}
        if not isinstance(obs, dict):
            obs = {}
        live = obs.get("live_tap") if isinstance(obs.get("live_tap"), dict) else {}
        self._live_en.setChecked(bool(live.get("enabled")))
        mode = str(live.get("mode") or "explicit").strip() or "explicit"
        midx = self._live_mode.findData(mode)
        if midx < 0:
            midx = self._live_mode.findData("explicit")
        self._live_mode.setCurrentIndex(max(0, midx))
        self._live_svcs.setPlainText(_list_to_lines(live.get("services")))
        rec = obs.get("record")
        if isinstance(rec, dict):
            self._record_mode.setCurrentText(str(rec.get("mode") or "minimal"))
            self._record_svcs.setPlainText(_list_to_lines(rec.get("services")))
        else:
            self._record_mode.setCurrentText(str(rec or "minimal"))
            self._record_svcs.clear()
        self._trace.setCurrentText(str(obs.get("trace_export") or "on"))

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

    def _set_profile(self, value: str) -> None:
        idx = self._profile.findData(value)
        if idx < 0:
            self._profile.blockSignals(True)
            self._profile.addItem(f"{value}{t('（未识别）')}", value)
            self._profile.blockSignals(False)
            idx = self._profile.findData(value)
        self._profile.setCurrentIndex(max(0, idx))

    def _set_topology(self, value: str) -> None:
        idx = self._topology.findData(value)
        if idx < 0:
            self._topology.blockSignals(True)
            self._topology.addItem(f"{value}{t('（未识别）')}", value)
            self._topology.blockSignals(False)
            idx = self._topology.findData(value)
        self._topology.setCurrentIndex(max(0, idx))

    def _apply_profile_ui(self) -> None:
        release = str(self._profile.currentData() or "") == "production-release"
        live_on = self._live_en.isChecked() and not release
        wiring_all = str(self._live_mode.currentData() or "") == "wiring_all"
        record_off = self._record_mode.currentText().strip() == "off"
        live_svcs = _lines_to_list(self._live_svcs.toPlainText())

        self._live_en.setEnabled(not release)
        self._live_mode.setEnabled(live_on)
        self._live_svcs.setEnabled(live_on and not wiring_all)
        self._record_mode.setEnabled(not release)
        self._record_svcs.setEnabled(not release and not record_off)
        self._trace.setEnabled(not release)

        if release:
            self._obs_hint.setText(
                t(
                    "production-release：live/record/trace 灰调；不编 iox_obs_tap；"
                    "run_sil 不起 Foxglove。bindings 仍保留。"
                )
            )
            self._obs_hint.setStyleSheet("color:#a04000; font-size:10px;")
        elif live_on and wiring_all:
            self._obs_hint.setText(
                t(
                    "wiring_all：天花板=画布 dataflows；将编入 tap（codegen）。"
                    "GMT 可再过滤。"
                )
            )
            self._obs_hint.setStyleSheet("color:#666; font-size:10px;")
        elif live_on and not live_svcs:
            self._obs_hint.setText(
                t("explicit 已开但白名单为空 → Verify 将失败。请填 live svcs。")
            )
            self._obs_hint.setStyleSheet("color:#a04000; font-size:10px;")
        elif live_on:
            self._obs_hint.setText(t("将编入 tap；run_sil 自动接 Foxglove。"))
            self._obs_hint.setStyleSheet("color:#666; font-size:10px;")
        else:
            bits = []
            if not live_on:
                bits.append(t("live 关 → 不编 tap"))
            if record_off:
                bits.append(t("record=off → services 灰调"))
            self._obs_hint.setText(" · ".join(bits) if bits else "")
            self._obs_hint.setStyleSheet("color:#666; font-size:10px;")

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
        # capabilities / apps：无 GUI，保留 YAML 原值（仅清洗自动 tap 条目）
        if "apps" in req:
            req["apps"] = _strip_tap_apps(req.get("apps"))
        # runtime_modules owned by PlatformEditor (tab 2)
        req["bindings"] = [n for n, cb in self._binding_boxes.items() if cb.isChecked()]
        live_on = self._live_en.isChecked() and req["profile"] == "vehicle-debug"
        live_mode = str(self._live_mode.currentData() or "explicit")
        live_block: dict = {
            "enabled": live_on,
            "mode": live_mode,
        }
        if live_mode == "explicit":
            live_block["services"] = _lines_to_list(self._live_svcs.toPlainText())
        req["observability"] = {
            "live_tap": live_block,
            "record": {
                "mode": self._record_mode.currentText().strip() or "minimal",
                "services": _lines_to_list(self._record_svcs.toPlainText()),
            },
            "trace_export": self._trace.currentText().strip() or "on",
        }
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
