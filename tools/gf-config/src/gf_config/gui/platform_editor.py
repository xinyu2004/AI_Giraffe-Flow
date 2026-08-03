"""页 2 · 平台运行时 — runtime_modules + platform/{exec,em_launch,phm,…}.yaml."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession
from gf_config.gui.field_ux import (
    COLORS_DID_ACCESS,
    COLORS_FG_INITIAL,
    COLORS_FORWARD,
    COLORS_LOG_LEVEL,
    COLORS_ON_FAILURE,
    ColorPair,
    combo_text,
    multi_selected,
    refresh_enum_combo_style,
    set_cell,
    set_combo,
    set_header_tips,
    set_multi_check,
    TintedComboBox,
    style_enum_combo,
    tipify,
)
from gf_config.gui import tips as T
from gf_config.i18n import t

# Fixed 5-column grid so row3 col1 (tsync) lines up under row2 col1 (sm).
# Always-on trio first (core / com / osal), then optional modules.
KNOWN_MODULES = [
    "core",
    "com",
    "osal",
    "log",
    "exec",
    "phm",
    "sm",
    "collector",
    "ucm",
    "diag",
    "per",
    "tsync",
    "trace",
]

# CMake always builds these (cmake/GfModules.cmake) — not trimable via checkbox.
ALWAYS_ON_MODULES = frozenset({"core", "com", "osal"})

_DEFAULT_MAX_RESTARTS = 3
# Explicit default argv token so the EM table never leaves args blank.
# Gateway: argv[1] = max Trajectory count (0 = forever). Other apps ignore argv today.
# Not an AUTOSAR AP standard field name — GF OS-EM spawn argv (POSIX-style).
_DEFAULT_EM_ARGS = "0"
_DEFAULT_ALIVE_PERIOD_MS = 100
_DEFAULT_ALIVE_TIMEOUT_MS = 300
# 0 = no separate deadline supervision in our SIL path (explicit, not null).
_DEFAULT_DEADLINE_MS = 0

_FG_INITIAL = ["Off", "Running", "Updating"]
_BOOL_TF = ["true", "false"]
_PHM_ON_FAILURE = ["log", "notify_sm", "restart"]
_DID_ACCESS = ["read", "write", "read_write"]


class _CurrentPageStack(QStackedWidget):
    """Use only the visible page for size hints so a tall page can't lock window height."""

    def minimumSizeHint(self):  # noqa: N802 — Qt API
        w = self.currentWidget()
        return w.minimumSizeHint() if w is not None else super().minimumSizeHint()

    def sizeHint(self):  # noqa: N802 — Qt API
        w = self.currentWidget()
        return w.sizeHint() if w is not None else super().sizeHint()


class _PlatformScrollPage(QScrollArea):
    """Scroll page that does not advertise tall content as the shell's preferred height."""

    def __init__(self, inner: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(inner)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setMinimumHeight(0)

    def sizeHint(self):  # noqa: N802 — Qt API
        return QSize(480, 360)

    def minimumSizeHint(self):  # noqa: N802 — Qt API
        return QSize(240, 160)


def _make_collapsible(
    title: str, *, expanded: bool = True
) -> tuple[QWidget, QWidget]:
    """Shell + body; put fields into body. Header arrow toggles body visibility."""
    shell = QFrame()
    shell.setFrameShape(QFrame.Shape.StyledPanel)
    outer = QVBoxLayout(shell)
    outer.setContentsMargins(8, 4, 8, 8)
    outer.setSpacing(4)

    hdr = QToolButton()
    hdr.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    hdr.setArrowType(
        Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
    )
    hdr.setText(title)
    hdr.setCheckable(True)
    hdr.setChecked(expanded)
    hdr.setAutoRaise(True)
    hdr.setCursor(Qt.CursorShape.PointingHandCursor)
    hdr.setStyleSheet(
        "QToolButton { border: none; font-weight: 600; padding: 2px 0; }"
    )

    body = QWidget()
    body.setVisible(expanded)

    def _toggle(checked: bool) -> None:
        body.setVisible(checked)
        hdr.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    hdr.toggled.connect(_toggle)
    outer.addWidget(hdr)
    outer.addWidget(body)
    return shell, body


_OTA_MODE_ITEMS: list[tuple[str, str]] = [
    ("request_file_transfer", "0x38 · RequestFileTransfer"),
    ("request_download", "0x34 · RequestDownload"),
    ("routine_sil", "0x31 · RoutineControl (SIL)"),
]

_MODULE_COLS = 5

# (platform yaml key, nav title, runtime_modules that unlock this page)
_NAV = [
    ("exec", "执行 / 功能组", frozenset({"exec", "sm"})),
    ("em_launch", "EM 启动表", frozenset({"exec"})),
    ("phm", "健康 PHM", frozenset({"phm"})),
    ("diag", "诊断 diag", frozenset({"diag"})),
    ("log", "日志", frozenset({"log"})),
    ("ucm", "OTA ucm", frozenset({"ucm"})),
    # Collector 最小集：有 diag 或 phm 即可配（不要求单独 runtime 模块名）
    ("collector", "事件收集", frozenset({"diag", "phm", "collector"})),
]

_LOG_LEVELS = ["FATAL", "ERROR", "WARN", "INFO", "DEBUG", "VERBOSE"]
_FORWARD_MODES = ["local_store", "cp_dem", "both"]
_COLLECTOR_SOURCES = ["phm", "process", "com"]


def _int_or_none(text: str) -> int | None:
    raw = text.strip()
    if not raw or raw.lower() in ("null", "none", "-"):
        return None
    return int(raw, 0)


def _int_or_default(text: str, default: int) -> int:
    try:
        v = _int_or_none(text)
    except ValueError:
        return default
    return default if v is None else v


def _cell(table: QTableWidget, row: int, col: int) -> str:
    item = table.item(row, col)
    return item.text().strip() if item else ""


def _set_cell(table: QTableWidget, row: int, col: int, text: str, tip: str = "") -> None:
    set_cell(table, row, col, text, tip)


def _combo_text(table: QTableWidget, row: int, col: int) -> str:
    return combo_text(table, row, col)


def _set_combo(
    table: QTableWidget,
    row: int,
    col: int,
    options: list[str],
    value: str,
    on_change: Callable[..., None],
    *,
    tip: str = "",
    bool_style: bool = False,
    enum_colors: dict[str, ColorPair] | None = None,
    item_tips: dict[str, str] | None = None,
) -> None:
    set_combo(
        table,
        row,
        col,
        options,
        value,
        on_change,
        tip=tip,
        bool_style=bool_style,
        enum_colors=enum_colors,
        item_tips=item_tips,
    )


class PlatformEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._loading = False
        self._modules: set[str] = set()
        self._module_boxes: dict[str, QCheckBox] = {}
        self._pages: dict[str, QWidget] = {}
        self._src_boxes: dict[str, QCheckBox] = {}

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
                "其余悬停看说明；勾选后左侧出现对应平台清单。"
            )
        )
        mods_note.setStyleSheet("color:#666; font-size:11px;")
        mods_l.addWidget(mods_note)
        root.addWidget(mods)

        body = QHBoxLayout()
        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        body.addWidget(self._nav)

        right = QVBoxLayout()
        self._empty = QLabel(
            t(
                "尚未勾选平台相关 runtime_modules（exec / phm / diag / log / ucm / sm）。\n"
                "勾选后，对应清单会出现在左侧。"
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
        for key, _title, _mods in _NAV:
            self._stack.addWidget(self._pages[key])

        self._nav.currentItemChanged.connect(self._on_nav_item)
        self._rebuild_nav()

    # ── pages ─────────────────────────────────────────────

    def _build_exec_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel(
            t(
                "exec.yaml：功能组（SM 极简）+ 进程隶属。"
                "进程名 / FG / depends_on 均从列表选择（不含 external.*）。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        fg_box = QGroupBox("function_groups")
        fg_l = QVBoxLayout(fg_box)
        self._fg_table = QTableWidget(0, 2)
        self._fg_table.setHorizontalHeaderLabels(["id", "initial"])
        set_header_tips(self._fg_table, [T.FG_ID, T.FG_INITIAL])
        self._fg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._fg_table.itemChanged.connect(self._on_exec_changed)
        fg_l.addWidget(self._fg_table)
        fg_btns = QHBoxLayout()
        add_fg = QPushButton(t("添加 FG"))
        tipify(add_fg, T.BTN_ADD_FG)
        add_fg.clicked.connect(self._add_fg_row)
        del_fg = QPushButton(t("删除选中"))
        tipify(del_fg, T.BTN_DEL_ROW)
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
            ["name", "function_group", "depends_on", "execution_client"]
        )
        set_header_tips(
            self._proc_table,
            [T.PROC_NAME, T.PROC_FG, T.PROC_DEPS, T.PROC_EC],
        )
        self._proc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._proc_table.itemChanged.connect(self._on_exec_changed)
        proc_l.addWidget(self._proc_table)
        proc_btns = QHBoxLayout()
        add_p = QPushButton(t("添加进程行"))
        tipify(add_p, T.BTN_ADD_PROC)
        add_p.clicked.connect(self._add_proc_row)
        del_p = QPushButton(t("删除选中"))
        tipify(del_p, T.BTN_DEL_ROW)
        del_p.clicked.connect(lambda: self._del_rows(self._proc_table, self._on_exec_changed))
        sync_p = QPushButton(t("从 wiring 同步进程名"))
        tipify(sync_p, T.BTN_SYNC_WIRING)
        sync_p.clicked.connect(self._sync_processes_from_wiring)
        proc_btns.addWidget(add_p)
        proc_btns.addWidget(del_p)
        proc_btns.addWidget(sync_p)
        proc_btns.addStretch(1)
        proc_l.addLayout(proc_btns)
        lay.addWidget(proc_box, stretch=1)
        return w

    def _build_em_launch_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel(
            t(
                "em_launch.yaml：OS EM（gf_em_daemon）二进制表。"
                "binary 相对 $GF_BUILD_DIR；与 exec.yaml 进程名对齐。"
                "args / max_restarts 不留空（默认 args=0、max_restarts=3）。"
                "args=POSIX argv（非 AP 字段，但 EM Spawn 需要；gateway 15=收满 Trajectory 退出）。"
                "PHM on_failure=restart + GF_EM_MANAGED → exit 75 后按 max_restarts relaunch。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        self._em_table = QTableWidget(0, 4)
        self._em_table.setHorizontalHeaderLabels(
            [
                "name",
                t("binary（相对 build_dir）"),
                t("args（空格/逗号）"),
                "max_restarts",
            ]
        )
        set_header_tips(
            self._em_table,
            [T.EM_NAME, T.EM_BINARY, T.EM_ARGS, T.EM_MAX_RESTARTS],
        )
        self._em_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._em_table.itemChanged.connect(self._on_em_launch_changed)
        lay.addWidget(self._em_table, stretch=1)
        btns = QHBoxLayout()
        add_e = QPushButton(t("添加行"))
        tipify(add_e, T.BTN_ADD_EM)
        add_e.clicked.connect(self._add_em_row)
        del_e = QPushButton(t("删除选中"))
        tipify(del_e, T.BTN_DEL_ROW)
        del_e.clicked.connect(lambda: self._del_rows(self._em_table, self._on_em_launch_changed))
        sync_e = QPushButton(t("从 exec 同步进程名"))
        tipify(sync_e, T.BTN_SYNC_EXEC)
        sync_e.clicked.connect(self._sync_em_from_exec)
        btns.addWidget(add_e)
        btns.addWidget(del_e)
        btns.addWidget(sync_e)
        btns.addStretch(1)
        lay.addLayout(btns)
        return w

    def _build_phm_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel(
            t(
                "phm.yaml：Alive / Deadline。process 从 wiring 选择。"
                "数值不留空（deadline_ms=0 表示不做独立 deadline）。"
                "on_failure 下拉：log | notify_sm | restart"
                "（restart：托管进程 exit 75 → EM relaunch；未托管 → soft）。"
            )
        )
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
        set_header_tips(
            self._phm_table,
            [
                T.PHM_ID,
                T.PHM_PROCESS,
                T.PHM_PERIOD,
                T.PHM_TIMEOUT,
                T.PHM_DEADLINE,
                T.PHM_ON_FAILURE,
            ],
        )
        self._phm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._phm_table.itemChanged.connect(self._on_phm_changed)
        lay.addWidget(self._phm_table, stretch=1)
        btns = QHBoxLayout()
        add_e = QPushButton(t("添加 entity"))
        tipify(add_e, T.BTN_ADD_PHM)
        add_e.clicked.connect(self._add_phm_row)
        del_e = QPushButton(t("删除选中"))
        tipify(del_e, T.BTN_DEL_ROW)
        del_e.clicked.connect(lambda: self._del_rows(self._phm_table, self._on_phm_changed))
        btns.addWidget(add_e)
        btns.addWidget(del_e)
        btns.addStretch(1)
        lay.addLayout(btns)
        return w

    def _build_diag_page(self) -> QWidget:
        # Scroll so added timing/ota blocks don't force the main window minimum height.
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        hint = QLabel(
            t(
                "diag.yaml：ISO 14229（UDS+NRC）为基础；ISO 13400 DoIP 为其传输子项（不可单独勾选）。"
                "无 DoIP 时 AP 不跑 ISO-TP，CAN 侧 PDU 交 MCU。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        std = QGroupBox(t("standards（依赖：13400 ⊂ 14229）"))
        std_l = QVBoxLayout(std)
        # Same left edge for both ISO checkboxes (no leading spaces).
        std_form = QFormLayout()
        std_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._iso_14229 = QCheckBox(t("ISO 14229 UDS（含 NRC）— 父能力"))
        tipify(self._iso_14229, T.DIAG_14229)
        self._iso_14229.toggled.connect(self._on_iso_14229_toggled)
        self._iso_13400 = QCheckBox(t("ISO 13400 DoIP — 依赖 14229"))
        tipify(self._iso_13400, T.DIAG_13400)
        self._iso_13400.toggled.connect(self._on_iso_13400_toggled)
        std_form.addRow("ISO 14229", self._iso_14229)
        std_form.addRow("ISO 13400", self._iso_13400)
        # 0x27 插件按 OEM 常换：在 GMT→OTA 配置；此处只保留 yaml 字段（加载时记住，保存时不覆盖）
        self._sec_plugin_path = ""
        plugin_hint = QLabel(
            t(
                "0x27/0x29 安全插件：在 GMT → OTA 本地记录路径；"
                "板端用环境变量 GF_DIAG_SEC_PLUGIN（本页只配诊断框架）。"
            )
        )
        plugin_hint.setWordWrap(True)
        plugin_hint.setStyleSheet("color:#666; font-size:11px;")
        std_l.addLayout(std_form)
        std_l.addWidget(plugin_hint)
        lay.addWidget(std)

        doip_shell, doip_body = _make_collapsible("doip", expanded=True)
        doip_f = QFormLayout(doip_body)
        self._doip_enabled = QCheckBox(t("enabled（与 iso_13400 同步）"))
        tipify(self._doip_enabled, T.DIAG_DOIP_EN)
        self._doip_enabled.toggled.connect(self._on_doip_enabled_toggled)
        self._doip_addr = QLineEdit()
        self._doip_addr.setPlaceholderText("0x0E00")
        tipify(self._doip_addr, T.DIAG_DOIP_ADDR)
        self._doip_addr.textChanged.connect(self._on_diag_changed)
        self._doip_tester = QLineEdit()
        self._doip_tester.setPlaceholderText("0x0E80")
        tipify(self._doip_tester, T.DIAG_DOIP_TESTER)
        self._doip_tester.textChanged.connect(self._on_diag_changed)
        self._doip_port = QSpinBox()
        self._doip_port.setRange(1, 65535)
        self._doip_port.setValue(13400)
        tipify(self._doip_port, T.DIAG_DOIP_PORT)
        self._doip_port.valueChanged.connect(self._on_diag_changed)
        doip_f.addRow("", self._doip_enabled)
        doip_f.addRow("logical_address", self._doip_addr)
        doip_f.addRow("tester_address", self._doip_tester)
        doip_f.addRow("tcp_port", self._doip_port)
        lay.addWidget(doip_shell)

        timing_shell, timing_body = _make_collapsible(
            "timing（S3 / 0x3E）", expanded=False
        )
        timing_f = QFormLayout(timing_body)
        timing_f.setSpacing(4)
        self._s3_ms = QSpinBox()
        self._s3_ms.setRange(100, 600000)
        self._s3_ms.setValue(5000)
        self._s3_ms.setSuffix(" ms")
        tipify(self._s3_ms, T.DIAG_S3)
        self._s3_ms.valueChanged.connect(self._on_diag_changed)
        self._tp_ms = QSpinBox()
        self._tp_ms.setRange(50, 300000)
        self._tp_ms.setValue(2000)
        self._tp_ms.setSuffix(" ms")
        tipify(self._tp_ms, T.DIAG_TP_PERIOD)
        self._tp_ms.valueChanged.connect(self._on_diag_changed)
        self._p2_ms = QSpinBox()
        self._p2_ms.setRange(1, 60000)
        self._p2_ms.setValue(50)
        self._p2_ms.setSuffix(" ms")
        tipify(self._p2_ms, T.DIAG_P2)
        self._p2_ms.valueChanged.connect(self._on_diag_changed)
        self._p2star_ms = QSpinBox()
        self._p2star_ms.setRange(1, 600000)
        self._p2star_ms.setValue(5000)
        self._p2star_ms.setSuffix(" ms")
        tipify(self._p2star_ms, T.DIAG_P2STAR)
        self._p2star_ms.valueChanged.connect(self._on_diag_changed)
        self._sec_delay_ms = QSpinBox()
        self._sec_delay_ms.setRange(0, 600000)
        self._sec_delay_ms.setValue(10000)
        self._sec_delay_ms.setSuffix(" ms")
        tipify(self._sec_delay_ms, T.DIAG_SEC_DELAY)
        self._sec_delay_ms.valueChanged.connect(self._on_diag_changed)
        timing_f.addRow("s3_server_ms", self._s3_ms)
        timing_f.addRow("tester_present_period_ms", self._tp_ms)
        timing_f.addRow("p2_server_ms", self._p2_ms)
        timing_f.addRow("p2_star_server_ms", self._p2star_ms)
        timing_f.addRow("security_delay_ms", self._sec_delay_ms)
        lay.addWidget(timing_shell)

        ota_shell, ota_body = _make_collapsible(
            "ota_transfer（下载 SID）", expanded=True
        )
        ota_f = QFormLayout(ota_body)
        ota_f.setSpacing(4)
        self._ota_mode = TintedComboBox()
        for key, label in _OTA_MODE_ITEMS:
            self._ota_mode.addItem(label, key)
        tipify(self._ota_mode, T.DIAG_OTA_MODE)
        style_enum_combo(
            self._ota_mode,
            {
                "request_file_transfer": ("#bbdefb", "#0d47a1"),
                "request_download": ("#c8e6c9", "#1b5e20"),
                "routine_sil": ("#ffe082", "#6d4c00"),
            },
            data_role=True,
            item_tips=T.DIAG_OTA_MODE_ITEMS,
        )
        self._ota_mode.currentIndexChanged.connect(self._on_diag_changed)
        self._ota_prog = QCheckBox(t("require ProgrammingSession"))
        tipify(self._ota_prog, T.DIAG_OTA_PROG)
        self._ota_prog.toggled.connect(self._on_diag_changed)
        self._ota_sec = QCheckBox(t("require SecurityAccess"))
        tipify(self._ota_sec, T.DIAG_OTA_SEC)
        self._ota_sec.toggled.connect(self._on_diag_changed)
        self._ota_block = QSpinBox()
        self._ota_block.setRange(8, 65535)
        self._ota_block.setValue(1024)
        tipify(self._ota_block, T.DIAG_OTA_BLOCK)
        self._ota_block.valueChanged.connect(self._on_diag_changed)
        ota_f.addRow(t("下载 SID"), self._ota_mode)
        ota_f.addRow("", self._ota_prog)
        ota_f.addRow("", self._ota_sec)
        ota_f.addRow("max_block_length", self._ota_block)
        lay.addWidget(ota_shell)

        did_box = QGroupBox("dids")
        did_l = QVBoxLayout(did_box)
        self._did_table = QTableWidget(0, 4)
        self._did_table.setHorizontalHeaderLabels(["id", "name", "access", "size"])
        set_header_tips(
            self._did_table,
            [T.DID_ID, T.DID_NAME, T.DID_ACCESS, T.DID_SIZE],
        )
        self._did_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._did_table.verticalHeader().setDefaultSectionSize(24)
        self._did_table.setMinimumHeight(72)
        self._did_table.setMaximumHeight(160)
        self._did_table.itemChanged.connect(self._on_diag_changed)
        did_l.addWidget(self._did_table)
        did_btns = QHBoxLayout()
        add_d = QPushButton(t("添加 DID"))
        tipify(add_d, T.BTN_ADD_DID)
        add_d.clicked.connect(self._add_did_row)
        del_d = QPushButton(t("删除选中"))
        tipify(del_d, T.BTN_DEL_ROW)
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
        self._rid_table.verticalHeader().setDefaultSectionSize(24)
        self._rid_table.setMinimumHeight(72)
        self._rid_table.setMaximumHeight(140)
        self._rid_table.itemChanged.connect(self._on_diag_changed)
        rid_l.addWidget(self._rid_table)
        rid_btns = QHBoxLayout()
        add_r = QPushButton(t("添加 RID"))
        add_r.clicked.connect(
            lambda: self._add_empty_row(self._rid_table, 2, self._on_diag_changed)
        )
        del_r = QPushButton(t("删除选中"))
        del_r.clicked.connect(lambda: self._del_rows(self._rid_table, self._on_diag_changed))
        rid_btns.addWidget(add_r)
        rid_btns.addWidget(del_r)
        rid_btns.addStretch(1)
        rid_l.addLayout(rid_btns)
        lay.addWidget(rid_box)
        lay.addStretch(1)

        scroll = _PlatformScrollPage(inner)
        return scroll

    def _build_log_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel(
            t("log.yaml：默认级别与 contexts（细配置在此；页 1 仅粗开关）。")
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        form = QFormLayout()
        self._log_level = TintedComboBox()
        self._log_level.addItems(_LOG_LEVELS)
        self._log_level.setCurrentText("INFO")
        tipify(self._log_level, T.LOG_DEFAULT)
        style_enum_combo(
            self._log_level, COLORS_LOG_LEVEL, item_tips=T.LOG_LEVEL_ITEMS
        )
        self._log_level.currentTextChanged.connect(self._on_log_changed)
        form.addRow("default_level", self._log_level)
        lay.addLayout(form)

        ctx_box = QGroupBox("contexts")
        ctx_l = QVBoxLayout(ctx_box)
        self._ctx_table = QTableWidget(0, 2)
        self._ctx_table.setHorizontalHeaderLabels(["id", "level"])
        set_header_tips(self._ctx_table, [T.LOG_CTX_ID, T.LOG_CTX_LEVEL])
        self._ctx_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ctx_table.itemChanged.connect(self._on_log_changed)
        ctx_l.addWidget(self._ctx_table)
        ctx_btns = QHBoxLayout()
        add_c = QPushButton(t("添加 context"))
        tipify(add_c, T.BTN_ADD_CTX)
        add_c.clicked.connect(self._add_log_ctx_row)
        del_c = QPushButton(t("删除选中"))
        tipify(del_c, T.BTN_DEL_ROW)
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
        hint = QLabel(
            t(
                "ucm.yaml：配置 SIL OTA 编排参数（不是刷写包本身）。"
                "流程：GMT/DoIP 下发 → OtaOrchestrator 把目标功能组切到 Updating → "
                "PackageManager 状态机 → Collector 记结果；失败可回滚。"
                "真板 RAUC 刷写仍为 stub（P3z）。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        form = QFormLayout()
        self._ucm_enabled = QCheckBox(t("启用 OTA 编排"))
        tipify(self._ucm_enabled, T.UCM_ENABLED)
        self._ucm_enabled.toggled.connect(self._on_ucm_changed)
        self._ucm_source = QLineEdit()
        self._ucm_source.setPlaceholderText("sil://artifact")
        tipify(self._ucm_source, T.UCM_SOURCE)
        self._ucm_source.textChanged.connect(self._on_ucm_changed)
        self._ucm_fg = QComboBox()
        tipify(self._ucm_fg, T.UCM_FG)
        self._ucm_fg.currentTextChanged.connect(self._on_ucm_changed)
        self._ucm_rollback = QCheckBox(t("失败时允许回滚"))
        tipify(self._ucm_rollback, T.UCM_ROLLBACK)
        self._ucm_rollback.toggled.connect(self._on_ucm_changed)
        form.addRow("", self._ucm_enabled)
        form.addRow(t("包 / 清单 URI"), self._ucm_source)
        form.addRow(t("目标功能组"), self._ucm_fg)
        form.addRow("", self._ucm_rollback)
        lay.addLayout(form)
        lay.addStretch(1)
        return w

    def _build_collector_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel(
            t(
                "collector.yaml：Event Collector 最小集。"
                "有 MCU CP → forward=cp_dem；否则 local_store（DEM-lite）。"
                "不做 Classic DEM 全编辑器。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        form = QFormLayout()
        self._col_forward = TintedComboBox()
        self._col_forward.addItems(_FORWARD_MODES)
        tipify(self._col_forward, T.COL_FORWARD)
        style_enum_combo(
            self._col_forward, COLORS_FORWARD, item_tips=T.COL_FORWARD_ITEMS
        )
        self._col_forward.currentTextChanged.connect(self._on_collector_changed)
        form.addRow("forward", self._col_forward)
        lay.addLayout(form)

        src_box = QGroupBox("sources")
        src_l = QHBoxLayout(src_box)
        for name in _COLLECTOR_SOURCES:
            cb = QCheckBox(name)
            tipify(cb, T.COL_SOURCE)
            cb.toggled.connect(self._on_collector_changed)
            self._src_boxes[name] = cb
            src_l.addWidget(cb)
        src_l.addStretch(1)
        lay.addWidget(src_box)

        local = QGroupBox(t("local（DEM-lite 落盘）"))
        local_f = QFormLayout(local)
        self._col_local_en = QCheckBox("enabled")
        tipify(self._col_local_en, T.COL_LOCAL_EN)
        self._col_local_en.toggled.connect(self._on_collector_changed)
        self._col_max = QSpinBox()
        self._col_max.setRange(1, 100000)
        self._col_max.setValue(256)
        tipify(self._col_max, T.COL_MAX)
        self._col_max.valueChanged.connect(self._on_collector_changed)
        local_f.addRow("", self._col_local_en)
        local_f.addRow("max_entries", self._col_max)
        lay.addWidget(local)
        lay.addStretch(1)
        return w

    # ── session ───────────────────────────────────────────

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        if session is None:
            return
        self._loading = True
        selected = set(str(x) for x in (session.req.get("runtime_modules") or []))
        selected |= ALWAYS_ON_MODULES
        for name, cb in self._module_boxes.items():
            if name in ALWAYS_ON_MODULES:
                cb.setChecked(True)
            else:
                cb.setChecked(name in selected)
        self._modules = set(selected)
        merged = self.selected_modules()
        if set(session.req.get("runtime_modules") or []) != set(merged):
            session.req["runtime_modules"] = merged
            session.dirty_req = True
        self._load_exec(session.platform.get("exec") or {})
        self._load_em_launch(session.platform.get("em_launch") or {})
        self._load_phm(session.platform.get("phm") or {})
        self._load_diag(session.platform.get("diag") or {})
        self._load_log(session.platform.get("log") or {})
        self._load_ucm(session.platform.get("ucm") or {})
        self._load_collector(session.platform.get("collector") or {})
        self._loading = False
        self._rebuild_nav()

    def selected_modules(self) -> list[str]:
        # Preserve KNOWN_MODULES order; always-on forced in.
        out: list[str] = []
        for n in KNOWN_MODULES:
            cb = self._module_boxes[n]
            if n in ALWAYS_ON_MODULES or cb.isChecked():
                out.append(n)
        return out

    def _on_modules_toggled(self, *_args: object) -> None:
        if self._loading or not self._session:
            return
        modules = self.selected_modules()
        self._session.req["runtime_modules"] = modules
        self._session.dirty_req = True
        self._modules = set(modules)
        self._rebuild_nav()
        self.changed.emit()

    def set_runtime_modules(self, modules: list[str]) -> None:
        """Compatibility: sync checkboxes if external code still calls this."""
        self._loading = True
        sel = {str(m) for m in modules} | ALWAYS_ON_MODULES
        for name, cb in self._module_boxes.items():
            if name in ALWAYS_ON_MODULES:
                cb.setChecked(True)
            else:
                cb.setChecked(name in sel)
        self._loading = False
        self._modules = sel
        self._rebuild_nav()

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

    def refresh_process_lists(self) -> None:
        """Call after wiring process set may have changed (optional UX)."""
        return

    def _process_names(self) -> list[str]:
        if not self._session:
            return []
        return self._session.wiring_process_names(include_external=False)

    def _fg_ids(self) -> list[str]:
        ids = [
            _cell(self._fg_table, r, 0)
            for r in range(self._fg_table.rowCount())
            if _cell(self._fg_table, r, 0)
        ]
        return ids or ["MachineFG"]

    def _default_fg(self) -> str:
        ids = self._fg_ids()
        return ids[0] if ids else "MachineFG"

    def _proc_names_in_table(self) -> list[str]:
        out: list[str] = []
        for r in range(self._proc_table.rowCount()):
            n = _combo_text(self._proc_table, r, 0)
            if n:
                out.append(n)
        return out

    def _deps_candidates_for_row(self, row: int) -> list[str]:
        self_name = _combo_text(self._proc_table, row, 0)
        names = self._proc_names_in_table() or self._process_names()
        return [n for n in names if n and n != self_name]

    def _fill_proc_row(
        self,
        r: int,
        *,
        name: str,
        fg: str,
        deps: list[str],
        execution_client: bool,
    ) -> None:
        names = self._process_names() or ([name] if name else ["process.name"])
        _set_combo(
            self._proc_table,
            r,
            0,
            names,
            name,
            self._on_exec_changed,
            tip=T.PROC_NAME,
        )
        _set_combo(
            self._proc_table,
            r,
            1,
            self._fg_ids(),
            fg or self._default_fg(),
            self._on_exec_changed,
            tip=T.PROC_FG,
        )
        set_multi_check(
            self._proc_table,
            r,
            2,
            [str(x) for x in deps],
            lambda row=r: self._deps_candidates_for_row(row),
            self._on_exec_changed,
            tip=T.PROC_DEPS,
            empty_label=t("（无依赖）"),
            title="选择 depends_on",
        )
        _set_combo(
            self._proc_table,
            r,
            3,
            _BOOL_TF,
            "true" if execution_client else "false",
            self._on_exec_changed,
            tip=T.PROC_EC,
            bool_style=True,
            item_tips=T.PROC_EC_ITEMS,
        )

    def _fill_em_row(
        self, r: int, *, name: str, binary: str, args_s: str, mr_s: str
    ) -> None:
        names = self._process_names() or ([name] if name else ["process.name"])
        _set_combo(
            self._em_table,
            r,
            0,
            names,
            name,
            self._on_em_launch_changed,
            tip=T.EM_NAME,
        )
        _set_cell(self._em_table, r, 1, binary, T.EM_BINARY)
        _set_cell(self._em_table, r, 2, args_s, T.EM_ARGS)
        _set_cell(self._em_table, r, 3, mr_s, T.EM_MAX_RESTARTS)

    def _fill_phm_row(
        self,
        r: int,
        *,
        eid: str,
        process: str,
        period: str,
        timeout: str,
        deadline: str,
        on_failure: str,
    ) -> None:
        names = self._process_names() or ([process] if process else ["process.name"])
        _set_cell(self._phm_table, r, 0, eid, T.PHM_ID)
        _set_combo(
            self._phm_table,
            r,
            1,
            names,
            process,
            self._on_phm_changed,
            tip=T.PHM_PROCESS,
        )
        _set_cell(self._phm_table, r, 2, period, T.PHM_PERIOD)
        _set_cell(self._phm_table, r, 3, timeout, T.PHM_TIMEOUT)
        _set_cell(self._phm_table, r, 4, deadline, T.PHM_DEADLINE)
        onf = on_failure if on_failure in _PHM_ON_FAILURE else "log"
        _set_combo(
            self._phm_table,
            r,
            5,
            _PHM_ON_FAILURE,
            onf,
            self._on_phm_changed,
            tip=T.PHM_ON_FAILURE,
            enum_colors=COLORS_ON_FAILURE,
            item_tips=T.PHM_ON_FAILURE_ITEMS,
        )

    def _refresh_ucm_fg_combo(self, current: str | None = None) -> None:
        want = current if current is not None else self._ucm_fg.currentText()
        ids = self._fg_ids()
        self._ucm_fg.blockSignals(True)
        self._ucm_fg.clear()
        self._ucm_fg.addItems(ids)
        if want in ids:
            self._ucm_fg.setCurrentText(want)
        elif ids:
            self._ucm_fg.setCurrentIndex(0)
        self._ucm_fg.blockSignals(False)

    def _refresh_proc_fg_options(self) -> None:
        ids = self._fg_ids()
        for r in range(self._proc_table.rowCount()):
            w = self._proc_table.cellWidget(r, 1)
            if not isinstance(w, QComboBox):
                continue
            cur = w.currentText()
            w.blockSignals(True)
            w.clear()
            w.addItems(ids)
            if cur in ids:
                w.setCurrentText(cur)
            elif ids:
                w.setCurrentIndex(0)
            w.blockSignals(False)

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
            _set_cell(self._fg_table, r, 0, str(fg.get("id") or ""), T.FG_ID)
            _set_combo(
                self._fg_table,
                r,
                1,
                _FG_INITIAL,
                str(fg.get("initial") or "Running"),
                self._on_exec_changed,
                tip=T.FG_INITIAL,
                enum_colors=COLORS_FG_INITIAL,
                item_tips=T.FG_INITIAL_ITEMS,
            )
        self._proc_table.setRowCount(0)
        for p in data.get("processes") or []:
            if not isinstance(p, dict):
                continue
            r = self._proc_table.rowCount()
            self._proc_table.insertRow(r)
            deps = p.get("depends_on") or []
            if not isinstance(deps, list):
                deps = []
            self._fill_proc_row(
                r,
                name=str(p.get("name") or ""),
                fg=str(p.get("function_group") or ""),
                deps=[str(x) for x in deps],
                execution_client=bool(p.get("execution_client", True)),
            )
        self._fg_table.blockSignals(False)
        self._proc_table.blockSignals(False)
        self._refresh_ucm_fg_combo()

    def _load_em_launch(self, data: dict[str, Any]) -> None:
        self._em_table.blockSignals(True)
        self._em_table.setRowCount(0)
        for p in data.get("processes") or []:
            if not isinstance(p, dict):
                continue
            r = self._em_table.rowCount()
            self._em_table.insertRow(r)
            args = p.get("args")
            if isinstance(args, list):
                args_s = ", ".join(str(x) for x in args)
            elif args is None:
                args_s = ""
            else:
                args_s = str(args)
            if not args_s.strip():
                args_s = _DEFAULT_EM_ARGS
            mr = p.get("max_restarts")
            if mr is None or mr == "":
                mr_s = str(_DEFAULT_MAX_RESTARTS)
            else:
                mr_s = str(mr)
            self._fill_em_row(
                r,
                name=str(p.get("name") or ""),
                binary=str(p.get("binary") or ""),
                args_s=args_s,
                mr_s=mr_s,
            )
        self._em_table.blockSignals(False)

    def _load_phm(self, data: dict[str, Any]) -> None:
        self._phm_table.blockSignals(True)
        self._phm_table.setRowCount(0)
        for e in data.get("entities") or []:
            if not isinstance(e, dict):
                continue
            r = self._phm_table.rowCount()
            self._phm_table.insertRow(r)
            dl = e.get("deadline_ms")
            if dl is None or dl == "":
                dl_s = str(_DEFAULT_DEADLINE_MS)
            else:
                dl_s = str(dl)
            self._fill_phm_row(
                r,
                eid=str(e.get("id") or ""),
                process=str(e.get("process") or ""),
                period=str(e.get("alive_period_ms", _DEFAULT_ALIVE_PERIOD_MS)),
                timeout=str(e.get("alive_timeout_ms", _DEFAULT_ALIVE_TIMEOUT_MS)),
                deadline=dl_s,
                on_failure=str(e.get("on_failure") or "log"),
            )
        self._phm_table.blockSignals(False)

    def _load_diag(self, data: dict[str, Any]) -> None:
        doip = data.get("doip") if isinstance(data.get("doip"), dict) else {}
        standards = data.get("standards") if isinstance(data.get("standards"), dict) else {}
        security = data.get("security") if isinstance(data.get("security"), dict) else {}
        iso14229 = bool(standards.get("iso_14229_uds", True))
        iso13400 = bool(standards.get("iso_13400_doip", doip.get("enabled", False)))
        if iso13400 and not iso14229:
            iso14229 = True
        self._iso_14229.blockSignals(True)
        self._iso_13400.blockSignals(True)
        self._doip_enabled.blockSignals(True)
        self._doip_addr.blockSignals(True)
        self._doip_tester.blockSignals(True)
        self._doip_port.blockSignals(True)
        self._s3_ms.blockSignals(True)
        self._tp_ms.blockSignals(True)
        self._p2_ms.blockSignals(True)
        self._p2star_ms.blockSignals(True)
        self._sec_delay_ms.blockSignals(True)
        self._ota_mode.blockSignals(True)
        self._ota_prog.blockSignals(True)
        self._ota_sec.blockSignals(True)
        self._ota_block.blockSignals(True)
        self._iso_14229.setChecked(iso14229)
        self._iso_13400.setChecked(iso13400 and iso14229)
        self._iso_13400.setEnabled(iso14229)
        self._doip_enabled.setChecked(iso13400 and iso14229)
        self._sec_plugin_path = str(security.get("plugin") or "")
        addr = doip.get("logical_address", "0x0E00")
        if isinstance(addr, int):
            self._doip_addr.setText(hex(addr))
        else:
            self._doip_addr.setText(str(addr or "0x0E00"))
        tester = doip.get("tester_address", "0x0E80")
        if isinstance(tester, int):
            self._doip_tester.setText(hex(tester))
        else:
            self._doip_tester.setText(str(tester or "0x0E80"))
        try:
            self._doip_port.setValue(int(doip.get("tcp_port") or 13400))
        except (TypeError, ValueError):
            self._doip_port.setValue(13400)
        timing = data.get("timing") if isinstance(data.get("timing"), dict) else {}
        xfer = data.get("ota_transfer") if isinstance(data.get("ota_transfer"), dict) else {}
        try:
            self._s3_ms.setValue(int(timing.get("s3_server_ms") or 5000))
            self._tp_ms.setValue(int(timing.get("tester_present_period_ms") or 2000))
            self._p2_ms.setValue(int(timing.get("p2_server_ms") or 50))
            self._p2star_ms.setValue(int(timing.get("p2_star_server_ms") or 5000))
            self._sec_delay_ms.setValue(int(timing.get("security_delay_ms") or 10000))
        except (TypeError, ValueError):
            pass
        mode = str(xfer.get("mode") or "request_file_transfer")
        idx = self._ota_mode.findData(mode)
        if idx < 0:
            idx = self._ota_mode.findText(mode)
        self._ota_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self._ota_prog.setChecked(bool(xfer.get("require_programming_session", True)))
        self._ota_sec.setChecked(bool(xfer.get("require_security", True)))
        try:
            self._ota_block.setValue(int(xfer.get("max_block_length") or 1024))
        except (TypeError, ValueError):
            self._ota_block.setValue(1024)
        self._iso_14229.blockSignals(False)
        self._iso_13400.blockSignals(False)
        self._doip_enabled.blockSignals(False)
        self._doip_addr.blockSignals(False)
        self._doip_tester.blockSignals(False)
        self._doip_port.blockSignals(False)
        self._s3_ms.blockSignals(False)
        self._tp_ms.blockSignals(False)
        self._p2_ms.blockSignals(False)
        self._p2star_ms.blockSignals(False)
        self._sec_delay_ms.blockSignals(False)
        self._ota_mode.blockSignals(False)
        self._ota_prog.blockSignals(False)
        self._ota_sec.blockSignals(False)
        self._ota_block.blockSignals(False)
        refresh_enum_combo_style(self._ota_mode)

        self._did_table.blockSignals(True)
        self._did_table.setRowCount(0)
        for d in data.get("dids") or []:
            if not isinstance(d, dict):
                continue
            r = self._did_table.rowCount()
            self._did_table.insertRow(r)
            did = d.get("id", "")
            _set_cell(
                self._did_table,
                r,
                0,
                hex(did) if isinstance(did, int) else str(did),
                T.DID_ID,
            )
            _set_cell(self._did_table, r, 1, str(d.get("name") or ""), T.DID_NAME)
            access = str(d.get("access") or "read")
            if access not in _DID_ACCESS:
                access = "read"
            _set_combo(
                self._did_table,
                r,
                2,
                _DID_ACCESS,
                access,
                self._on_diag_changed,
                tip=T.DID_ACCESS,
                enum_colors=COLORS_DID_ACCESS,
                item_tips=T.DID_ACCESS_ITEMS,
            )
            _set_cell(
                self._did_table,
                r,
                3,
                str(d.get("size") if d.get("size") is not None else "0"),
                T.DID_SIZE,
            )
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
        refresh_enum_combo_style(self._log_level)
        self._ctx_table.blockSignals(True)
        self._ctx_table.setRowCount(0)
        for c in data.get("contexts") or []:
            if not isinstance(c, dict):
                continue
            r = self._ctx_table.rowCount()
            self._ctx_table.insertRow(r)
            _set_cell(self._ctx_table, r, 0, str(c.get("id") or ""), T.LOG_CTX_ID)
            level = str(c.get("level") or "INFO")
            if level not in _LOG_LEVELS:
                level = "INFO"
            _set_combo(
                self._ctx_table,
                r,
                1,
                _LOG_LEVELS,
                level,
                self._on_log_changed,
                tip=T.LOG_CTX_LEVEL,
                enum_colors=COLORS_LOG_LEVEL,
                item_tips=T.LOG_LEVEL_ITEMS,
            )
        self._ctx_table.blockSignals(False)

    def _load_ucm(self, data: dict[str, Any]) -> None:
        self._ucm_enabled.blockSignals(True)
        self._ucm_source.blockSignals(True)
        self._ucm_rollback.blockSignals(True)
        self._ucm_enabled.setChecked(bool(data.get("enabled", False)))
        self._ucm_source.setText(str(data.get("package_source") or ""))
        self._refresh_ucm_fg_combo(str(data.get("function_group") or "MachineFG"))
        self._ucm_rollback.setChecked(bool(data.get("allow_rollback", True)))
        self._ucm_enabled.blockSignals(False)
        self._ucm_source.blockSignals(False)
        self._ucm_rollback.blockSignals(False)

    def _load_collector(self, data: dict[str, Any]) -> None:
        fwd = str(data.get("forward") or "local_store")
        idx = self._col_forward.findText(fwd)
        self._col_forward.blockSignals(True)
        self._col_forward.setCurrentIndex(idx if idx >= 0 else 0)
        self._col_forward.blockSignals(False)
        refresh_enum_combo_style(self._col_forward)
        srcs = {str(x) for x in (data.get("sources") or [])}
        for name, cb in self._src_boxes.items():
            cb.blockSignals(True)
            cb.setChecked(name in srcs if srcs else name in ("phm", "process", "com"))
            cb.blockSignals(False)
        local = data.get("local") if isinstance(data.get("local"), dict) else {}
        self._col_local_en.blockSignals(True)
        self._col_max.blockSignals(True)
        self._col_local_en.setChecked(bool(local.get("enabled", True)))
        try:
            self._col_max.setValue(int(local.get("max_entries") or 256))
        except (TypeError, ValueError):
            self._col_max.setValue(256)
        self._col_local_en.blockSignals(False)
        self._col_max.blockSignals(False)

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
            initial = _combo_text(self._fg_table, r, 1) or "Running"
            if initial not in _FG_INITIAL:
                initial = "Running"
            fgs.append({"id": fid, "initial": initial})
        procs: list[dict[str, Any]] = []
        for r in range(self._proc_table.rowCount()):
            name = _combo_text(self._proc_table, r, 0)
            if not name:
                continue
            deps = multi_selected(self._proc_table, r, 2)
            ec_s = (_combo_text(self._proc_table, r, 3) or "true").lower()
            ec = ec_s not in ("false", "0", "no")
            procs.append(
                {
                    "name": name,
                    "function_group": _combo_text(self._proc_table, r, 1)
                    or self._default_fg(),
                    "depends_on": deps,
                    "execution_client": ec,
                }
            )
        data = self._session.platform.setdefault("exec", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["function_groups"] = fgs
        data["processes"] = procs
        self._refresh_proc_fg_options()
        self._refresh_ucm_fg_combo()
        self._mark("exec")

    def _on_em_launch_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        procs: list[dict[str, Any]] = []
        for r in range(self._em_table.rowCount()):
            name = _combo_text(self._em_table, r, 0)
            binary = _cell(self._em_table, r, 1)
            if not name:
                continue
            args_raw = _cell(self._em_table, r, 2).replace(",", " ")
            args = [x for x in args_raw.split() if x]
            if not args:
                args = [_DEFAULT_EM_ARGS]
            entry: dict[str, Any] = {
                "name": name,
                "binary": binary,
                "args": args,
            }
            mr_s = _cell(self._em_table, r, 3)
            try:
                entry["max_restarts"] = int(mr_s, 0) if mr_s else _DEFAULT_MAX_RESTARTS
            except ValueError:
                entry["max_restarts"] = _DEFAULT_MAX_RESTARTS
            procs.append(entry)
        data = self._session.platform.setdefault("em_launch", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["processes"] = procs
        self._mark("em_launch")

    def _on_phm_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        entities: list[dict[str, Any]] = []
        for r in range(self._phm_table.rowCount()):
            eid = _cell(self._phm_table, r, 0)
            if not eid:
                continue
            period = _int_or_default(
                _cell(self._phm_table, r, 2), _DEFAULT_ALIVE_PERIOD_MS
            )
            timeout = _int_or_default(
                _cell(self._phm_table, r, 3), _DEFAULT_ALIVE_TIMEOUT_MS
            )
            deadline = _int_or_default(
                _cell(self._phm_table, r, 4), _DEFAULT_DEADLINE_MS
            )
            onf = _combo_text(self._phm_table, r, 5) or "log"
            if onf not in _PHM_ON_FAILURE:
                onf = "log"
            entities.append(
                {
                    "id": eid,
                    "process": _combo_text(self._phm_table, r, 1),
                    "alive_period_ms": period,
                    "alive_timeout_ms": timeout,
                    "deadline_ms": deadline,
                    "on_failure": onf,
                }
            )
        data = self._session.platform.setdefault("phm", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["entities"] = entities
        self._mark("phm")

    def _on_iso_14229_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if not checked:
            self._iso_13400.blockSignals(True)
            self._doip_enabled.blockSignals(True)
            self._iso_13400.setChecked(False)
            self._doip_enabled.setChecked(False)
            self._iso_13400.blockSignals(False)
            self._doip_enabled.blockSignals(False)
        self._iso_13400.setEnabled(checked)
        self._on_diag_changed()

    def _on_iso_13400_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if checked and not self._iso_14229.isChecked():
            self._iso_14229.blockSignals(True)
            self._iso_14229.setChecked(True)
            self._iso_14229.blockSignals(False)
            self._iso_13400.setEnabled(True)
        self._doip_enabled.blockSignals(True)
        self._doip_enabled.setChecked(checked)
        self._doip_enabled.blockSignals(False)
        self._on_diag_changed()

    def _on_doip_enabled_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if checked and not self._iso_14229.isChecked():
            self._iso_14229.blockSignals(True)
            self._iso_14229.setChecked(True)
            self._iso_14229.blockSignals(False)
        self._iso_13400.blockSignals(True)
        self._iso_13400.setChecked(checked)
        self._iso_13400.blockSignals(False)
        self._iso_13400.setEnabled(self._iso_14229.isChecked())
        self._on_diag_changed()

    def _on_diag_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        try:
            addr = _int_or_none(self._doip_addr.text())
            if addr is None:
                addr = 0x0E00
        except ValueError:
            addr = 0x0E00
        try:
            tester = _int_or_none(self._doip_tester.text())
            if tester is None:
                tester = 0x0E80
        except ValueError:
            tester = 0x0E80
        dids: list[dict[str, Any]] = []
        for r in range(self._did_table.rowCount()):
            did = _cell(self._did_table, r, 0)
            if not did:
                continue
            access = _combo_text(self._did_table, r, 2) or "read"
            if access not in _DID_ACCESS:
                access = "read"
            entry: dict[str, Any] = {
                "id": did,
                "name": _cell(self._did_table, r, 1),
                "access": access,
            }
            size_s = _cell(self._did_table, r, 3) or "0"
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
        iso14229 = self._iso_14229.isChecked()
        iso13400 = self._iso_13400.isChecked() and iso14229
        data = self._session.platform.setdefault("diag", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["standards"] = {
            "iso_14229_uds": iso14229,
            "iso_13400_doip": iso13400,
        }
        # 保留 GMT OTA 写入的 plugin 路径，本页不编辑
        data["security"] = {"plugin": getattr(self, "_sec_plugin_path", "") or ""}
        data["doip"] = {
            "enabled": iso13400,
            "logical_address": addr,
            "tester_address": tester,
            "tcp_port": int(self._doip_port.value()),
        }
        data["timing"] = {
            "s3_server_ms": int(self._s3_ms.value()),
            "tester_present_period_ms": int(self._tp_ms.value()),
            "p2_server_ms": int(self._p2_ms.value()),
            "p2_star_server_ms": int(self._p2star_ms.value()),
            "security_delay_ms": int(self._sec_delay_ms.value()),
        }
        data["ota_transfer"] = {
            "mode": str(
                self._ota_mode.currentData() or "request_file_transfer"
            ),
            "require_programming_session": self._ota_prog.isChecked(),
            "require_security": self._ota_sec.isChecked(),
            "max_block_length": int(self._ota_block.value()),
        }
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
            level = _combo_text(self._ctx_table, r, 1) or "INFO"
            if level not in _LOG_LEVELS:
                level = "INFO"
            contexts.append({"id": cid, "level": level})
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
        data["function_group"] = self._ucm_fg.currentText().strip() or "MachineFG"
        data["allow_rollback"] = self._ucm_rollback.isChecked()
        self._mark("ucm")

    def _on_collector_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        data = self._session.platform.setdefault("collector", {"schema_version": "0.1"})
        data["schema_version"] = data.get("schema_version") or "0.1"
        data["forward"] = self._col_forward.currentText().strip() or "local_store"
        data["sources"] = [n for n, cb in self._src_boxes.items() if cb.isChecked()]
        data["local"] = {
            "enabled": self._col_local_en.isChecked(),
            "max_entries": int(self._col_max.value()),
        }
        self._mark("collector")

    # ── row helpers ───────────────────────────────────────

    def _add_fg_row(self) -> None:
        self._fg_table.blockSignals(True)
        r = self._fg_table.rowCount()
        self._fg_table.insertRow(r)
        _set_cell(self._fg_table, r, 0, f"FG{r + 1}", T.FG_ID)
        _set_combo(
            self._fg_table,
            r,
            1,
            _FG_INITIAL,
            "Running",
            self._on_exec_changed,
            tip=T.FG_INITIAL,
            enum_colors=COLORS_FG_INITIAL,
            item_tips=T.FG_INITIAL_ITEMS,
        )
        self._fg_table.blockSignals(False)
        self._on_exec_changed()

    def _add_proc_row(self) -> None:
        names = self._process_names()
        used = {
            _combo_text(self._proc_table, r, 0)
            for r in range(self._proc_table.rowCount())
        }
        pick = next(
            (n for n in names if n not in used),
            names[0] if names else "process.name",
        )
        self._proc_table.blockSignals(True)
        r = self._proc_table.rowCount()
        self._proc_table.insertRow(r)
        self._fill_proc_row(
            r,
            name=pick,
            fg=self._default_fg(),
            deps=[],
            execution_client=True,
        )
        self._proc_table.blockSignals(False)
        self._on_exec_changed()

    def _sync_processes_from_wiring(self) -> None:
        if not self._session:
            return
        names = self._process_names()
        if not names:
            QMessageBox.information(self, "同步", "wiring 中没有非 external 进程。")
            return
        existing: dict[str, tuple[str, list[str], bool]] = {}
        for r in range(self._proc_table.rowCount()):
            name = _combo_text(self._proc_table, r, 0)
            if name:
                ec = (_combo_text(self._proc_table, r, 3) or "true").lower() != "false"
                existing[name] = (
                    _combo_text(self._proc_table, r, 1),
                    multi_selected(self._proc_table, r, 2),
                    ec,
                )
        self._proc_table.blockSignals(True)
        self._proc_table.setRowCount(0)
        fg = self._default_fg()
        for name in names:
            r = self._proc_table.rowCount()
            self._proc_table.insertRow(r)
            old = existing.get(name)
            self._fill_proc_row(
                r,
                name=name,
                fg=old[0] if old else fg,
                deps=old[1] if old else [],
                execution_client=old[2] if old else True,
            )
        self._proc_table.blockSignals(False)
        self._on_exec_changed()

    def _add_em_row(self) -> None:
        names = self._process_names()
        used = {
            _combo_text(self._em_table, r, 0)
            for r in range(self._em_table.rowCount())
        }
        pick = next(
            (n for n in names if n not in used),
            names[0] if names else "process.name",
        )
        self._em_table.blockSignals(True)
        r = self._em_table.rowCount()
        self._em_table.insertRow(r)
        self._fill_em_row(
            r,
            name=pick,
            binary="",
            args_s=_DEFAULT_EM_ARGS,
            mr_s=str(_DEFAULT_MAX_RESTARTS),
        )
        self._em_table.blockSignals(False)
        self._on_em_launch_changed()

    def _sync_em_from_exec(self) -> None:
        if not self._session:
            return
        exec_data = self._session.platform.get("exec") or {}
        names = [
            str(p.get("name") or "").strip()
            for p in (exec_data.get("processes") or [])
            if isinstance(p, dict) and p.get("name")
        ]
        if not names:
            names = self._process_names()
        if not names:
            QMessageBox.information(self, "同步", "exec / wiring 中没有可同步的进程名。")
            return
        existing: dict[str, tuple[str, str, str]] = {}
        for r in range(self._em_table.rowCount()):
            name = _combo_text(self._em_table, r, 0)
            if name:
                existing[name] = (
                    _cell(self._em_table, r, 1),
                    _cell(self._em_table, r, 2),
                    _cell(self._em_table, r, 3),
                )
        self._em_table.blockSignals(True)
        self._em_table.setRowCount(0)
        for name in names:
            r = self._em_table.rowCount()
            self._em_table.insertRow(r)
            old = existing.get(name)
            self._fill_em_row(
                r,
                name=name,
                binary=old[0] if old else "",
                args_s=(old[1] if old else "") or _DEFAULT_EM_ARGS,
                mr_s=(old[2] if old else "") or str(_DEFAULT_MAX_RESTARTS),
            )
        self._em_table.blockSignals(False)
        self._on_em_launch_changed()

    def _add_phm_row(self) -> None:
        names = self._process_names()
        pick = names[0] if names else "process.name"
        self._phm_table.blockSignals(True)
        r = self._phm_table.rowCount()
        self._phm_table.insertRow(r)
        self._fill_phm_row(
            r,
            eid=f"{pick.split('.')[-1]}_alive",
            process=pick,
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

    def _add_log_ctx_row(self) -> None:
        self._ctx_table.blockSignals(True)
        r = self._ctx_table.rowCount()
        self._ctx_table.insertRow(r)
        _set_cell(self._ctx_table, r, 0, f"ctx{r + 1}", T.LOG_CTX_ID)
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

    def _del_rows(self, table: QTableWidget, on_change: Callable[..., None]) -> None:
        rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        table.blockSignals(True)
        for r in rows:
            table.removeRow(r)
        table.blockSignals(False)
        on_change()
