"""C · 平台 — edit platform/{exec,phm,diag,log,ucm}.yaml."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession

# (platform yaml key, nav title, runtime_modules that unlock this page)
_NAV = [
    ("exec", "执行 / 功能组", frozenset({"exec", "sm"})),
    ("phm", "健康 PHM", frozenset({"phm"})),
    ("diag", "诊断 diag", frozenset({"diag"})),
    ("log", "日志", frozenset({"log"})),
    ("ucm", "OTA ucm", frozenset({"ucm"})),
]

_LOG_LEVELS = ["FATAL", "ERROR", "WARN", "INFO", "DEBUG", "VERBOSE"]


def _int_or_none(text: str) -> int | None:
    t = text.strip()
    if not t or t.lower() in ("null", "none", "-"):
        return None
    return int(t, 0)


def _cell(table: QTableWidget, row: int, col: int) -> str:
    item = table.item(row, col)
    return item.text().strip() if item else ""


def _set_cell(table: QTableWidget, row: int, col: int, text: str) -> None:
    table.setItem(row, col, QTableWidgetItem(text))


class PlatformEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._loading = False
        self._modules: set[str] = set()
        self._pages: dict[str, QWidget] = {}

        root = QHBoxLayout(self)
        self._nav = QListWidget()
        self._nav.setFixedWidth(160)
        root.addWidget(self._nav)

        right = QVBoxLayout()
        self._empty = QLabel(
            "当前 A · SKU 未勾选任何平台模块（exec / phm / diag / log / ucm / sm）。\n"
            "请到 A 页勾选 runtime_modules 后，对应清单才会出现在左侧。"
        )
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._empty.setStyleSheet("color:#666; padding:12px;")
        right.addWidget(self._empty)

        self._stack = QStackedWidget()
        right.addWidget(self._stack, stretch=1)
        root.addLayout(right, stretch=1)

        self._pages["exec"] = self._build_exec_page()
        self._pages["phm"] = self._build_phm_page()
        self._pages["diag"] = self._build_diag_page()
        self._pages["log"] = self._build_log_page()
        self._pages["ucm"] = self._build_ucm_page()
        for key, _title, _mods in _NAV:
            self._stack.addWidget(self._pages[key])

        self._nav.currentItemChanged.connect(self._on_nav_item)
        self._rebuild_nav()

    # ── pages ─────────────────────────────────────────────

    def _build_exec_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel(
            "exec.yaml：功能组（SM 极简）+ 进程隶属。进程名只读自 wiring（不含 external.*）。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        fg_box = QGroupBox("function_groups")
        fg_l = QVBoxLayout(fg_box)
        self._fg_table = QTableWidget(0, 2)
        self._fg_table.setHorizontalHeaderLabels(["id", "initial"])
        self._fg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._fg_table.itemChanged.connect(self._on_exec_changed)
        fg_l.addWidget(self._fg_table)
        fg_btns = QHBoxLayout()
        add_fg = QPushButton("添加 FG")
        add_fg.clicked.connect(self._add_fg_row)
        del_fg = QPushButton("删除选中")
        del_fg.clicked.connect(lambda: self._del_rows(self._fg_table, self._on_exec_changed))
        fg_btns.addWidget(add_fg)
        fg_btns.addWidget(del_fg)
        fg_btns.addStretch(1)
        fg_l.addLayout(fg_btns)
        lay.addWidget(fg_box)

        proc_box = QGroupBox("processes")
        proc_l = QVBoxLayout(proc_box)
        self._proc_table = QTableWidget(0, 4)
        self._proc_table.setHorizontalHeaderLabels(
            ["name", "function_group", "depends_on（空格/逗号分隔）", "execution_client"]
        )
        self._proc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._proc_table.itemChanged.connect(self._on_exec_changed)
        proc_l.addWidget(self._proc_table)
        proc_btns = QHBoxLayout()
        add_p = QPushButton("添加进程行")
        add_p.clicked.connect(self._add_proc_row)
        del_p = QPushButton("删除选中")
        del_p.clicked.connect(lambda: self._del_rows(self._proc_table, self._on_exec_changed))
        sync_p = QPushButton("从 wiring 同步进程名")
        sync_p.clicked.connect(self._sync_processes_from_wiring)
        proc_btns.addWidget(add_p)
        proc_btns.addWidget(del_p)
        proc_btns.addWidget(sync_p)
        proc_btns.addStretch(1)
        proc_l.addLayout(proc_btns)
        lay.addWidget(proc_box, stretch=1)
        return w

    def _build_phm_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel("phm.yaml：Alive / 可选 Deadline。process ∈ wiring（非 external）。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        self._phm_table = QTableWidget(0, 6)
        self._phm_table.setHorizontalHeaderLabels(
            [
                "id",
                "process",
                "alive_period_ms",
                "alive_timeout_ms",
                "deadline_ms",
                "on_failure",
            ]
        )
        self._phm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._phm_table.itemChanged.connect(self._on_phm_changed)
        lay.addWidget(self._phm_table, stretch=1)
        btns = QHBoxLayout()
        add_e = QPushButton("添加 entity")
        add_e.clicked.connect(self._add_phm_row)
        del_e = QPushButton("删除选中")
        del_e.clicked.connect(lambda: self._del_rows(self._phm_table, self._on_phm_changed))
        btns.addWidget(add_e)
        btns.addWidget(del_e)
        btns.addStretch(1)
        lay.addLayout(btns)
        return w

    def _build_diag_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel("diag.yaml：DoIP + DID/RID（非 DEM）。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        doip = QGroupBox("doip")
        doip_f = QFormLayout(doip)
        self._doip_enabled = QCheckBox("enabled")
        self._doip_enabled.toggled.connect(self._on_diag_changed)
        self._doip_addr = QLineEdit()
        self._doip_addr.setPlaceholderText("0x0E00")
        self._doip_addr.textChanged.connect(self._on_diag_changed)
        doip_f.addRow("", self._doip_enabled)
        doip_f.addRow("logical_address", self._doip_addr)
        lay.addWidget(doip)

        did_box = QGroupBox("dids")
        did_l = QVBoxLayout(did_box)
        self._did_table = QTableWidget(0, 4)
        self._did_table.setHorizontalHeaderLabels(["id", "name", "access", "size"])
        self._did_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._did_table.itemChanged.connect(self._on_diag_changed)
        did_l.addWidget(self._did_table)
        did_btns = QHBoxLayout()
        add_d = QPushButton("添加 DID")
        add_d.clicked.connect(
            lambda: self._add_empty_row(self._did_table, 4, self._on_diag_changed)
        )
        del_d = QPushButton("删除选中")
        del_d.clicked.connect(lambda: self._del_rows(self._did_table, self._on_diag_changed))
        did_btns.addWidget(add_d)
        did_btns.addWidget(del_d)
        did_btns.addStretch(1)
        did_l.addLayout(did_btns)
        lay.addWidget(did_box)

        rid_box = QGroupBox("rids")
        rid_l = QVBoxLayout(rid_box)
        self._rid_table = QTableWidget(0, 2)
        self._rid_table.setHorizontalHeaderLabels(["id", "name"])
        self._rid_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._rid_table.itemChanged.connect(self._on_diag_changed)
        rid_l.addWidget(self._rid_table)
        rid_btns = QHBoxLayout()
        add_r = QPushButton("添加 RID")
        add_r.clicked.connect(
            lambda: self._add_empty_row(self._rid_table, 2, self._on_diag_changed)
        )
        del_r = QPushButton("删除选中")
        del_r.clicked.connect(lambda: self._del_rows(self._rid_table, self._on_diag_changed))
        rid_btns.addWidget(add_r)
        rid_btns.addWidget(del_r)
        rid_btns.addStretch(1)
        rid_l.addLayout(rid_btns)
        lay.addWidget(rid_box, stretch=1)
        return w

    def _build_log_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel("log.yaml：默认级别与 contexts（细配置在此；A 页仅粗开关）。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        form = QFormLayout()
        self._log_level = QComboBox()
        self._log_level.setEditable(True)
        self._log_level.addItems(_LOG_LEVELS)
        self._log_level.currentTextChanged.connect(self._on_log_changed)
        form.addRow("default_level", self._log_level)
        lay.addLayout(form)

        ctx_box = QGroupBox("contexts")
        ctx_l = QVBoxLayout(ctx_box)
        self._ctx_table = QTableWidget(0, 2)
        self._ctx_table.setHorizontalHeaderLabels(["id", "level"])
        self._ctx_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ctx_table.itemChanged.connect(self._on_log_changed)
        ctx_l.addWidget(self._ctx_table)
        ctx_btns = QHBoxLayout()
        add_c = QPushButton("添加 context")
        add_c.clicked.connect(
            lambda: self._add_empty_row(self._ctx_table, 2, self._on_log_changed)
        )
        del_c = QPushButton("删除选中")
        del_c.clicked.connect(lambda: self._del_rows(self._ctx_table, self._on_log_changed))
        ctx_btns.addWidget(add_c)
        ctx_btns.addWidget(del_c)
        ctx_btns.addStretch(1)
        ctx_l.addLayout(ctx_btns)
        lay.addWidget(ctx_box, stretch=1)
        return w

    def _build_ucm_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel("ucm.yaml：P2 空壳（stub）。真 OTA 策略在 P3。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        form = QFormLayout()
        self._ucm_enabled = QCheckBox("enabled")
        self._ucm_enabled.toggled.connect(self._on_ucm_changed)
        self._ucm_source = QLineEdit()
        self._ucm_source.textChanged.connect(self._on_ucm_changed)
        self._ucm_rollback = QCheckBox("allow_rollback")
        self._ucm_rollback.toggled.connect(self._on_ucm_changed)
        form.addRow("", self._ucm_enabled)
        form.addRow("package_source", self._ucm_source)
        form.addRow("", self._ucm_rollback)
        lay.addLayout(form)
        lay.addStretch(1)
        return w

    # ── session ───────────────────────────────────────────

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        if session is None:
            return
        self._loading = True
        self._load_exec(session.platform.get("exec") or {})
        self._load_phm(session.platform.get("phm") or {})
        self._load_diag(session.platform.get("diag") or {})
        self._load_log(session.platform.get("log") or {})
        self._load_ucm(session.platform.get("ucm") or {})
        self._loading = False
        mods = [str(x) for x in (session.req.get("runtime_modules") or [])]
        self.set_runtime_modules(mods)

    def set_runtime_modules(self, modules: list[str]) -> None:
        """Filter C 子页：仅显示 A 页已勾选的平台模块。"""
        self._modules = {str(m) for m in modules}
        self._rebuild_nav()

    def _enabled_nav(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for key, title, unlock in _NAV:
            if self._modules & unlock:
                out.append((key, title))
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

    def refresh_process_lists(self) -> None:
        """Call after wiring process set may have changed (optional UX)."""
        return

    def _process_names(self) -> list[str]:
        if not self._session:
            return []
        return self._session.wiring_process_names(include_external=False)

    def _default_fg(self) -> str:
        if self._fg_table.rowCount() > 0:
            return _cell(self._fg_table, 0, 0) or "MachineFG"
        return "MachineFG"

    # ── load helpers ──────────────────────────────────────

    def _load_exec(self, data: dict[str, Any]) -> None:
        self._fg_table.blockSignals(True)
        self._proc_table.blockSignals(True)
        self._fg_table.setRowCount(0)
        for fg in data.get("function_groups") or []:
            if not isinstance(fg, dict):
                continue
            r = self._fg_table.rowCount()
            self._fg_table.insertRow(r)
            _set_cell(self._fg_table, r, 0, str(fg.get("id") or ""))
            _set_cell(self._fg_table, r, 1, str(fg.get("initial") or "Running"))
        self._proc_table.setRowCount(0)
        for p in data.get("processes") or []:
            if not isinstance(p, dict):
                continue
            r = self._proc_table.rowCount()
            self._proc_table.insertRow(r)
            deps = p.get("depends_on") or []
            deps_s = ", ".join(str(x) for x in deps)
            _set_cell(self._proc_table, r, 0, str(p.get("name") or ""))
            _set_cell(self._proc_table, r, 1, str(p.get("function_group") or ""))
            _set_cell(self._proc_table, r, 2, deps_s)
            _set_cell(
                self._proc_table,
                r,
                3,
                "true" if p.get("execution_client", True) else "false",
            )
        self._fg_table.blockSignals(False)
        self._proc_table.blockSignals(False)

    def _load_phm(self, data: dict[str, Any]) -> None:
        self._phm_table.blockSignals(True)
        self._phm_table.setRowCount(0)
        for e in data.get("entities") or []:
            if not isinstance(e, dict):
                continue
            r = self._phm_table.rowCount()
            self._phm_table.insertRow(r)
            dl = e.get("deadline_ms")
            _set_cell(self._phm_table, r, 0, str(e.get("id") or ""))
            _set_cell(self._phm_table, r, 1, str(e.get("process") or ""))
            _set_cell(self._phm_table, r, 2, str(e.get("alive_period_ms", 100)))
            _set_cell(self._phm_table, r, 3, str(e.get("alive_timeout_ms", 300)))
            _set_cell(self._phm_table, r, 4, "" if dl is None else str(dl))
            _set_cell(self._phm_table, r, 5, str(e.get("on_failure") or "log"))
        self._phm_table.blockSignals(False)

    def _load_diag(self, data: dict[str, Any]) -> None:
        doip = data.get("doip") if isinstance(data.get("doip"), dict) else {}
        self._doip_enabled.blockSignals(True)
        self._doip_addr.blockSignals(True)
        self._doip_enabled.setChecked(bool(doip.get("enabled", False)))
        addr = doip.get("logical_address", "0x0E00")
        if isinstance(addr, int):
            self._doip_addr.setText(hex(addr))
        else:
            self._doip_addr.setText(str(addr or "0x0E00"))
        self._doip_enabled.blockSignals(False)
        self._doip_addr.blockSignals(False)

        self._did_table.blockSignals(True)
        self._did_table.setRowCount(0)
        for d in data.get("dids") or []:
            if not isinstance(d, dict):
                continue
            r = self._did_table.rowCount()
            self._did_table.insertRow(r)
            did = d.get("id", "")
            _set_cell(self._did_table, r, 0, hex(did) if isinstance(did, int) else str(did))
            _set_cell(self._did_table, r, 1, str(d.get("name") or ""))
            _set_cell(self._did_table, r, 2, str(d.get("access") or ""))
            _set_cell(self._did_table, r, 3, str(d.get("size") or ""))
        self._did_table.blockSignals(False)

        self._rid_table.blockSignals(True)
        self._rid_table.setRowCount(0)
        for d in data.get("rids") or []:
            if not isinstance(d, dict):
                continue
            r = self._rid_table.rowCount()
            self._rid_table.insertRow(r)
            rid = d.get("id", "")
            _set_cell(self._rid_table, r, 0, hex(rid) if isinstance(rid, int) else str(rid))
            _set_cell(self._rid_table, r, 1, str(d.get("name") or ""))
        self._rid_table.blockSignals(False)

    def _load_log(self, data: dict[str, Any]) -> None:
        self._log_level.blockSignals(True)
        self._log_level.setCurrentText(str(data.get("default_level") or "INFO"))
        self._log_level.blockSignals(False)
        self._ctx_table.blockSignals(True)
        self._ctx_table.setRowCount(0)
        for c in data.get("contexts") or []:
            if not isinstance(c, dict):
                continue
            r = self._ctx_table.rowCount()
            self._ctx_table.insertRow(r)
            _set_cell(self._ctx_table, r, 0, str(c.get("id") or ""))
            _set_cell(self._ctx_table, r, 1, str(c.get("level") or "INFO"))
        self._ctx_table.blockSignals(False)

    def _load_ucm(self, data: dict[str, Any]) -> None:
        self._ucm_enabled.blockSignals(True)
        self._ucm_source.blockSignals(True)
        self._ucm_rollback.blockSignals(True)
        self._ucm_enabled.setChecked(bool(data.get("enabled", False)))
        self._ucm_source.setText(str(data.get("package_source") or ""))
        self._ucm_rollback.setChecked(bool(data.get("allow_rollback", True)))
        self._ucm_enabled.blockSignals(False)
        self._ucm_source.blockSignals(False)
        self._ucm_rollback.blockSignals(False)

    # ── write-back ────────────────────────────────────────

    def _mark(self, key: str) -> None:
        if self._loading or not self._session:
            return
        self._session.mark_platform_dirty(key)
        self.changed.emit()

    def _on_exec_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        fgs: list[dict[str, Any]] = []
        for r in range(self._fg_table.rowCount()):
            fid = _cell(self._fg_table, r, 0)
            if not fid:
                continue
            fgs.append(
                {
                    "id": fid,
                    "initial": _cell(self._fg_table, r, 1) or "Running",
                }
            )
        procs: list[dict[str, Any]] = []
        for r in range(self._proc_table.rowCount()):
            name = _cell(self._proc_table, r, 0)
            if not name:
                continue
            deps_raw = _cell(self._proc_table, r, 2).replace(",", " ")
            deps = [x for x in deps_raw.split() if x]
            ec = _cell(self._proc_table, r, 3).lower() not in ("false", "0", "no", "")
            procs.append(
                {
                    "name": name,
                    "function_group": _cell(self._proc_table, r, 1) or self._default_fg(),
                    "depends_on": deps,
                    "execution_client": ec,
                }
            )
        data = self._session.platform.setdefault("exec", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["function_groups"] = fgs
        data["processes"] = procs
        self._mark("exec")

    def _on_phm_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        entities: list[dict[str, Any]] = []
        for r in range(self._phm_table.rowCount()):
            eid = _cell(self._phm_table, r, 0)
            if not eid:
                continue
            try:
                period = int(_cell(self._phm_table, r, 2) or "100")
                timeout = int(_cell(self._phm_table, r, 3) or "300")
                deadline = _int_or_none(_cell(self._phm_table, r, 4))
            except ValueError:
                continue
            entities.append(
                {
                    "id": eid,
                    "process": _cell(self._phm_table, r, 1),
                    "alive_period_ms": period,
                    "alive_timeout_ms": timeout,
                    "deadline_ms": deadline,
                    "on_failure": _cell(self._phm_table, r, 5) or "log",
                }
            )
        data = self._session.platform.setdefault("phm", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["entities"] = entities
        self._mark("phm")

    def _on_diag_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        try:
            addr = _int_or_none(self._doip_addr.text())
            if addr is None:
                addr = 0x0E00
        except ValueError:
            addr = 0x0E00
        dids: list[dict[str, Any]] = []
        for r in range(self._did_table.rowCount()):
            did = _cell(self._did_table, r, 0)
            if not did:
                continue
            entry: dict[str, Any] = {
                "id": did,
                "name": _cell(self._did_table, r, 1),
                "access": _cell(self._did_table, r, 2),
            }
            size_s = _cell(self._did_table, r, 3)
            if size_s:
                try:
                    entry["size"] = int(size_s, 0)
                except ValueError:
                    entry["size"] = size_s
            dids.append(entry)
        rids: list[dict[str, Any]] = []
        for r in range(self._rid_table.rowCount()):
            rid = _cell(self._rid_table, r, 0)
            if not rid:
                continue
            rids.append({"id": rid, "name": _cell(self._rid_table, r, 1)})
        data = self._session.platform.setdefault("diag", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["doip"] = {"enabled": self._doip_enabled.isChecked(), "logical_address": addr}
        data["dids"] = dids
        data["rids"] = rids
        self._mark("diag")

    def _on_log_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        contexts: list[dict[str, Any]] = []
        for r in range(self._ctx_table.rowCount()):
            cid = _cell(self._ctx_table, r, 0)
            if not cid:
                continue
            contexts.append(
                {"id": cid, "level": _cell(self._ctx_table, r, 1) or "INFO"}
            )
        data = self._session.platform.setdefault("log", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["default_level"] = self._log_level.currentText().strip() or "INFO"
        data["contexts"] = contexts
        self._mark("log")

    def _on_ucm_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        data = self._session.platform.setdefault("ucm", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["enabled"] = self._ucm_enabled.isChecked()
        data["package_source"] = self._ucm_source.text().strip()
        data["allow_rollback"] = self._ucm_rollback.isChecked()
        self._mark("ucm")

    # ── row helpers ───────────────────────────────────────

    def _add_fg_row(self) -> None:
        self._fg_table.blockSignals(True)
        r = self._fg_table.rowCount()
        self._fg_table.insertRow(r)
        _set_cell(self._fg_table, r, 0, f"FG{r + 1}")
        _set_cell(self._fg_table, r, 1, "Running")
        self._fg_table.blockSignals(False)
        self._on_exec_changed()

    def _add_proc_row(self) -> None:
        names = self._process_names()
        used = {_cell(self._proc_table, r, 0) for r in range(self._proc_table.rowCount())}
        pick = next((n for n in names if n not in used), names[0] if names else "process.name")
        self._proc_table.blockSignals(True)
        r = self._proc_table.rowCount()
        self._proc_table.insertRow(r)
        _set_cell(self._proc_table, r, 0, pick)
        _set_cell(self._proc_table, r, 1, self._default_fg())
        _set_cell(self._proc_table, r, 2, "")
        _set_cell(self._proc_table, r, 3, "true")
        self._proc_table.blockSignals(False)
        self._on_exec_changed()

    def _sync_processes_from_wiring(self) -> None:
        if not self._session:
            return
        names = self._process_names()
        if not names:
            QMessageBox.information(self, "同步", "wiring 中没有非 external 进程。")
            return
        existing: dict[str, tuple[str, str, str]] = {}
        for r in range(self._proc_table.rowCount()):
            name = _cell(self._proc_table, r, 0)
            if name:
                existing[name] = (
                    _cell(self._proc_table, r, 1),
                    _cell(self._proc_table, r, 2),
                    _cell(self._proc_table, r, 3) or "true",
                )
        self._proc_table.blockSignals(True)
        self._proc_table.setRowCount(0)
        fg = self._default_fg()
        for name in names:
            r = self._proc_table.rowCount()
            self._proc_table.insertRow(r)
            old = existing.get(name)
            _set_cell(self._proc_table, r, 0, name)
            _set_cell(self._proc_table, r, 1, old[0] if old else fg)
            _set_cell(self._proc_table, r, 2, old[1] if old else "")
            _set_cell(self._proc_table, r, 3, old[2] if old else "true")
        self._proc_table.blockSignals(False)
        self._on_exec_changed()

    def _add_phm_row(self) -> None:
        names = self._process_names()
        pick = names[0] if names else "process.name"
        self._phm_table.blockSignals(True)
        r = self._phm_table.rowCount()
        self._phm_table.insertRow(r)
        _set_cell(self._phm_table, r, 0, f"{pick.split('.')[-1]}_alive")
        _set_cell(self._phm_table, r, 1, pick)
        _set_cell(self._phm_table, r, 2, "100")
        _set_cell(self._phm_table, r, 3, "300")
        _set_cell(self._phm_table, r, 4, "")
        _set_cell(self._phm_table, r, 5, "log")
        self._phm_table.blockSignals(False)
        self._on_phm_changed()

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

    def _del_rows(self, table: QTableWidget, on_change: Callable[..., None]) -> None:
        rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        table.blockSignals(True)
        for r in rows:
            table.removeRow(r)
        table.blockSignals(False)
        on_change()
