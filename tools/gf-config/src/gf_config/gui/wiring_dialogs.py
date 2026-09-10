"""Wiring canvas dialogs (ports, import, frame_ingest, add node)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gf_codegen.compose.parse_hpp import is_fat_port_name
from gf_config.core import (
    CHANNEL_POLICY_DEFAULTS,
    DEFAULT_CHANNEL_NAMES,
    canon_service,
    default_publish_spec,
    short_service,
)
from gf_config.i18n import t

_TRIGGERS = (
    ("period", "周期"),
    ("on_change", "变化时"),
)


def _fill_trigger_combo(trig: QComboBox, trigger: str) -> None:
    trig.clear()
    for value, label in _TRIGGERS:
        trig.addItem(t(label), value)
    idx = trig.findData(trigger)
    trig.setCurrentIndex(max(0, idx))


def _style_policy_spin(
    spin: QSpinBox, trigger: str, spec: dict[str, Any], *, reset: bool
) -> None:
    if trigger == "period":
        spin.setRange(1, 1000)
        spin.setSuffix(" ms")
        spin.setValue(10 if reset else int(spec.get("period_ms") or 10))
    else:
        spin.setRange(0, 120)
        spin.setSuffix(" fps")
        spin.setValue(0 if reset else int(spec.get("expect_fps") or 0))


def _read_policy_row(trig: QComboBox, spin: QSpinBox) -> dict[str, Any]:
    trigger = str(trig.currentData() or "on_change")
    spec: dict[str, Any] = {"trigger": trigger}
    if trigger == "period":
        spec["period_ms"] = int(spin.value())
    else:
        fps = int(spin.value())
        if fps > 0:
            spec["expect_fps"] = fps
    return spec


class PortEditDialog(QDialog):
    """Double-click block: In/Out ports + per-Out publish trigger (topic policy)."""

    def __init__(
        self,
        process: str,
        provides: list[str],
        requires: list[str],
        candidates: list[str],
        parent: QWidget | None = None,
        *,
        out_policies: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("编辑端口 — {process}").format(process=process))
        self.resize(560, 520)
        self._active_in = True
        self._policies = {
            short_service(k): dict(v)
            for k, v in (out_policies or {}).items()
            if isinstance(v, dict)
        }

        self._requires = QListWidget()
        for r in requires:
            self._requires.addItem(canon_service(r))
        self._requires.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._requires.itemSelectionChanged.connect(self._on_in_selected)
        self._requires.itemClicked.connect(lambda *_: self._focus_in())

        self._outs = QTableWidget(0, 3)
        self._outs.setHorizontalHeaderLabels(
            [t("Out（服务）"), t("触发"), t("ms / fps")]
        )
        self._outs.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._outs.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._outs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._outs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._outs.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._outs.itemSelectionChanged.connect(self._on_out_selected)
        for p in provides:
            self._append_out_row(canon_service(p))

        self._svc = QComboBox()
        self._svc.setEditable(True)
        for c in candidates:
            self._svc.addItem(canon_service(c) if not c.startswith("services.") else c)
        if not candidates:
            self._svc.addItem("services.semantic.")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("In（requires）")))
        layout.addWidget(self._requires)
        layout.addWidget(
            QLabel(t("Out（provides）— 触发写在发布话题上（多订阅共享一份）"))
        )
        layout.addWidget(self._outs)

        row = QHBoxLayout()
        row.addWidget(QLabel(t("service")))
        row.addWidget(self._svc, stretch=1)
        btn_out = QPushButton(t("＋ Out"))
        btn_in = QPushButton(t("＋ In"))
        btn_del = QPushButton(t("删除选中"))
        btn_swap = QPushButton(t("切换方向"))
        btn_out.clicked.connect(lambda: self._add("out"))
        btn_in.clicked.connect(lambda: self._add("in"))
        btn_del.clicked.connect(self._delete_selected)
        btn_swap.clicked.connect(self._swap_direction)
        row.addWidget(btn_in)
        row.addWidget(btn_out)
        row.addWidget(btn_del)
        row.addWidget(btn_swap)
        layout.addLayout(row)

        hint = QLabel(
            t(
                "一发多收：多模块 In 同名正常（DDS/SOME/IP 多订阅）。"
                "透传时可两模块 Out 同名；publish_policy 按短名一份，属发布话题而非边。"
                "\n手输短名 → services.semantic.*；In/Out 同模块可同名（gateway）。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:11px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _focus_in(self) -> None:
        self._active_in = True
        self._outs.clearSelection()

    def _on_in_selected(self) -> None:
        if self._requires.selectedItems():
            self._active_in = True
            self._outs.blockSignals(True)
            self._outs.clearSelection()
            self._outs.blockSignals(False)

    def _on_out_selected(self) -> None:
        if self._outs.selectionModel() and self._outs.selectionModel().hasSelection():
            self._active_in = False
            self._requires.blockSignals(True)
            self._requires.clearSelection()
            self._requires.blockSignals(False)

    def _spec_for(self, svc: str) -> dict[str, Any]:
        short = short_service(svc)
        return dict(self._policies.get(short) or default_publish_spec())

    def _append_out_row(self, svc: str) -> None:
        row = self._outs.rowCount()
        self._outs.insertRow(row)
        item = QTableWidgetItem(svc)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._outs.setItem(row, 0, item)
        trig = QComboBox()
        spec = self._spec_for(svc)
        trigger = str(spec.get("trigger") or "on_change")
        _fill_trigger_combo(trig, trigger)
        spin = QSpinBox()
        _style_policy_spin(spin, trigger, spec, reset=False)
        trig.currentIndexChanged.connect(lambda _i, r=row: self._on_trig_changed(r))
        self._outs.setCellWidget(row, 1, trig)
        self._outs.setCellWidget(row, 2, spin)

    def _on_trig_changed(self, row: int) -> None:
        trig = self._outs.cellWidget(row, 1)
        spin = self._outs.cellWidget(row, 2)
        if not isinstance(trig, QComboBox) or not isinstance(spin, QSpinBox):
            return
        trigger = str(trig.currentData() or "on_change")
        spin.blockSignals(True)
        _style_policy_spin(spin, trigger, {}, reset=True)
        spin.blockSignals(False)

    def _out_svc_at(self, row: int) -> str:
        item = self._outs.item(row, 0)
        return canon_service(item.text() if item else "")

    def _add(self, direction: str) -> None:
        text = self._svc.currentText().strip()
        if not text:
            return
        svc = canon_service(text)
        if direction == "in":
            existing = {
                short_service(self._requires.item(i).text())
                for i in range(self._requires.count())
            }
            if short_service(svc) in existing:
                return
            self._requires.addItem(svc)
            self._requires.setCurrentRow(self._requires.count() - 1)
            self._on_in_selected()
            return
        existing = {
            short_service(self._out_svc_at(i)) for i in range(self._outs.rowCount())
        }
        if short_service(svc) in existing:
            return
        self._policies.setdefault(short_service(svc), default_publish_spec())
        self._append_out_row(svc)
        self._outs.selectRow(self._outs.rowCount() - 1)
        self._on_out_selected()

    def _delete_selected(self) -> None:
        if not self._active_in and self._outs.currentRow() >= 0:
            row = self._outs.currentRow()
            short = short_service(self._out_svc_at(row))
            self._outs.removeRow(row)
            self._policies.pop(short, None)
            return
        row = self._requires.currentRow()
        if row >= 0:
            self._requires.takeItem(row)

    def _swap_direction(self) -> None:
        if not self._active_in and self._outs.currentRow() >= 0:
            row = self._outs.currentRow()
            svc = self._out_svc_at(row)
            short = short_service(svc)
            self._outs.removeRow(row)
            self._policies.pop(short, None)
            self._requires.addItem(svc)
            self._requires.setCurrentRow(self._requires.count() - 1)
            self._on_in_selected()
            return
        row = self._requires.currentRow()
        if row < 0:
            return
        item = self._requires.takeItem(row)
        if item is None:
            return
        svc = item.text()
        self._policies.setdefault(short_service(svc), default_publish_spec())
        self._append_out_row(svc)
        self._outs.selectRow(self._outs.rowCount() - 1)
        self._on_out_selected()

    def result_ports(self) -> tuple[list[str], list[str]]:
        provides = [self._out_svc_at(i) for i in range(self._outs.rowCount())]
        requires = [self._requires.item(i).text() for i in range(self._requires.count())]
        return provides, requires

    def result_out_policies(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for i in range(self._outs.rowCount()):
            svc = self._out_svc_at(i)
            short = short_service(svc)
            if not short:
                continue
            trig_w = self._outs.cellWidget(i, 1)
            spin_w = self._outs.cellWidget(i, 2)
            if isinstance(trig_w, QComboBox) and isinstance(spin_w, QSpinBox):
                out[short] = _read_policy_row(trig_w, spin_w)
            else:
                out[short] = default_publish_spec()
        return out


class ImportPortsDialog(QDialog):
    """Shared dialog: pick candidates from hpp or fidl → module ports."""

    def __init__(
        self,
        candidates: list[str],
        processes: list[str],
        default_process: str,
        parent: QWidget | None = None,
        *,
        title: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or t("添加端口"))
        self.resize(460, 480)
        self._all = list(candidates)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(hint or t("勾选要加入的名称（作为 service 短名）：")))

        self._fat_only = QCheckBox(t("仅粗端口 / 整包对接（推荐，隐藏 Item 碎片）"))
        self._fat_only.setChecked(len(candidates) > 6)
        self._fat_only.toggled.connect(self._rebuild_checks)
        layout.addWidget(self._fat_only)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._checks_host = QWidget()
        self._checks_layout = QVBoxLayout(self._checks_host)
        self._scroll.setWidget(self._checks_host)
        layout.addWidget(self._scroll, stretch=1)
        self._checks: list[QCheckBox] = []
        self._rebuild_checks()

        form = QFormLayout()
        self._proc = QComboBox()
        self._proc.addItems(processes)
        if default_process in processes:
            self._proc.setCurrentText(default_process)
        form.addRow(t("目标模块"), self._proc)

        self._dir_out = QRadioButton(t("Out（provides）"))
        self._dir_in = QRadioButton(t("In（requires）"))
        self._dir_in.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._dir_out)
        bg.addButton(self._dir_in)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_in)
        dir_row.addWidget(self._dir_out)
        form.addRow(t("方向"), dir_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _rebuild_checks(self) -> None:
        while self._checks_layout.count():
            item = self._checks_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._checks.clear()
        names = self._all
        if self._fat_only.isChecked():
            fat = [n for n in self._all if is_fat_port_name(n)]
            if fat:
                names = fat
        for name in names:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._checks.append(cb)
            self._checks_layout.addWidget(cb)
        self._checks_layout.addStretch(1)

    def selected(self) -> tuple[str, list[str], str]:
        names = [cb.text() for cb in self._checks if cb.isChecked()]
        direction = "out" if self._dir_out.isChecked() else "in"
        return self._proc.currentText(), names, direction


class FrameIngestDialog(QDialog):
    """Configure host.frame_ingest lanes + channel publish_policy."""

    def __init__(
        self,
        fi: dict[str, Any],
        slots: list[dict[str, Any]],
        *,
        parent: QWidget | None = None,
        channel_policies: dict[str, dict[str, Any]] | None = None,
        channel_names: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("frame_ingest · 视频契约"))
        self.setMinimumWidth(520)
        self._rows: list[dict[str, Any]] = []
        root = QVBoxLayout(self)
        hint = QLabel(
            t(
                "每路 = 一个 Out（gf.channel.{id}）→ 拖到消费方。\n"
                "SOP 默认帧源=isp；SIL 用 GF_FRAME_SOURCE=carla|replay|colorbar|none（run_sil）。\n"
                "无外参/内参/ego；buffers=AB 固定 2。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:11px;")
        root.addWidget(hint)

        root.addWidget(QLabel(t("相机路（每路一条 GfChannel Out）")))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        root.addWidget(self._list)
        form = QFormLayout()
        self._id = QLineEdit()
        self._w = QSpinBox()
        self._w.setRange(16, 8192)
        self._h = QSpinBox()
        self._h.setRange(16, 8192)
        self._pixel = QComboBox()
        self._pixel.setEditable(True)
        for p in ("nv12", "nv21", "yuv422", "yuv444", "rgb8"):
            self._pixel.addItem(p, p)
        self._fps = QSpinBox()
        self._fps.setRange(0, 240)
        self._fps.setSuffix(" fps")
        self._fps.setToolTip(t("相机物理帧率。0=未填。Out expect_fps 须 ≤ 此值。"))
        self._slot_ro = QLabel("")
        self._slot_ro.setStyleSheet("color:#5dade2;")
        form.addRow("id", self._id)
        form.addRow(t("槽名"), self._slot_ro)
        form.addRow(t("宽"), self._w)
        form.addRow(t("高"), self._h)
        form.addRow("pixel_format", self._pixel)
        form.addRow("fps", self._fps)
        root.addLayout(form)
        row_btns = QHBoxLayout()
        btn_add = QPushButton(t("添加一路"))
        btn_del = QPushButton(t("删除当前路"))
        btn_add.clicked.connect(self._add_row)
        btn_del.clicked.connect(self._del_row)
        row_btns.addWidget(btn_add)
        row_btns.addWidget(btn_del)
        row_btns.addStretch(1)
        root.addLayout(row_btns)
        self._id.textChanged.connect(self._sync_slot_label)
        self._id.editingFinished.connect(self._apply_form_to_row)
        self._w.valueChanged.connect(lambda _v: self._apply_form_to_row())
        self._h.valueChanged.connect(lambda _v: self._apply_form_to_row())
        self._pixel.currentTextChanged.connect(lambda _t: self._apply_form_to_row())
        self._fps.valueChanged.connect(lambda _v: self._apply_form_to_row())

        root.addWidget(QLabel(t("通道发布策略")))
        self._ch_table = QTableWidget(0, 4)
        self._ch_table.setHorizontalHeaderLabels(
            [t("通道"), t("槽名"), t("触发"), t("ms / fps")]
        )
        self._ch_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._ch_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._ch_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._ch_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._ch_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._ch_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        root.addWidget(self._ch_table)
        self._fi_channels: dict[str, str] = {}
        ch_map = fi.get("channels") if isinstance(fi.get("channels"), dict) else {}
        for k, v in ch_map.items():
            n = str(k).strip()
            if n:
                self._fi_channels[n] = str(v).strip() or f"gf.channel.{n}"
        authored = {
            str(k): dict(v)
            for k, v in (channel_policies or {}).items()
            if isinstance(v, dict)
        }
        names: list[str] = []
        seen: set[str] = set()
        for n in channel_names or []:
            n = str(n).strip()
            if n and n not in seen:
                seen.add(n)
                names.append(n)
        for n in self._fi_channels:
            if n not in seen:
                seen.add(n)
                names.append(n)
        for k in authored:
            if k not in seen:
                seen.add(k)
                names.append(k)
        if not names:
            names = list(DEFAULT_CHANNEL_NAMES)
            for n in names:
                self._fi_channels.setdefault(n, f"gf.channel.{n}")
        for name in names:
            default = CHANNEL_POLICY_DEFAULTS.get(name) or default_publish_spec()
            spec = authored.get(name) or default
            slot = self._fi_channels.get(name) or f"gf.channel.{name}"
            self._append_channel_row(name, slot, spec)
        ch_btns = QHBoxLayout()
        btn_ch_add = QPushButton(t("添加通道"))
        btn_ch_del = QPushButton(t("删除选中通道"))
        btn_ch_add.clicked.connect(self._add_channel_row)
        btn_ch_del.clicked.connect(self._del_channel_row)
        ch_btns.addWidget(btn_ch_add)
        ch_btns.addWidget(btn_ch_del)
        ch_btns.addStretch(1)
        root.addLayout(ch_btns)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._loading = False
        self._load(fi, slots)

    def _append_channel_row(self, name: str, slot: str, spec: dict[str, Any]) -> None:
        row = self._ch_table.rowCount()
        self._ch_table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._ch_table.setItem(row, 0, name_item)
        slot_item = QTableWidgetItem(slot or f"gf.channel.{name}")
        slot_item.setFlags(slot_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._ch_table.setItem(row, 1, slot_item)
        trig = QComboBox()
        trigger = str(spec.get("trigger") or "on_change")
        _fill_trigger_combo(trig, trigger)
        spin = QSpinBox()
        _style_policy_spin(spin, trigger, spec, reset=False)
        trig.currentIndexChanged.connect(
            lambda _i, r=row: self._on_ch_trig_changed(r)
        )
        self._ch_table.setCellWidget(row, 2, trig)
        self._ch_table.setCellWidget(row, 3, spin)

    def _channel_names_used(self) -> set[str]:
        used: set[str] = set()
        for i in range(self._ch_table.rowCount()):
            item = self._ch_table.item(i, 0)
            n = (item.text() if item else "").strip()
            if n:
                used.add(n)
        return used

    def _add_channel_row(self) -> None:
        used = self._channel_names_used()
        n = 1
        name = "channel_1"
        while name in used:
            n += 1
            name = f"channel_{n}"
        slot = f"gf.channel.{name}"
        self._fi_channels.setdefault(name, slot)
        self._append_channel_row(name, slot, default_publish_spec())
        self._ch_table.selectRow(self._ch_table.rowCount() - 1)

    def _del_channel_row(self) -> None:
        row = self._ch_table.currentRow()
        if row < 0:
            QMessageBox.information(self, t("通道"), t("请先选中一行通道。"))
            return
        item = self._ch_table.item(row, 0)
        name = (item.text() if item else "").strip()
        self._ch_table.removeRow(row)
        if name:
            self._fi_channels.pop(name, None)

    def _on_ch_trig_changed(self, row: int) -> None:
        trig = self._ch_table.cellWidget(row, 2)
        spin = self._ch_table.cellWidget(row, 3)
        if not isinstance(trig, QComboBox) or not isinstance(spin, QSpinBox):
            return
        trigger = str(trig.currentData() or "on_change")
        spin.blockSignals(True)
        _style_policy_spin(spin, trigger, {}, reset=True)
        spin.blockSignals(False)

    @staticmethod
    def _set_combo(cb: QComboBox, value: str) -> None:
        idx = cb.findData(value)
        if idx < 0:
            idx = cb.findText(value)
        if idx >= 0:
            cb.setCurrentIndex(idx)
        elif cb.isEditable():
            cb.setEditText(value)

    def _default_slot(self, sid: str = "front") -> dict[str, Any]:
        return {"id": sid, "w": 640, "h": 480, "pixel_format": "nv12", "fps": 30}

    def _load(self, fi: dict[str, Any], slots: list[dict[str, Any]]) -> None:
        default_pix = str(fi.get("pixel_format") or "nv12")
        self._rows = []
        for s in slots:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id") or "").strip()
            if not sid:
                continue
            self._rows.append(
                {
                    "id": sid,
                    "w": int(s.get("w") or fi.get("frame_w") or 640),
                    "h": int(s.get("h") or fi.get("frame_h") or 480),
                    "pixel_format": str(s.get("pixel_format") or default_pix),
                    "fps": int(s.get("fps") or 0),
                }
            )
        if not self._rows:
            self._rows.append(self._default_slot("front"))
        self._refresh_list()
        self._list.setCurrentRow(0)

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for r in self._rows:
            sid = str(r.get("id") or "?")
            pix = str(r.get("pixel_format") or "nv12")
            fps = int(r.get("fps") or 0)
            extra = f"  {fps}fps" if fps > 0 else ""
            self._list.addItem(f"{sid}  →  gf.channel.{sid}  ({pix}{extra})")
        self._list.blockSignals(False)

    def _on_row(self, row: int) -> None:
        if row < 0 or row >= len(self._rows):
            return
        self._loading = True
        try:
            r = self._rows[row]
            self._id.setText(str(r.get("id") or ""))
            self._w.setValue(int(r.get("w") or 640))
            self._h.setValue(int(r.get("h") or 480))
            self._set_combo(self._pixel, str(r.get("pixel_format") or "nv12"))
            self._fps.setValue(int(r.get("fps") or 0))
            self._sync_slot_label()
        finally:
            self._loading = False

    def _sync_slot_label(self) -> None:
        sid = self._id.text().strip() or "?"
        self._slot_ro.setText(f"gf.channel.{sid}")

    def _apply_form_to_row(self) -> None:
        if self._loading:
            return
        row = self._list.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        sid = self._id.text().strip() or f"cam{row + 1}"
        pix = str(self._pixel.currentData() or self._pixel.currentText() or "nv12")
        self._rows[row] = {
            "id": sid,
            "w": int(self._w.value()),
            "h": int(self._h.value()),
            "pixel_format": pix,
            "fps": int(self._fps.value()),
        }
        item = self._list.item(row)
        if item is not None:
            fps = int(self._fps.value())
            extra = f"  {fps}fps" if fps > 0 else ""
            item.setText(f"{sid}  →  gf.channel.{sid}  ({pix}{extra})")

    def _add_row(self) -> None:
        self._apply_form_to_row()
        used = {str(r.get("id")) for r in self._rows}
        n = 1
        sid = "front"
        while sid in used:
            n += 1
            sid = f"cam{n}"
        self._rows.append(self._default_slot(sid))
        self._refresh_list()
        self._list.setCurrentRow(len(self._rows) - 1)

    def _del_row(self) -> None:
        row = self._list.currentRow()
        if row < 0 or len(self._rows) <= 1:
            QMessageBox.information(self, t("通道"), t("至少保留一路。"))
            return
        del self._rows[row]
        self._refresh_list()
        self._list.setCurrentRow(min(row, len(self._rows) - 1))

    def _on_accept(self) -> None:
        self._apply_form_to_row()
        ids = [str(r.get("id") or "").strip() for r in self._rows]
        if not all(ids) or len(ids) != len(set(ids)):
            QMessageBox.warning(self, t("通道"), t("每路 id 必填且唯一。"))
            return
        ch_names: list[str] = []
        new_map: dict[str, str] = {}
        for i in range(self._ch_table.rowCount()):
            name_item = self._ch_table.item(i, 0)
            slot_item = self._ch_table.item(i, 1)
            n = (name_item.text() if name_item else "").strip()
            if not n:
                QMessageBox.warning(self, t("通道"), t("通道名必填。"))
                return
            slot = (slot_item.text() if slot_item else "").strip() or f"gf.channel.{n}"
            if not slot.startswith("gf.channel."):
                slot = f"gf.channel.{slot}" if not slot.startswith("gf.") else slot
            ch_names.append(n)
            new_map[n] = slot
        if len(ch_names) != len(set(ch_names)):
            QMessageBox.warning(self, t("通道"), t("通道名必须唯一。"))
            return
        self._fi_channels = new_map
        self.accept()

    def result_config(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Freeze SOP default isp; SIL overrides via GF_FRAME_SOURCE."""
        slots = []
        for r in self._rows:
            slots.append(
                {
                    "id": str(r.get("id")),
                    "w": int(r.get("w") or 640),
                    "h": int(r.get("h") or 480),
                    "pixel_format": str(r.get("pixel_format") or "nv12"),
                    "fps": int(r.get("fps") or 0),
                }
            )
        fields: dict[str, Any] = {
            "active_source": "isp",
            "frame_source": "none",
            "bridge": {"enabled": True},
            "channels": dict(self._fi_channels),
        }
        if slots:
            fields["frame_w"] = int(slots[0]["w"])
            fields["frame_h"] = int(slots[0]["h"])
            fields["pixel_format"] = str(slots[0].get("pixel_format") or "nv12")
        return fields, slots

    def result_channel_policies(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for i in range(self._ch_table.rowCount()):
            item = self._ch_table.item(i, 0)
            name = (item.text() if item else "").strip()
            if not name:
                continue
            trig = self._ch_table.cellWidget(i, 2)
            spin = self._ch_table.cellWidget(i, 3)
            if isinstance(trig, QComboBox) and isinstance(spin, QSpinBox):
                out[name] = _read_policy_row(trig, spin)
            else:
                out[name] = default_publish_spec()
        return out


class AddNodeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("添加模块"))
        form = QFormLayout(self)
        self._name = QLineEdit("sensing.new_app")
        self._domain = QComboBox()
        self._domain.setEditable(False)
        self._domain.addItem(t("ap_linux — AP Linux（默认）"), "ap_linux")
        self._domain.addItem(t("host — 桌面 / 仿真 PC"), "host")
        self._domain.setCurrentIndex(0)
        self._domain.setToolTip(
            t(
                "compute_domain：进程运行位置。\n"
                "写入 wiring.yaml → Verify → gf.sor.json deployments[]。"
            )
        )
        hint = QLabel(
            t(
                "compute_domain 是 wiring 字段（进 SOR）。\n"
                "外部 MCU：空白画布右键 → 添加外部 MCU。\n"
                "视频契约：空白处右键 → 添加 frame_ingest（不进 deployments）。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:11px;")
        form.addRow(t("进程名"), self._name)
        form.addRow(t("计算域"), self._domain)
        form.addRow(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[str, str]:
        name = self._name.text().strip()
        data = self._domain.currentData()
        domain = str(data) if data else "ap_linux"
        return name, domain or "ap_linux"
