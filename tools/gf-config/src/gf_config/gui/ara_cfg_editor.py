"""页 2 · ARA 运行时（gf_ara_cfg）— runtime_modules + cfg/gf_ara_cfg/{exec,em_launch,…}.yaml."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from gf_codegen.compose.mem_budget import (
    estimate_mem_budget,
    fmt_bytes,
    mem_section_gates,
)
from gf_codegen.compose.emit_em_launch import (
    HOST_DLT,
    HOST_FRAME_INGEST,
    HOST_ROUDI,
    gated_host_processes,
)

from gf_config.core import ProjectSession
from gf_config.validate import ALWAYS_ON_MODULES
from gf_config.gui.editor_history import HistoryHooksMixin
from gf_config.gui.ara_pages import AraPagesMixin
from gf_config.gui.ara_tables import AraTablesMixin
from gf_config.gui.ara_load import AraLoadMixin
from gf_config.gui.ara_commit import AraCommitMixin
from gf_config.gui.field_ux import (
    COLORS_DID_ACCESS,
    COLORS_LOG_LEVEL,
    set_spin_baseline,
    tipify,
)
from gf_config.gui import tips as T
from gf_config.i18n import t

from gf_config.gui.ara_constants import (
    KNOWN_MODULES,
    MODULE_DEP_HINTS,
    MODULE_DEPS,
    _DEFAULT_ALIVE_PERIOD_MS,
    _DEFAULT_ALIVE_TIMEOUT_MS,
    _DEFAULT_DEADLINE_MS,
    _DEFAULT_EM_ARGS,
    _DEFAULT_MAX_RESTARTS,
    _DID_ACCESS,
    _LOG_LEVELS,
    _MODULE_COLS,
    _NAV,
)
from gf_config.gui.ara_widgets import (
    _CurrentPageStack,
    _set_cell,
    _set_combo,
)

class AraCfgEditor(
    HistoryHooksMixin,
    AraPagesMixin,
    AraTablesMixin,
    AraLoadMixin,
    AraCommitMixin,
    QWidget,
):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_history_hooks()
        self._session: ProjectSession | None = None
        self._loading = False
        self._modules: set[str] = set()
        self._module_boxes: dict[str, QCheckBox] = {}
        self._pages: dict[str, QWidget] = {}
        self._src_boxes: dict[str, QCheckBox] = {}
        # Explicit only — do not auto-read reports/iox_shm_report.json on open.
        self._iox_shm_report_path: Path | None = None

        root = QVBoxLayout(self)

        mods = QGroupBox(
            t("runtime_modules（编进镜像 · 勾选后下方出现对应清单）")
        )
        mods_l = QVBoxLayout(mods)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        for i, name in enumerate(KNOWN_MODULES):
            cb = QCheckBox(name)
            tipify(cb, T.MODULE.get(name, name))
            if name in ALWAYS_ON_MODULES:
                cb.setChecked(True)
                cb.setEnabled(False)
                cb.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            else:
                cb.toggled.connect(self._on_modules_toggled)
            self._module_boxes[name] = cb
            grid.addWidget(cb, i // _MODULE_COLS, i % _MODULE_COLS)
        mods_l.addLayout(grid)
        mods_note = QLabel(
            t(
                "必选 core / com / osal 灰显不可关（CMake always-on）。"
                "勾选 collector/ucm/phm/diag/exec 会自动带上依赖模块并提示原因。"
            )
        )
        mods_note.setStyleSheet("color:#666; font-size:11px;")
        mods_l.addWidget(mods_note)
        self._mod_dep_hint = QLabel("")
        self._mod_dep_hint.setWordWrap(True)
        self._mod_dep_hint.setStyleSheet("color:#0d47a1; font-size:11px;")
        self._mod_dep_hint.hide()
        mods_l.addWidget(self._mod_dep_hint)
        root.addWidget(mods)

        body = QHBoxLayout()
        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        body.addWidget(self._nav)

        right = QVBoxLayout()
        self._empty = QLabel(
            t(
                "尚未勾选可选平台模块（exec / phm / diag / log / ucm / sm / collector …）。\n"
                "core / com / osal 常开；勾选后对应清单出现在左侧（有界内存因 com 常显）。"
            )
        )
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._empty.setStyleSheet("color:#666; padding:12px;")
        right.addWidget(self._empty)

        # Only the visible page should dictate min height (Qt default = max of all pages).
        self._stack = _CurrentPageStack()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right.addWidget(self._stack, stretch=1)
        body.addLayout(right, stretch=1)
        root.addLayout(body, stretch=1)

        self._pages["exec"] = self._build_exec_page()
        self._pages["em_launch"] = self._build_em_launch_page()
        self._pages["phm"] = self._build_phm_page()
        self._pages["diag"] = self._build_diag_page()
        self._pages["log"] = self._build_log_page()
        self._pages["ucm"] = self._build_ucm_page()
        self._pages["collector"] = self._build_collector_page()
        self._pages["bounds"] = self._build_bounds_page()
        for key, _title, _mods in _NAV:
            self._stack.addWidget(self._pages[key])

        self._wire_coalesce_end_edit()
        self._nav.currentItemChanged.connect(self._on_nav_item)
        self._rebuild_nav()

    # ── pages ─────────────────────────────────────────────

    # ── session / history ─────────────────────────────────

    def _coalesce_sender(self) -> bool:
        return isinstance(self.sender(), (QLineEdit, QSpinBox))

    def _wire_coalesce_end_edit(self) -> None:
        for w in (
            self._doip_addr,
            self._doip_tester,
            self._doip_port,
            self._s3_ms,
            self._tp_ms,
            self._p2_ms,
            self._p2star_ms,
            self._sec_delay_ms,
            self._ota_block,
            self._ucm_source,
            self._col_max,
            self._col_deb_keys,
            self._col_store_max,
            self._log_file_max,
            self._bnd_dlt_ctx,
            self._bnd_com_depth,
            self._bnd_com_keys,
            self._bnd_com_avg,
            self._bnd_per_keys,
            self._bnd_per_val,
            self._bnd_rx,
            self._bnd_did_n,
            self._bnd_did_pay,
            self._bnd_bud_ram,
            self._bnd_bud_disk,
            self._iox_pub,
            self._iox_sub,
            self._iox_sub_per_pub,
            self._iox_hist,
            self._iox_chunk_pub,
            self._iox_chunk_sub,
            self._iox_iface,
            self._iox_bud_shm,
        ):
            w.editingFinished.connect(self._end_doc_edit)

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        self._iox_shm_report_path = None  # never auto-load report on open
        if session is None:
            return
        self._loading = True
        # UI may force-show always-on checkboxes; never rewrite req on open.
        selected = set(str(x) for x in (session.req.get("runtime_modules") or []))
        for name, cb in self._module_boxes.items():
            if name in ALWAYS_ON_MODULES:
                cb.setChecked(True)
            else:
                cb.setChecked(name in selected)
        self._modules = set(selected) | ALWAYS_ON_MODULES
        # Soft deps only on user toggle — never rewrite membership on open.
        self._load_exec(session.get_ara_doc("exec"))
        self._load_em_launch(session.get_ara_doc("em_launch"))
        self._load_phm(session.get_ara_doc("phm"))
        self._load_diag(session.get_ara_doc("diag"))
        self._load_log(session.get_ara_doc("log"))
        self._load_ucm(session.get_ara_doc("ucm"))
        self._load_collector(session.get_ara_doc("collector"))
        self._load_bounds(session.get_ara_doc("bounds"))
        self._loading = False
        self.sync_capability_hosts()
        self._refresh_bounds_gates()
        self.rebaseline_spins()
        self._rebuild_nav()
        self._refresh_mem_estimate()

    def selected_modules(self) -> list[str]:
        # Preserve KNOWN_MODULES order; always-on forced in.
        out: list[str] = []
        for n in KNOWN_MODULES:
            cb = self._module_boxes[n]
            if n in ALWAYS_ON_MODULES or cb.isChecked():
                out.append(n)
        return out

    def _dependents_of(self, dep: str) -> list[str]:
        return [m for m, deps in MODULE_DEPS.items() if dep in deps]

    def _apply_module_deps(self, newly_checked: str | None) -> list[str]:
        """Auto-check soft deps; return human hints for status line."""
        hints: list[str] = []
        changed = True
        while changed:
            changed = False
            for name, cb in self._module_boxes.items():
                if name in ALWAYS_ON_MODULES or not cb.isChecked():
                    continue
                for dep in MODULE_DEPS.get(name, ()):
                    dcb = self._module_boxes.get(dep)
                    if dcb is None or dcb.isChecked():
                        continue
                    dcb.blockSignals(True)
                    dcb.setChecked(True)
                    dcb.blockSignals(False)
                    # Compose after t(): tipify(t(full)) would miss formatted keys.
                    dcb.setToolTip(
                        t("因勾选了 {0} 而自动启用：{1}").format(
                            name, t(MODULE_DEP_HINTS.get(name, dep))
                        )
                    )
                    tipify(dcb, "")  # hand cursor only
                    changed = True
                    if newly_checked == name or newly_checked is None:
                        h = MODULE_DEP_HINTS.get(name)
                        if h and h not in hints:
                            hints.append(t(h))
        return hints

    def _on_modules_toggled(self, *_args: object) -> None:
        if self._loading or not self._session:
            return
        src = self.sender()
        name = ""
        for n, cb in self._module_boxes.items():
            if cb is src:
                name = n
                break

        # Turning off a soft dependency while dependents remain → confirm.
        if name and name not in ALWAYS_ON_MODULES:
            cb = self._module_boxes[name]
            if not cb.isChecked():
                deps_users = [
                    u
                    for u in self._dependents_of(name)
                    if self._module_boxes[u].isChecked()
                ]
                if deps_users:
                    reply = QMessageBox.question(
                        self,
                        t("关闭依赖模块"),
                        t(
                            "关闭 {0} 后，仍勾选的 {1} 将降级"
                            "（例如 DTC/版本仅本会话有效，重启丢失）。仍要关闭？"
                        ).format(name, ", ".join(deps_users)),
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        cb.blockSignals(True)
                        cb.setChecked(True)
                        cb.blockSignals(False)
                        return

        self._checkpoint(coalesce=False)
        hints = self._apply_module_deps(name if name and self._module_boxes[name].isChecked() else None)
        if hints:
            self._mod_dep_hint.setText(" · ".join(hints))
            self._mod_dep_hint.show()
        modules = self.selected_modules()
        self._session.set_runtime_modules(modules)
        self._modules = set(modules)
        self._rebuild_nav()
        self._refresh_bounds_gates()
        self._refresh_mem_estimate()
        self.changed.emit()
        self._end_doc_edit()

    def _refresh_bounds_gates(self) -> None:
        """Show/hide bounds sections by runtime_modules + iceoryx binding."""
        if not hasattr(self, "_bnd_grp_log"):
            return
        req: dict[str, Any] = {}
        if self._session and isinstance(self._session.req, dict):
            req = dict(self._session.req)
        req["runtime_modules"] = (
            self.selected_modules() if self._session else sorted(self._modules)
        )
        g = mem_section_gates(req)
        self._bnd_grp_log.setVisible(g["log"])
        self._bnd_grp_com.setVisible(g["com"])
        self._bnd_grp_per.setVisible(g["per"])
        self._bnd_grp_diag.setVisible(g["diag"])
        self._bnd_grp_iox.setVisible(g["iceoryx"])
        if hasattr(self, "_bnd_shm_bar"):
            self._bnd_shm_bar.setVisible(g["iceoryx"])

    def _enabled_nav(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for key, title, unlock in _NAV:
            if self._modules & unlock:
                out.append((key, t(title)))
        return out

    def _rebuild_nav(self) -> None:
        enabled = self._enabled_nav()
        prev_key = None
        cur = self._nav.currentItem()
        if cur is not None:
            prev_key = cur.data(Qt.ItemDataRole.UserRole)

        self._nav.blockSignals(True)
        self._nav.clear()
        for key, title in enabled:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._nav.addItem(item)
        self._nav.blockSignals(False)

        if not enabled:
            self._empty.setVisible(True)
            self._stack.setVisible(False)
            return

        self._empty.setVisible(False)
        self._stack.setVisible(True)
        pick = 0
        if prev_key:
            for i, (key, _t) in enumerate(enabled):
                if key == prev_key:
                    pick = i
                    break
        self._nav.setCurrentRow(pick)
        self._show_key(enabled[pick][0])

    def _on_nav_item(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if key:
            self._show_key(str(key))

    def _show_key(self, key: str) -> None:
        page = self._pages.get(key)
        if page is not None:
            self._stack.setCurrentWidget(page)
            self._stack.updateGeometry()
        if key == "bounds":
            self._refresh_mem_estimate()

    def _capability_host_flags(self) -> tuple[bool, bool, bool]:
        """(k_dlt, k_roudi, k_frame_ingest) from live UI / session (authoring truth)."""
        if not self._session:
            return False, False, False
        # Prefer live log checkbox when the Log page exists.
        if hasattr(self, "_log_sink_dlt"):
            k_dlt = bool(self._log_sink_dlt.isChecked())
        else:
            log = self._session.get_ara_doc("log")
            sinks = {str(s).strip().lower() for s in (log.get("sinks") or [])}
            k_dlt = "dlt" in sinks
        bindings = [
            str(b).strip().lower()
            for b in (self._session.req.get("bindings") or [])
        ]
        k_roudi = "iceoryx" in bindings
        fi = self._session.req.get("frame_ingest")
        if not isinstance(fi, dict):
            fi = {}
        bridge = fi.get("bridge") if isinstance(fi.get("bridge"), dict) else {}
        active = str(fi.get("active_source") or "none").strip().lower()
        k_frame = bool(bridge.get("enabled")) or (active not in ("", "none"))
        return k_dlt, k_roudi, k_frame

    def _process_names(self) -> list[str]:
        """Eligible process names for exec / EM / PHM pickers.

        - SOA apps: page-1 wiring deployments (non-external)
        - host.*: capability-gated (DLT sink / iceoryx / frame_ingest) — not inventable
        """
        if not self._session:
            return []
        ap = list(self._session.wiring_process_names(include_external=False))
        k_dlt, k_roudi, k_frame = self._capability_host_flags()
        hosts = gated_host_processes(
            k_dlt=k_dlt, k_roudi=k_roudi, k_frame_ingest=k_frame
        )
        # Hosts first (stable EM order), then wiring apps.
        seen: set[str] = set()
        out: list[str] = []
        for n in list(hosts) + ap:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def _host_row_tip(self, name: str) -> str:
        if name == HOST_DLT:
            return T.HOST_ROW_DLT
        if name == HOST_ROUDI:
            return T.HOST_ROW_ROUDI
        if name == HOST_FRAME_INGEST:
            return T.HOST_ROW_FRAME
        return T.HOST_ROW_GENERIC

    def sync_capability_hosts(self) -> None:
        """Capability changed: refresh pickers/gates only — never mutate exec/EM rows.

        Host membership vs capability is enforced by validate (open/save gate).
        """
        if self._loading or not self._session:
            return
        if not hasattr(self, "_proc_table") or not hasattr(self, "_em_table"):
            return
        self._refresh_process_name_combos()
        self._refresh_bounds_gates()
        self._refresh_mem_estimate()

    def _name_picker_options(self, current: str = "") -> list[str]:
        """Wiring SOA + capability-gated host.* (and current value if orphaned)."""
        names = list(self._process_names())
        if current and current not in names:
            names = [current] + names
        if "" not in names:
            names = [""] + names
        return names

    def _iox_shm_report_default_path(self) -> Path | None:
        if not self._session:
            return None
        return self._session.paths.project_dir / "reports" / "iox_shm_report.json"

    def _load_iox_shm_report(self) -> None:
        default = self._iox_shm_report_default_path()
        start = ""
        if default is not None:
            # Prefer full default file path so the dialog lands on reports/iox_shm_report.json
            start = str(default)
        elif self._session is not None:
            start = str(self._session.paths.project_dir / "reports")
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            t("载入实测 SHM"),
            start,
            t("iox SHM 报告 (*.json);;所有文件 (*)"),
        )
        if not path_str:
            return
        path = Path(path_str)
        if not path.is_file():
            QMessageBox.warning(
                self,
                t("载入实测 SHM"),
                t(
                    "未找到 {path}\n"
                    "请先跑 SIL / smoke_sil_verify（RouDi 会写出该报告），再载入。"
                ).format(path=path),
            )
            return
        self._iox_shm_report_path = path
        self._refresh_mem_estimate()

    def _clear_iox_shm_report(self) -> None:
        self._iox_shm_report_path = None
        self._refresh_mem_estimate()

    def _refresh_mem_estimate(self) -> None:
        if not self._session or not hasattr(self, "_bnd_estimate"):
            return
        est = estimate_mem_budget(
            self._session.ara_cfg,
            req=self._session.req,
            shm_report_path=self._iox_shm_report_path,
        )
        ram_b = int(est.get("total_ram_bytes") or 0)
        disk_b = int(est.get("total_disk_bytes") or 0)
        shm_b = int(est.get("total_shm_bytes") or 0)
        mgmt_st = str(est.get("roudi_mgmt_status") or "n/a")
        payload_b = 0
        mgmt_b = 0
        for ln in est.get("lines") or []:
            if ln.get("kind") != "shm":
                continue
            if ln.get("name") == "roudi_payload":
                payload_b = int(ln.get("bytes") or 0)
            elif ln.get("name") == "roudi_mgmt":
                mgmt_b = int(ln.get("bytes") or 0)
        if hasattr(self, "_bnd_shm_status"):
            if self._iox_shm_report_path is not None and mgmt_st == "measured":
                self._bnd_shm_status.setText(
                    t(
                        "SHM 实测：已载入 {path} · mgmt={mgmt} · payload={payload}（与当前 IOX 一致）"
                    ).format(
                        path=self._iox_shm_report_path.name,
                        mgmt=fmt_bytes(mgmt_b),
                        payload=fmt_bytes(payload_b),
                    )
                )
                self._bnd_shm_status.setStyleSheet("color:#E65100; font-size:12px;")
            elif self._iox_shm_report_path is not None and mgmt_st == "approx":
                self._bnd_shm_status.setText(
                    t(
                        "SHM：已载入 {path}，但 IOX 与报告不一致 → mgmt≈{mgmt}（近似，以重编实测为准）"
                    ).format(
                        path=self._iox_shm_report_path.name,
                        mgmt=fmt_bytes(mgmt_b),
                    )
                )
                self._bnd_shm_status.setStyleSheet("color:#E65100; font-size:12px;")
            elif self._iox_shm_report_path is not None:
                self._bnd_shm_status.setText(
                    t("SHM 实测：已指定 {path}，但报告无效或未含 mgmt_bytes").format(
                        path=self._iox_shm_report_path
                    )
                )
                self._bnd_shm_status.setStyleSheet("color:#b71c1c; font-size:12px;")
            else:
                self._bnd_shm_status.setText(
                    t(
                        "SHM 实测：未载入 · roudi_mgmt≈{mgmt}（近似，缺依据，以实测为准）"
                    ).format(mgmt=fmt_bytes(mgmt_b))
                )
                self._bnd_shm_status.setStyleSheet("color:#666; font-size:12px;")
        # Conclusion colors: RAM blue · DISK green · SHM amber (distinct kinds).
        shm_note = ""
        if mgmt_st == "measured":
            shm_note = (
                "&nbsp;<span style='color:#E65100;font-size:12px;'>"
                f"({html.escape(t('payload+mgmt 实测'))})</span>"
            )
        elif mgmt_st == "approx" and est.get("iceoryx_enabled"):
            shm_note = (
                "&nbsp;<span style='color:#999;font-size:12px;'>"
                f"({html.escape(t('mgmt 近似 — 非精确，以 SIL 实测为准'))})</span>"
            )
        if hasattr(self, "_bnd_estimate_summary"):
            parts = [
                html.escape(t("有界内存预估")),
                f'<span style="color:#1565C0;font-weight:700;">'
                f"RAM={html.escape(fmt_bytes(ram_b))}</span>",
                f'<span style="color:#2E7D32;font-weight:700;">'
                f"DISK={html.escape(fmt_bytes(disk_b))}</span>",
            ]
            if est.get("iceoryx_enabled"):
                parts.append(
                    f'<span style="color:#E65100;font-weight:700;">'
                    f"SHM={html.escape(fmt_bytes(shm_b))}</span>"
                    f"{shm_note}"
                )
            self._bnd_estimate_summary.setText("&nbsp;&nbsp;".join(parts))
        self._bnd_estimate.setText(self._mem_estimate_body_html(est))

    @staticmethod
    def _mem_estimate_body_html(est: dict[str, Any]) -> str:
        """Detail lines: color+pct on value before ←; formula after ← unchanged."""
        colors = {"ram": "#1565C0", "disk": "#2E7D32", "shm": "#E65100"}
        totals = {
            "ram": int(est.get("total_ram_bytes") or 0),
            "disk": int(est.get("total_disk_bytes") or 0),
            "shm": int(est.get("total_shm_bytes") or 0),
        }

        def pct(n: int, total: int) -> str:
            if total <= 0:
                return "0.0%"
            return f"{100.0 * n / total:.1f}%"

        def value_span(kind: str, n: int) -> str:
            c = colors.get(kind, "#333")
            return (
                f'<span style="color:{c};font-weight:600;">'
                f"{html.escape(fmt_bytes(n))} ({pct(n, totals.get(kind, 0))})"
                f"</span>"
            )

        lines_out: list[str] = []
        if est.get("iceoryx_enabled"):
            lines_out.append(
                html.escape(
                    "SHM = iceoryx/RouDi POSIX shared memory "
                    "(roudi_payload mempools + iceoryx_mgmt); not process heap RSS."
                )
            )
        lines_out.append(html.escape(f"(constants: {est.get('constants')})"))
        lines_out.append(html.escape("RAM lines (process-local upper bound):"))
        for ln in est.get("lines") or []:
            if ln.get("kind") != "ram":
                continue
            lines_out.append(
                f"&nbsp;&nbsp;{html.escape(str(ln.get('name')))}: "
                f"{value_span('ram', int(ln.get('bytes') or 0))}"
                f"&nbsp;&nbsp;← {html.escape(str(ln.get('formula') or ''))}"
            )
        lines_out.append(html.escape("DISK lines:"))
        for ln in est.get("lines") or []:
            if ln.get("kind") != "disk":
                continue
            lines_out.append(
                f"&nbsp;&nbsp;{html.escape(str(ln.get('name')))}: "
                f"{value_span('disk', int(ln.get('bytes') or 0))}"
                f"&nbsp;&nbsp;← {html.escape(str(ln.get('formula') or ''))}"
            )
        shm_lines = [ln for ln in (est.get("lines") or []) if ln.get("kind") == "shm"]
        if shm_lines:
            lines_out.append(
                html.escape("SHM lines (iceoryx / RouDi shared memory):")
            )
            for ln in shm_lines:
                lines_out.append(
                    f"&nbsp;&nbsp;{html.escape(str(ln.get('name')))}: "
                    f"{value_span('shm', int(ln.get('bytes') or 0))}"
                    f"&nbsp;&nbsp;← {html.escape(str(ln.get('formula') or ''))}"
                )
            if est.get("roudi_mgmt_status") == "approx":
                lines_out.append(
                    html.escape(
                        t(
                            "说明：roudi_mgmt 为近似值（非精确）。"
                            "改 mgmt.* → compose → 重编 iceoryx（如 compile_sil）→ "
                            "跑 SIL → 载入 iox_shm_report.json。"
                            "仅改 mempool → compose + 重启 RouDi。"
                        )
                    )
                )
            elif est.get("roudi_mgmt_status") == "measured":
                lines_out.append(
                    html.escape(
                        t(
                            "说明：roudi_mgmt 来自实测报告（与当前 IOX 配置一致）。"
                            "仅改 mempool → compose + 重启 RouDi（无需重编 iceoryx）。"
                        )
                    )
                )
        for e in est.get("errors") or []:
            lines_out.append(
                f'<span style="color:#b71c1c;">ERROR: {html.escape(str(e))}</span>'
            )
        for w in est.get("warnings") or []:
            lines_out.append(
                f'<span style="color:#e65100;">WARN: {html.escape(str(w))}</span>'
            )
        return "<br/>".join(lines_out)

    # ── write-back ────────────────────────────────────────

    def rebaseline_spins(self) -> None:
        """After save: clear amber dirty tint on numeric fields."""
        for spin in self.findChildren(QSpinBox):
            if getattr(spin, "_gf_dirty_bound", False):
                set_spin_baseline(spin)

    def _add_iox_pool_row(self) -> None:
        self._iox_pool_table.blockSignals(True)
        r = self._iox_pool_table.rowCount()
        self._iox_pool_table.insertRow(r)
        _set_cell(self._iox_pool_table, r, 0, "256")
        _set_cell(self._iox_pool_table, r, 1, "32")
        self._iox_pool_table.blockSignals(False)
        self._on_bounds_changed()

    # ── row helpers ───────────────────────────────────────

    def _add_fg_row(self) -> None:
        self._fg_table.blockSignals(True)
        r = self._fg_table.rowCount()
        self._fg_table.insertRow(r)
        self._fill_fg_row(
            r,
            fid=f"FG{r + 1}",
            kind="machine",
            initial="Running",
            states=[],
        )
        self._fg_table.blockSignals(False)
        self._on_exec_changed()

    def _add_proc_row(self) -> None:
        """Insert a blank membership row; name must be chosen from wiring."""
        self._proc_table.blockSignals(True)
        r = self._proc_table.rowCount()
        self._proc_table.insertRow(r)
        self._fill_proc_row(
            r,
            name="",
            fg=self._default_fg(),
            deps=[],
            execution_client=True,
            active_in=[],
        )
        self._proc_table.blockSignals(False)
        self._on_exec_changed()

    def _add_em_row(self) -> None:
        self._em_table.blockSignals(True)
        r = self._em_table.rowCount()
        self._em_table.insertRow(r)
        self._fill_em_row(
            r,
            name="",
            binary="",
            args_s=_DEFAULT_EM_ARGS,
            mr_s=str(_DEFAULT_MAX_RESTARTS),
        )
        self._em_table.blockSignals(False)
        self._on_em_launch_changed()

    def _add_phm_row(self) -> None:
        self._phm_table.blockSignals(True)
        r = self._phm_table.rowCount()
        self._phm_table.insertRow(r)
        self._fill_phm_row(
            r,
            eid="",
            process="",
            period=str(_DEFAULT_ALIVE_PERIOD_MS),
            timeout=str(_DEFAULT_ALIVE_TIMEOUT_MS),
            deadline=str(_DEFAULT_DEADLINE_MS),
            on_failure="log",
        )
        self._phm_table.blockSignals(False)
        self._on_phm_changed()

    def _add_did_row(self) -> None:
        self._did_table.blockSignals(True)
        r = self._did_table.rowCount()
        self._did_table.insertRow(r)
        _set_cell(self._did_table, r, 0, "0x0000", T.DID_ID)
        _set_cell(self._did_table, r, 1, "", T.DID_NAME)
        _set_combo(
            self._did_table,
            r,
            2,
            _DID_ACCESS,
            "read",
            self._on_diag_changed,
            tip=T.DID_ACCESS,
            enum_colors=COLORS_DID_ACCESS,
            item_tips=T.DID_ACCESS_ITEMS,
        )
        _set_cell(self._did_table, r, 3, "0", T.DID_SIZE)
        self._did_table.blockSignals(False)
        self._on_diag_changed()

    def select_nav(self, key: str) -> bool:
        """Switch left nav / stack to a platform page key (exec, phm, log, …)."""
        enabled = self._enabled_nav()
        for i, (k, _title) in enumerate(enabled):
            if k == key:
                self._nav.setCurrentRow(i)
                self._show_key(key)
                return True
        return False

    def _add_log_ctx_row(self) -> None:
        self._ctx_table.blockSignals(True)
        r = self._ctx_table.rowCount()
        self._ctx_table.insertRow(r)
        mods = [m for m in KNOWN_MODULES if m not in ALWAYS_ON_MODULES] + ["app"]
        _set_combo(
            self._ctx_table,
            r,
            0,
            mods,
            "",
            self._on_log_changed,
            tip=T.LOG_CTX_ID,
        )
        _set_combo(
            self._ctx_table,
            r,
            1,
            _LOG_LEVELS,
            "INFO",
            self._on_log_changed,
            tip=T.LOG_CTX_LEVEL,
            enum_colors=COLORS_LOG_LEVEL,
            item_tips=T.LOG_LEVEL_ITEMS,
        )
        self._ctx_table.blockSignals(False)
        self._ctx_table.selectRow(r)
        self._on_log_changed()

    def _add_empty_row(
        self, table: QTableWidget, cols: int, on_change: Callable[..., None]
    ) -> None:
        table.blockSignals(True)
        r = table.rowCount()
        table.insertRow(r)
        for c in range(cols):
            _set_cell(table, r, c, "")
        table.blockSignals(False)
        on_change()

    def _del_proc_rows(self) -> None:
        self._del_rows(self._proc_table, self._on_exec_changed)

    def _del_em_rows(self) -> None:
        self._del_rows(self._em_table, self._on_em_launch_changed)

    def _del_rows(self, table: QTableWidget, on_change: Callable[..., None]) -> None:
        rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
        if not rows and table.currentRow() >= 0:
            rows = [table.currentRow()]
        if not rows:
            return
        table.blockSignals(True)
        for r in rows:
            table.removeRow(r)
        table.blockSignals(False)
        on_change()
