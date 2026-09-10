"""Platform tab page builders (UI construction only)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gf_codegen.compose.mem_budget import (
    C_DEBOUNCE_ENTRY,
    C_DLT_CTX,
    C_EVENT_RECORD,
    C_PER_KEY_OH,
)
from gf_config.gui import tips as T
from gf_config.gui.ara_constants import (
    _COLLECTOR_SOURCES,
    _FORWARD_MODES,
    _LOG_LEVELS,
    _OTA_MODE_ITEMS,
)
from gf_config.gui.ara_widgets import (
    _PlatformScrollPage,
    _make_collapsible,
)
from gf_config.gui.field_ux import (
    COLORS_FORWARD,
    COLORS_LOG_LEVEL,
    TintedComboBox,
    bind_dirty_spin,
    enable_table_row_selection,
    set_header_tips,
    style_enum_combo,
    tipify,
)
from gf_config.i18n import t


class AraPagesMixin:
    """Mixin: ``_build_*_page`` constructors for AraCfgEditor."""

    def _build_exec_page(self) -> QWidget:
        w = QWidget(self)
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
        self._fg_table = QTableWidget(0, 4)
        self._fg_table.setHorizontalHeaderLabels(["id", "kind", "initial", "states"])
        set_header_tips(self._fg_table, [T.FG_ID, T.FG_KIND, T.FG_INITIAL, T.FG_STATES])
        self._fg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # FG rows are few; cap height so processes (often many) keep most of the page.
        self._fg_table.setMinimumHeight(72)
        self._fg_table.setMaximumHeight(128)
        self._fg_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
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
        fg_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        lay.addWidget(fg_box, stretch=0)

        proc_box = QGroupBox("processes")
        proc_l = QVBoxLayout(proc_box)
        self._proc_table = QTableWidget(0, 5)
        self._proc_table.setHorizontalHeaderLabels(
            ["name", "function_group", "depends_on", "active_in", "execution_client"]
        )
        set_header_tips(
            self._proc_table,
            [T.PROC_NAME, T.PROC_FG, T.PROC_DEPS, T.PROC_ACTIVE_IN, T.PROC_EC],
        )
        self._proc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._proc_table.itemChanged.connect(self._on_exec_changed)
        proc_l.addWidget(self._proc_table)
        proc_btns = QHBoxLayout()
        add_p = QPushButton(t("添加进程行"))
        tipify(add_p, T.BTN_ADD_PROC)
        add_p.clicked.connect(self._add_proc_row)
        del_p = QPushButton(t("删除选中"))
        tipify(del_p, T.BTN_DEL_PROC)
        del_p.clicked.connect(self._del_proc_rows)
        proc_btns.addWidget(add_p)
        proc_btns.addWidget(del_p)
        proc_btns.addStretch(1)
        proc_l.addLayout(proc_btns)
        lay.addWidget(proc_box, stretch=1)
        return w

    def _build_em_launch_page(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        hint = QLabel(
            t(
                "em_launch.yaml：EM Spawn 表（binary / args / max_restarts）。"
                "进程名来自 wiring（及能力允许的 host.*）；与 exec.yaml 只共享名字，"
                "成员集合互不强制对齐。binary 相对 $GF_BUILD_DIR。"
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
        tipify(del_e, T.BTN_DEL_EM)
        del_e.clicked.connect(self._del_em_rows)
        btns.addWidget(add_e)
        btns.addWidget(del_e)
        btns.addStretch(1)
        lay.addLayout(btns)
        return w

    def _build_phm_page(self) -> QWidget:
        w = QWidget(self)
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
        inner = QWidget(self)
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

        doip_shell, doip_body = _make_collapsible(
            "doip", expanded=True, parent=inner
        )
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
        bind_dirty_spin(self._doip_port)
        tipify(self._doip_port, T.DIAG_DOIP_PORT)
        self._doip_port.valueChanged.connect(self._on_diag_changed)
        doip_f.addRow("", self._doip_enabled)
        doip_f.addRow("logical_address", self._doip_addr)
        doip_f.addRow("tester_address", self._doip_tester)
        doip_f.addRow("tcp_port", self._doip_port)
        lay.addWidget(doip_shell)

        timing_shell, timing_body = _make_collapsible(
            "timing（S3 / 0x3E）", expanded=False, parent=inner
        )
        timing_f = QFormLayout(timing_body)
        timing_f.setSpacing(4)
        self._s3_ms = QSpinBox()
        self._s3_ms.setRange(100, 600000)
        self._s3_ms.setValue(5000)
        bind_dirty_spin(self._s3_ms)
        self._s3_ms.setSuffix(" ms")
        tipify(self._s3_ms, T.DIAG_S3)
        self._s3_ms.valueChanged.connect(self._on_diag_changed)
        self._tp_ms = QSpinBox()
        self._tp_ms.setRange(50, 300000)
        self._tp_ms.setValue(2000)
        bind_dirty_spin(self._tp_ms)
        self._tp_ms.setSuffix(" ms")
        tipify(self._tp_ms, T.DIAG_TP_PERIOD)
        self._tp_ms.valueChanged.connect(self._on_diag_changed)
        self._p2_ms = QSpinBox()
        self._p2_ms.setRange(1, 60000)
        self._p2_ms.setValue(50)
        bind_dirty_spin(self._p2_ms)
        self._p2_ms.setSuffix(" ms")
        tipify(self._p2_ms, T.DIAG_P2)
        self._p2_ms.valueChanged.connect(self._on_diag_changed)
        self._p2star_ms = QSpinBox()
        self._p2star_ms.setRange(1, 600000)
        self._p2star_ms.setValue(5000)
        bind_dirty_spin(self._p2star_ms)
        self._p2star_ms.setSuffix(" ms")
        tipify(self._p2star_ms, T.DIAG_P2STAR)
        self._p2star_ms.valueChanged.connect(self._on_diag_changed)
        self._sec_delay_ms = QSpinBox()
        self._sec_delay_ms.setRange(0, 600000)
        self._sec_delay_ms.setValue(10000)
        bind_dirty_spin(self._sec_delay_ms)
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
            "ota_transfer（下载 SID）", expanded=True, parent=inner
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
        bind_dirty_spin(self._ota_block)
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

        scroll = _PlatformScrollPage(inner, self)
        return scroll

    def _build_log_page(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        hint = QLabel(
            t(
                "log.yaml：默认级别、输出 sinks（console / file / DLT）、按模块级别。"
                "勾选 DLT 时由 EM 拉起 dlt-daemon（daemon，非与 EM 并列）；上位机用 dlt-viewer / GMT。"
                "页 1 的 live/record 是观测通道，与这里分开。"
            )
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
        form.addRow(t("默认级别"), self._log_level)

        sink_row = QHBoxLayout()
        self._log_sink_console = QCheckBox(t("console"))
        self._log_sink_file = QCheckBox(t("file"))
        self._log_sink_dlt = QCheckBox(t("dlt（remote）"))
        self._log_sink_console.setChecked(True)
        self._log_sink_dlt.setChecked(True)
        tipify(self._log_sink_console, "终端 stdout/stderr（SIL 本机）")
        tipify(self._log_sink_file, "落盘 file_path；仅本机调试，非 GMT 路径")
        tipify(self._log_sink_dlt, "COVESA DLT → dlt-daemon；标准协议给 viewer/GMT")
        for cb in (self._log_sink_console, self._log_sink_file, self._log_sink_dlt):
            cb.toggled.connect(self._on_log_changed)
            sink_row.addWidget(cb)
        sink_row.addStretch(1)
        form.addRow(t("输出 sinks"), sink_row)

        self._log_dlt_app = QLineEdit("GFAP")
        self._log_dlt_app.setMaxLength(4)
        self._log_dlt_app.setMaximumWidth(80)
        tipify(self._log_dlt_app, "DLT Application ID（4 字符）；多进程可由运行时覆盖")
        self._log_dlt_app.textChanged.connect(self._on_log_changed)
        form.addRow(t("DLT app_id"), self._log_dlt_app)
        self._log_file_max = QSpinBox()
        self._log_file_max.setRange(4096, 2_147_483_647)
        self._log_file_max.setValue(1_048_576)
        bind_dirty_spin(self._log_file_max)
        tipify(self._log_file_max, T.LOG_FILE_MAX)
        self._log_file_max.valueChanged.connect(self._on_log_changed)
        form.addRow("file_max_bytes", self._log_file_max)
        lay.addLayout(form)

        ctx_box = QGroupBox(t("按模块覆盖级别"))
        ctx_l = QVBoxLayout(ctx_box)
        self._ctx_table = QTableWidget(0, 2)
        self._ctx_table.setHorizontalHeaderLabels([t("模块"), t("级别")])
        set_header_tips(self._ctx_table, [T.LOG_CTX_ID, T.LOG_CTX_LEVEL])
        self._ctx_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        enable_table_row_selection(self._ctx_table)
        self._ctx_table.itemChanged.connect(self._on_log_changed)
        ctx_l.addWidget(self._ctx_table)
        ctx_btns = QHBoxLayout()
        add_c = QPushButton(t("添加模块级别"))
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
        w = QWidget(self)
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
        w = QWidget(self)
        lay = QVBoxLayout(w)
        hint = QLabel(
            t(
                "collector.yaml：Event Collector 最小集。"
                "有 MCU CP → forward=cp_dem；否则 local_store（DEM-lite）。"
                "sources 勾选本工程会 ReportEvent 的来源：phm / process / com / ucm"
                "（不是封闭枚举；diag 多是读 DTC，一般不作 source）。"
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
        bind_dirty_spin(self._col_max)
        tipify(self._col_max, T.COL_MAX)
        self._col_max.valueChanged.connect(self._on_collector_changed)
        self._col_deb_keys = QSpinBox()
        self._col_deb_keys.setRange(1, 100000)
        self._col_deb_keys.setValue(64)
        bind_dirty_spin(self._col_deb_keys)
        tipify(self._col_deb_keys, T.COL_DEB)
        self._col_deb_keys.valueChanged.connect(self._on_collector_changed)
        self._col_store_max = QSpinBox()
        self._col_store_max.setRange(4096, 2_147_483_647)
        self._col_store_max.setValue(1_048_576)
        bind_dirty_spin(self._col_store_max)
        tipify(self._col_store_max, T.COL_STORE)
        self._col_store_max.valueChanged.connect(self._on_collector_changed)
        local_f.addRow("", self._col_local_en)
        local_f.addRow("max_entries", self._col_max)
        local_f.addRow("debounce_max_keys", self._col_deb_keys)
        local_f.addRow("store_max_bytes", self._col_store_max)
        lay.addWidget(local)
        lay.addStretch(1)
        return w

    def _build_bounds_page(self) -> QWidget:
        inner = QWidget(self)
        lay = QVBoxLayout(inner)
        hint = QLabel(
            t(
                "BL-MEM-BOUND：平台有界内存 / 磁盘上界。"
                "下方预估为保守上界（非实测 RSS），公式见 mem_budget.py FORMULAS。"
                "未勾选的模块对应段不显示、不计入预估。"
                "log.file_max / collector 环与落盘上限在「日志」「事件收集」页编辑。"
                "Verify / Generate 跑同一套 estimate。"
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        lay.addWidget(hint)

        const_lbl = QLabel(
            t("公式常量（字节）")
            + f":  C_EVENT_RECORD={C_EVENT_RECORD}  "
            f"C_DEBOUNCE_ENTRY={C_DEBOUNCE_ENTRY}  "
            f"C_DLT_CTX={C_DLT_CTX}  C_PER_KEY_OH={C_PER_KEY_OH}"
        )
        const_lbl.setWordWrap(True)
        const_lbl.setStyleSheet(
            "font-family: monospace; font-size: 11px; color:#333; "
            "background:#f5f5f5; padding:6px;"
        )
        lay.addWidget(const_lbl)

        def _narrow(w: QWidget) -> QWidget:
            """~4/5 width + empty gutter: page wheel less likely to hit editors."""
            wrap = QWidget(self)
            h = QHBoxLayout(wrap)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(0)
            h.addWidget(w, 4)
            h.addStretch(1)
            return wrap

        def _spin(lo: int, hi: int, default: int) -> QSpinBox:
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(default)
            s.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            s.valueChanged.connect(self._on_bounds_changed)
            return bind_dirty_spin(s)

        # ── bounds.yaml (per-module sections; hidden when module off) ──
        self._bnd_grp_log = QGroupBox(t("bounds · log / DLT"))
        bf_log = QFormLayout(self._bnd_grp_log)
        self._bnd_dlt_ctx = _spin(1, 4096, 64)
        tipify(self._bnd_dlt_ctx, T.BND_DLT_CTX)
        bf_log.addRow("dlt.max_contexts", _narrow(self._bnd_dlt_ctx))
        lay.addWidget(self._bnd_grp_log)

        self._bnd_grp_com = QGroupBox(t("bounds · com"))
        bf_com = QFormLayout(self._bnd_grp_com)
        self._bnd_com_depth = _spin(1, 1024, 16)
        tipify(self._bnd_com_depth, T.BND_COM_DEPTH)
        self._bnd_com_keys = _spin(1, 100000, 64)
        tipify(self._bnd_com_keys, T.BND_COM_KEYS)
        self._bnd_com_avg = _spin(1, 1_048_576, 256)
        tipify(self._bnd_com_avg, T.BND_COM_AVG)
        bf_com.addRow("com.queue_depth", _narrow(self._bnd_com_depth))
        bf_com.addRow("com.max_topic_keys", _narrow(self._bnd_com_keys))
        bf_com.addRow("com.avg_payload_bytes", _narrow(self._bnd_com_avg))
        lay.addWidget(self._bnd_grp_com)

        self._bnd_grp_per = QGroupBox(t("bounds · per"))
        bf_per = QFormLayout(self._bnd_grp_per)
        self._bnd_per_keys = _spin(1, 1_000_000, 1024)
        tipify(self._bnd_per_keys, T.BND_PER_KEYS)
        self._bnd_per_val = _spin(1, 16_777_216, 65536)
        tipify(self._bnd_per_val, T.BND_PER_VAL)
        bf_per.addRow("per.max_keys", _narrow(self._bnd_per_keys))
        bf_per.addRow("per.max_value_bytes", _narrow(self._bnd_per_val))
        lay.addWidget(self._bnd_grp_per)

        self._bnd_grp_diag = QGroupBox(t("bounds · diag"))
        bf_diag = QFormLayout(self._bnd_grp_diag)
        self._bnd_rx = _spin(1024, 16_777_216, 65536)
        tipify(self._bnd_rx, T.BND_RX)
        self._bnd_did_n = _spin(1, 100000, 256)
        tipify(self._bnd_did_n, T.BND_DID_N)
        self._bnd_did_pay = _spin(1, 1_048_576, 4096)
        tipify(self._bnd_did_pay, T.BND_DID_PAY)
        bf_diag.addRow("diag.rx_max_bytes", _narrow(self._bnd_rx))
        bf_diag.addRow("diag.dids.max_entries", _narrow(self._bnd_did_n))
        bf_diag.addRow("diag.dids.max_payload", _narrow(self._bnd_did_pay))
        lay.addWidget(self._bnd_grp_diag)

        self._bnd_grp_budget = QGroupBox(t("bounds · budget（总预算）"))
        bf_bud = QFormLayout(self._bnd_grp_budget)
        self._bnd_bud_ram = _spin(0, 2_147_483_647, 0)
        tipify(self._bnd_bud_ram, T.BND_BUD_RAM)
        self._bnd_bud_disk = _spin(0, 2_147_483_647, 0)
        tipify(self._bnd_bud_disk, T.BND_BUD_DISK)
        bf_bud.addRow("budget.ram_bytes", _narrow(self._bnd_bud_ram))
        bf_bud.addRow("budget.disk_bytes", _narrow(self._bnd_bud_disk))
        lay.addWidget(self._bnd_grp_budget)

        # ── BL-MEM-ROUDI (bindings · iceoryx) ──
        self._bnd_grp_iox = QGroupBox(t("iceoryx / RouDi（BL-MEM-ROUDI）"))
        iox_l = QVBoxLayout(self._bnd_grp_iox)
        iox_warn = QLabel(t(T.IOX_WARN))
        iox_warn.setWordWrap(True)
        iox_warn.setStyleSheet(
            "color:#b71c1c; font-size:11px; background:#fff3e0; padding:6px;"
        )
        iox_l.addWidget(iox_warn)
        mgmt_f = QFormLayout()
        self._iox_pub = _spin(1, 4096, 32)
        tipify(self._iox_pub, T.IOX_PUB)
        self._iox_sub = _spin(1, 8192, 64)
        tipify(self._iox_sub, T.IOX_SUB)
        self._iox_sub_per_pub = _spin(1, 1024, 8)
        tipify(self._iox_sub_per_pub, T.IOX_SUB_PER_PUB)
        self._iox_hist = _spin(1, 256, 4)
        tipify(self._iox_hist, T.IOX_HIST)
        self._iox_chunk_pub = _spin(1, 256, 2)
        tipify(self._iox_chunk_pub, T.IOX_CHUNK_PUB)
        self._iox_chunk_sub = _spin(1, 4096, 16)
        tipify(self._iox_chunk_sub, T.IOX_CHUNK_SUB)
        self._iox_iface = _spin(1, 64, 2)
        tipify(self._iox_iface, T.IOX_IFACE)
        self._iox_bud_shm = _spin(0, 2_147_483_647, 0)
        tipify(self._iox_bud_shm, T.IOX_BUD_SHM)
        mgmt_f.addRow("mgmt.max_publishers", _narrow(self._iox_pub))
        mgmt_f.addRow("mgmt.max_subscribers", _narrow(self._iox_sub))
        mgmt_f.addRow(
            "mgmt.max_subscribers_per_publisher", _narrow(self._iox_sub_per_pub)
        )
        mgmt_f.addRow("mgmt.max_publisher_history", _narrow(self._iox_hist))
        mgmt_f.addRow(
            "mgmt.max_chunks_allocated_per_publisher", _narrow(self._iox_chunk_pub)
        )
        mgmt_f.addRow(
            "mgmt.max_chunks_held_per_subscriber", _narrow(self._iox_chunk_sub)
        )
        mgmt_f.addRow("mgmt.max_interface_number", _narrow(self._iox_iface))
        mgmt_f.addRow("budget_shm_bytes", _narrow(self._iox_bud_shm))
        # mempools: same FormLayout label column as mgmt spins → field aligns with _narrow.
        self._iox_pool_table = QTableWidget(0, 2)
        self._iox_pool_table.setHorizontalHeaderLabels(["size", "count"])
        self._iox_pool_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._iox_pool_table.setMinimumHeight(120)
        enable_table_row_selection(self._iox_pool_table)
        set_header_tips(self._iox_pool_table, [T.IOX_POOL_SIZE, T.IOX_POOL_COUNT])
        self._iox_pool_table.itemChanged.connect(self._on_bounds_changed)
        tipify(self._iox_pool_table, T.IOX_MEMPOOLS)
        mgmt_f.addRow("mempools", _narrow(self._iox_pool_table))
        pool_btns_w = QWidget(self)
        pool_btns = QHBoxLayout(pool_btns_w)
        pool_btns.setContentsMargins(0, 0, 0, 0)
        add_p = QPushButton(t("添加 mempool"))
        tipify(add_p, T.IOX_ADD_POOL)
        add_p.clicked.connect(self._add_iox_pool_row)
        del_p = QPushButton(t("删除选中"))
        tipify(del_p, T.BTN_DEL_ROW)
        del_p.clicked.connect(
            lambda: self._del_rows(self._iox_pool_table, self._on_bounds_changed)
        )
        pool_btns.addWidget(add_p)
        pool_btns.addWidget(del_p)
        pool_btns.addStretch(1)
        mgmt_f.addRow("", _narrow(pool_btns_w))
        iox_l.addLayout(mgmt_f)
        lay.addWidget(self._bnd_grp_iox)

        est_box = QGroupBox(t("静态上界预估（只读 · 含公式）"))
        est_l = QVBoxLayout(est_box)
        self._bnd_shm_bar = QWidget(self)
        shm_bar = QHBoxLayout(self._bnd_shm_bar)
        shm_bar.setContentsMargins(0, 0, 0, 0)
        self._bnd_shm_status = QLabel(
            t("SHM 实测：未载入（roudi_mgmt 用近似值，非精确）")
        )
        self._bnd_shm_status.setWordWrap(True)
        self._bnd_shm_status.setStyleSheet("color:#666; font-size:12px;")
        tipify(self._bnd_shm_status, "SHM 合计 = roudi_payload（mempool 用户数据）+ roudi_mgmt（iceoryx_mgmt 端口表）。未载入实测时 mgmt 用 SIL 拟合近似值（非精确，以实测为准）。改 mgmt.* → 保存/compose → 重编 iceoryx → 跑 SIL →「载入实测 SHM」。")
        load_shm = QPushButton(t("载入实测 SHM"))
        tipify(load_shm, "弹出文件选择；默认指向 reports/iox_shm_report.json。报告内 mgmt 与当前 bounds 一致则用实测；不一致则用模型+偏移近似。打开工程时不自动读盘。")
        load_shm.clicked.connect(self._load_iox_shm_report)
        clear_shm = QPushButton(t("清除实测"))
        tipify(clear_shm, "回到未载入状态；roudi_mgmt 改回模型近似。")
        clear_shm.clicked.connect(self._clear_iox_shm_report)
        shm_bar.addWidget(self._bnd_shm_status, 1)
        shm_bar.addWidget(load_shm)
        shm_bar.addWidget(clear_shm)
        est_l.addWidget(self._bnd_shm_bar)
        # Conclusion line (full width) — larger + RAM/DISK/SHM colors.
        self._bnd_estimate_summary = QLabel()
        self._bnd_estimate_summary.setWordWrap(True)
        self._bnd_estimate_summary.setTextFormat(Qt.TextFormat.RichText)
        self._bnd_estimate_summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._bnd_estimate_summary.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._bnd_estimate_summary.setStyleSheet(
            "font-size: 15px; background:#fafafa; padding:10px 8px 6px 8px; "
            "border:1px solid #e0e0e0; border-bottom: none;"
        )
        # Detail lines — full width (not narrowed).
        self._bnd_estimate = QLabel()
        self._bnd_estimate.setWordWrap(True)
        self._bnd_estimate.setTextFormat(Qt.TextFormat.RichText)
        self._bnd_estimate.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._bnd_estimate.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._bnd_estimate.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._bnd_estimate.setStyleSheet(
            "font-family: monospace; font-size: 11px; background:#fafafa; "
            "padding:4px 8px 8px 8px; border:1px solid #e0e0e0; border-top: none;"
        )
        est_l.addWidget(self._bnd_estimate_summary)
        est_l.addWidget(self._bnd_estimate)
        lay.addWidget(est_box)
        lay.addStretch(1)
        return _PlatformScrollPage(inner, self)

