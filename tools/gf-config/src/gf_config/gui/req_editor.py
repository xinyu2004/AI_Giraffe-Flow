"""SKU / req.yaml editor — thin ① on tab 1 (runtime_modules live on tab 2)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession
from gf_config.gui.field_ux import (
    COLORS_LIVE_MODE,
    COLORS_ON_OFF,
    COLORS_PROFILE,
    COLORS_RECORD,
    COLORS_TOPOLOGY,
    MultiCheckButton,
    TintedComboBox,
    style_enum_combo,
    tipify,
)
from gf_config.gui import tips as T
from gf_config.i18n import t

# Frozen topologies (DESIGN §6 / heterogeneous-compute)
# (yaml_value, zh_label) — labels go through t()
KNOWN_TOPOLOGIES = [
    ("ap_only", "仅 AP（无 MCU）"),
    ("ap_mcu_cp", "AP + MCU CP"),
]

KNOWN_BINDINGS = ["iceoryx", "someip", "dds", "cross_domain_ipc"]
_BINDING_LABELS = {
    "iceoryx": "iceoryx（本机零拷贝）",
    "someip": "SOME/IP",
    "dds": "DDS",
    "cross_domain_ipc": "跨域 IPC",
}
_BINDING_TIPS = {
    "iceoryx": T.SKU_BIND_ICEORYX,
    "someip": T.SKU_BIND_SOMEIP,
    "dds": T.SKU_BIND_DDS,
    "cross_domain_ipc": T.SKU_BIND_XDOMAIN,
}
KNOWN_PROFILES = [
    ("vehicle-debug", "车辆调试"),
    ("production-release", "量产发布"),
]
_RECORD_MODES = [
    ("minimal", "最小"),
    ("sampled", "抽样"),
    ("full", "全量"),
    ("off", "关闭"),
]
_TRACE_MODES = [
    ("on", "开"),
    ("off", "关"),
]

TAP_APP = "debug_bridge/iox_obs_tap"
INJECT_APP = "debug_bridge/iox_obs_inject"
_AUTO_APPS = frozenset({TAP_APP, INJECT_APP})


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
        self._checkpoint_fn: Callable[..., None] | None = None
        self._end_edit_fn: Callable[[], None] | None = None

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
            f.setHorizontalSpacing(8)
            f.setVerticalSpacing(4)
            f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
            # 标签列按文案占位，避免英文 Live scope / Record services 被挤扁
            f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            f.setLabelAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            return f

        meta = QGroupBox(t("SKU"))
        meta_f = _form()
        meta.setLayout(meta_f)
        self._variant = QLineEdit()
        tipify(self._variant, T.SKU_VARIANT)
        self._variant.textChanged.connect(self._on_any)
        self._variant.editingFinished.connect(self._end_doc_edit)
        self._topology = TintedComboBox()
        tipify(self._topology, T.SKU_TOPOLOGY)
        for value, label in KNOWN_TOPOLOGIES:
            self._topology.addItem(t(label), value)
        style_enum_combo(
            self._topology,
            COLORS_TOPOLOGY,
            data_role=True,
            item_tips=T.SKU_TOPOLOGY_ITEMS,
        )
        self._topology.currentIndexChanged.connect(self._on_any)
        self._product = QLineEdit()
        tipify(self._product, T.SKU_PRODUCT)
        self._product.textChanged.connect(self._on_any)
        self._product.editingFinished.connect(self._end_doc_edit)
        meta_f.addRow(t("变体"), self._variant)
        meta_f.addRow(t("拓扑"), self._topology)
        meta_f.addRow(t("产品"), self._product)
        root.addWidget(meta)

        stage = QGroupBox(t("剖面 / 观测"))
        stage_l = QVBoxLayout(stage)
        stage_l.setContentsMargins(4, 4, 4, 4)
        stage_l.setSpacing(4)
        stage_f = _form()
        self._profile = TintedComboBox()
        tipify(self._profile, T.SKU_PROFILE)
        for value, label in KNOWN_PROFILES:
            self._profile.addItem(t(label), value)
        style_enum_combo(
            self._profile,
            COLORS_PROFILE,
            data_role=True,
            item_tips=T.SKU_PROFILE_ITEMS,
        )
        self._profile.currentIndexChanged.connect(self._on_profile_or_any)
        stage_f.addRow(t("剖面"), self._profile)
        self._live_en = QCheckBox(t("Live 旁路"))
        tipify(self._live_en, T.SKU_LIVE)
        self._live_en.toggled.connect(self._on_profile_or_any)
        self._live_mode = TintedComboBox()
        tipify(self._live_mode, T.SKU_LIVE_MODE)
        self._live_mode.addItem(t("跟随画布（推荐）"), "wiring_all")
        self._live_mode.addItem(t("白名单"), "explicit")
        style_enum_combo(
            self._live_mode,
            COLORS_LIVE_MODE,
            data_role=True,
            item_tips=T.SKU_LIVE_MODE_ITEMS,
        )
        self._live_mode.currentIndexChanged.connect(self._on_profile_or_any)
        self._live_svcs = MultiCheckButton(
            [],
            self._service_candidates,
            tip=T.SKU_LIVE_SVCS,
            empty_label=t("（未选服务）"),
            title=t("选择 Live 服务"),
        )
        self._live_svcs.changed.connect(self._on_profile_or_any)
        self._record_mode = TintedComboBox()
        tipify(self._record_mode, T.SKU_RECORD)
        for value, label in _RECORD_MODES:
            self._record_mode.addItem(t(label), value)
        style_enum_combo(
            self._record_mode,
            COLORS_RECORD,
            data_role=True,
            item_tips=T.SKU_RECORD_ITEMS,
        )
        self._record_mode.currentIndexChanged.connect(self._on_profile_or_any)
        self._record_svcs = MultiCheckButton(
            [],
            self._service_candidates,
            tip=T.SKU_REC_SVCS,
            empty_label=t("（未选服务）"),
            title=t("选择录制服务"),
        )
        self._record_svcs.changed.connect(self._on_any)
        self._trace = TintedComboBox()
        tipify(self._trace, T.SKU_TRACE)
        for value, label in _TRACE_MODES:
            self._trace.addItem(t(label), value)
        style_enum_combo(
            self._trace, COLORS_ON_OFF, data_role=True, item_tips=T.SKU_TRACE_ITEMS
        )
        self._trace.currentIndexChanged.connect(self._on_profile_or_any)
        stage_f.addRow("", self._live_en)
        stage_f.addRow(t("Live 范围"), self._live_mode)
        stage_f.addRow(t("Live 服务"), self._live_svcs)
        stage_f.addRow(t("录制"), self._record_mode)
        stage_f.addRow(t("录制服务"), self._record_svcs)
        stage_f.addRow(t("时序导出"), self._trace)
        stage_l.addLayout(stage_f)
        self._obs_hint = QLabel("")
        self._obs_hint.setWordWrap(True)
        self._obs_hint.setStyleSheet("color:#666; font-size:10px;")
        stage_l.addWidget(self._obs_hint)
        root.addWidget(stage)

        binds = QGroupBox(t("通信绑定"))
        binds_l = QVBoxLayout(binds)
        binds_l.setContentsMargins(4, 4, 4, 4)
        binds_l.setSpacing(2)
        bind_grid = QVBoxLayout()
        bind_grid.setSpacing(2)
        row = QHBoxLayout()
        for i, name in enumerate(KNOWN_BINDINGS):
            cb = QCheckBox(t(_BINDING_LABELS.get(name, name)))
            cb.setStyleSheet("font-size:11px;")
            tipify(cb, _BINDING_TIPS.get(name, name))
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

        acc = QGroupBox(t("验收"))
        acc_f = _form()
        acc.setLayout(acc_f)
        self._acc_desc = QLineEdit()
        tipify(self._acc_desc, T.SKU_ACC_DESC)
        self._acc_desc.textChanged.connect(self._on_any)
        self._acc_desc.editingFinished.connect(self._end_doc_edit)
        self._acc_lineage = QCheckBox(t("强制 lineage 门禁"))
        tipify(self._acc_lineage, T.SKU_ACC_LINEAGE)
        self._acc_lineage.toggled.connect(self._on_any)
        self._acc_svcs = MultiCheckButton(
            [],
            self._service_candidates,
            tip=T.SKU_ACC_SVCS,
            empty_label=t("（未选服务）"),
            title=t("选择验收服务"),
        )
        self._acc_svcs.changed.connect(self._on_any)
        acc_f.addRow(t("说明"), self._acc_desc)
        acc_f.addRow("", self._acc_lineage)
        acc_f.addRow(t("服务"), self._acc_svcs)
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

    def _service_candidates(self) -> list[str]:
        if not self._session:
            return []
        return self._session.wiring_service_names()

    def set_history_hooks(
        self,
        checkpoint: Callable[..., None] | None,
        end_edit: Callable[[], None] | None = None,
    ) -> None:
        self._checkpoint_fn = checkpoint
        self._end_edit_fn = end_edit

    def _checkpoint(self, *, coalesce: bool = False) -> None:
        if self._checkpoint_fn is not None:
            self._checkpoint_fn(coalesce=coalesce)

    def _end_doc_edit(self) -> None:
        if self._end_edit_fn is not None:
            self._end_edit_fn()

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
        self._live_svcs.set_selected([str(x) for x in (live.get("services") or [])])
        rec = obs.get("record")
        if isinstance(rec, dict):
            self._set_combo_data(self._record_mode, str(rec.get("mode") or "minimal"))
            self._record_svcs.set_selected([str(x) for x in (rec.get("services") or [])])
        else:
            self._set_combo_data(self._record_mode, str(rec or "minimal"))
            self._record_svcs.set_selected([])
        self._set_combo_data(self._trace, str(obs.get("trace_export") or "on"))

        acc = req.get("acceptance") or {}
        if isinstance(acc, dict):
            self._acc_desc.setText(str(acc.get("description") or ""))
            self._acc_lineage.setChecked(bool(acc.get("lineage_required")))
            self._acc_svcs.set_selected(
                [str(x) for x in (acc.get("required_services") or [])]
            )
        else:
            self._acc_desc.clear()
            self._acc_lineage.setChecked(False)
            self._acc_svcs.set_selected([])

        self._loading = False
        self._apply_profile_ui()

    def _set_combo_data(self, cb: QComboBox, value: str) -> None:
        idx = cb.findData(value)
        if idx < 0:
            cb.blockSignals(True)
            cb.addItem(f"{value}{t('（未识别）')}", value)
            cb.blockSignals(False)
            idx = cb.findData(value)
        cb.setCurrentIndex(max(0, idx))

    def _set_profile(self, value: str) -> None:
        self._set_combo_data(self._profile, value)

    def _set_topology(self, value: str) -> None:
        self._set_combo_data(self._topology, value)

    def _apply_profile_ui(self) -> None:
        release = str(self._profile.currentData() or "") == "production-release"
        live_on = self._live_en.isChecked() and not release
        wiring_all = str(self._live_mode.currentData() or "") == "wiring_all"
        record_off = str(self._record_mode.currentData() or "") == "off"
        live_svcs = self._live_svcs.selected()

        self._live_en.setEnabled(not release)
        self._live_mode.setEnabled(live_on)
        self._live_svcs.setEnabled(live_on and not wiring_all)
        self._record_mode.setEnabled(not release)
        self._record_svcs.setEnabled(not release and not record_off)
        self._trace.setEnabled(not release)

        if release:
            self._obs_hint.setText(
                t(
                    "量产发布：Live/录制/时序灰调；不编 iox_obs_tap；"
                    "run_sil 不起 Foxglove。通信绑定仍保留。"
                )
            )
            self._obs_hint.setStyleSheet("color:#a04000; font-size:10px;")
        elif live_on and wiring_all:
            self._obs_hint.setText(
                t(
                    "跟随画布：天花板=页 1 dataflows；将编入 tap（codegen）。"
                    "GMT 可再过滤。"
                )
            )
            self._obs_hint.setStyleSheet("color:#666; font-size:10px;")
        elif live_on and not live_svcs:
            self._obs_hint.setText(
                t("白名单模式已开但未选服务 → Verify 将失败。请选择 Live 服务。")
            )
            self._obs_hint.setStyleSheet("color:#a04000; font-size:10px;")
        elif live_on:
            self._obs_hint.setText(t("将编入 tap；run_sil 自动接 Foxglove。"))
            self._obs_hint.setStyleSheet("color:#666; font-size:10px;")
        else:
            bits = []
            if not live_on:
                bits.append(t("Live 关 → 不编 tap"))
            if record_off:
                bits.append(t("录制关闭 → 录制服务灰调"))
            self._obs_hint.setText(" · ".join(bits) if bits else "")
            self._obs_hint.setStyleSheet("color:#666; font-size:10px;")

    def _on_profile_or_any(self, *_args: object) -> None:
        if not self._loading:
            self._apply_profile_ui()
        self._on_any()

    def _on_any(self, *_args: object) -> None:
        if self._loading or not self._session:
            return
        src = self.sender()
        coalesce = isinstance(src, QLineEdit)
        self._checkpoint(coalesce=coalesce)
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
            live_block["services"] = self._live_svcs.selected()
        req["observability"] = {
            "live_tap": live_block,
            "record": {
                "mode": str(self._record_mode.currentData() or "minimal"),
                "services": self._record_svcs.selected(),
            },
            "trace_export": str(self._trace.currentData() or "on"),
        }
        prev_acc = req.get("acceptance") if isinstance(req.get("acceptance"), dict) else {}
        acceptance: dict = {
            "description": self._acc_desc.text().strip(),
            "lineage_required": self._acc_lineage.isChecked(),
            "required_services": self._acc_svcs.selected(),
        }
        if prev_acc.get("sor_golden"):
            acceptance["sor_golden"] = prev_acc["sor_golden"]
        req["acceptance"] = acceptance
        self._session.dirty_req = True
        self.changed.emit()
        if not coalesce:
            self._end_doc_edit()
