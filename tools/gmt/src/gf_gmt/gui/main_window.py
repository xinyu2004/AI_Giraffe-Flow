"""GMT GUI — record / editable tags / replay / order / animated DAG."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.bridge_live import DEFAULT_LIVE_PORT
from gf_gmt.gui.anim_dag_view import AnimDagView
from gf_gmt.gui.inject_client import (
    DEFAULT_INJECT_PORT,
    InjectCtrlClient,
    InjectStreamHelper,
    is_injectable_topic,
)
from gf_gmt.gui.dlt_log_panel import DltLogPanel
from gf_gmt.gui.inject_panel import InjectPanel
from gf_gmt.gui.ota_panel import OtaPanel
from gf_gmt.gui.live_client import LiveWsSession
from gf_gmt.gui.order_view import OrderRaceView
from gf_gmt.gui.session_model import (
    SessionModel,
    load_session,
    write_session_meta_line,
)
from gf_gmt.gui.tag_panel import TagPanel
from gf_gmt.gui.var_strip_view import VarStripView
from gf_gmt.gui.wall_time import SessionClock
from gf_gmt.measure_export import export_session_jsonl
from gf_gmt.measure_ndjson import parse_session_line
from gf_gmt.i18n import get_language, switch_language_and_restart, t


class GmtMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("GMT — 选项目 → Live / 回灌 / Tag / 回放"))
        self.resize(1100, 720)
        self.setMinimumSize(720, 480)
        self._model = SessionModel()
        self._sor: dict[str, Any] | None = None
        self._session_path: Path | None = None
        self._project_dir: Path | None = None
        self._fox_proc: subprocess.Popen[bytes] | None = None
        self._ws: LiveWsSession | None = None
        self._live_log_fp: TextIO | None = None
        self._live_active = False
        # When True: Live WS connected but must not wipe/append into inject/file session.
        self._live_observe_only = False
        self._inject: InjectCtrlClient | None = None
        self._inject_helper: InjectStreamHelper | None = None
        self._inject_active = False
        self._inject_syncing = False  # avoid re-entrant seek storms
        self._inject_eof_asking = False  # avoid stacked eof dialogs
        self._playing = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._ws_timer = QTimer(self)
        self._ws_timer.setInterval(50)
        self._ws_timer.timeout.connect(self._on_ws_tick)
        self._inject_timer = QTimer(self)
        self._inject_timer.setInterval(100)
        self._inject_timer.timeout.connect(self._on_inject_tick)
        self._stick_tail = True  # when following, keep playhead at end
        self._last_follow_seek_ms = 0  # throttle Graphics seek while Live-following

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # —— 连接条拆两行，避免强制超宽 ——
        row1 = QHBoxLayout()
        self._btn_proj = QPushButton(t("加载项目…"))
        self._btn_proj.setToolTip(
            t("选择 project.yaml（与 gf-config / codegen 同一入口；SOR 在同目录）")
        )
        self._btn_proj.clicked.connect(self._open_project)
        row1.addWidget(self._btn_proj)
        self._btn_open = QPushButton(t("打开 session…"))
        self._btn_open.setToolTip(
            t("打开 session JSONL（回灌 / 时间轴权威源；加载项目后常用）")
        )
        self._btn_open.clicked.connect(self._open_session)
        row1.addWidget(self._btn_open)
        row1.addWidget(QLabel("Host"))
        self._host_edit = QLineEdit("127.0.0.1")
        self._host_edit.setToolTip(
            t(
                "SIL / 观测机地址（本机 127.0.0.1；远端填局域网 IP）\n"
                "Live 与回灌共用此 Host"
            )
        )
        self._host_edit.setMaximumWidth(120)
        row1.addWidget(self._host_edit)
        row1.addWidget(QLabel("Live"))
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(DEFAULT_LIVE_PORT)
        self._port_spin.setToolTip(
            t("Live WebSocket 端口（默认 {port}）").format(port=DEFAULT_LIVE_PORT)
        )
        self._port_spin.setMaximumWidth(64)
        row1.addWidget(self._port_spin)
        self._btn_live_connect = QPushButton(t("连接"))
        self._btn_live_connect.setToolTip(
            t("连 live_tap 旁路（ws:8766）；默认只看流不落盘，需落盘请点「录制」")
        )
        self._btn_live_connect.clicked.connect(self._connect_live)
        self._btn_live_disconnect = QPushButton(t("断开"))
        self._btn_live_disconnect.setEnabled(False)
        self._btn_live_disconnect.clicked.connect(self._disconnect_live)
        self._btn_live_rec = QPushButton(t("录制"))
        self._btn_live_rec.setCheckable(True)
        self._btn_live_rec.setEnabled(False)
        self._btn_live_rec.setToolTip(
            t("将 Live 流落盘；已有 session_live.jsonl 时可新建或覆盖")
        )
        self._btn_live_rec.toggled.connect(self._on_live_record_toggled)
        self._live_state = QLabel(t("空闲"))
        self._live_state.setStyleSheet("color:#555;")
        row1.addWidget(self._btn_live_connect)
        row1.addWidget(self._btn_live_disconnect)
        row1.addWidget(self._btn_live_rec)
        row1.addWidget(self._live_state)
        # Follow latest = Live 显示策略（不是回灌）。关=冻屏仍收流/可录制。
        self._follow_latest = QCheckBox(t("跟随最新"))
        self._follow_latest.setChecked(True)
        self._follow_latest.setToolTip(
            t(
                "仅影响 playhead：开=贴最新；关=停在当前帧（与是否录制落盘无关）"
            )
        )
        self._follow_latest.toggled.connect(self._on_follow_latest_toggled)
        row1.addWidget(self._follow_latest)
        row1.addStretch(1)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel(t("回灌 tcp")))
        self._inject_port_spin = QSpinBox()
        self._inject_port_spin.setRange(1, 65535)
        self._inject_port_spin.setValue(DEFAULT_INJECT_PORT)
        self._inject_port_spin.setToolTip(
            t("inject 控制口（默认 {port}，GF_INJECT_PORT）").format(
                port=DEFAULT_INJECT_PORT
            )
        )
        self._inject_port_spin.setMaximumWidth(64)
        row2.addWidget(self._inject_port_spin)
        self._btn_inject_connect = QPushButton(t("连接"))
        self._btn_inject_connect.setToolTip(
            t("连 playhead inject（TCP JSON）；需 GF_INJECT_MODE=playhead")
        )
        self._btn_inject_connect.clicked.connect(self._on_inject_connect_clicked)
        self._btn_inject_disconnect = QPushButton(t("断开"))
        self._btn_inject_disconnect.setEnabled(False)
        self._btn_inject_disconnect.clicked.connect(self._disconnect_inject)
        self._inject_state = QLabel(t("空闲"))
        self._inject_state.setStyleSheet("color:#555;")
        row2.addWidget(self._btn_inject_connect)
        row2.addWidget(self._btn_inject_disconnect)
        row2.addWidget(self._inject_state)
        row2.addStretch(1)
        root.addLayout(row2)

        self._proj_banner = QLabel(
            t("⚠ 请先「加载项目…」选择 project.yaml（回灌已禁用；Live 仍可旁观）")
        )
        self._proj_banner.setWordWrap(True)
        self._proj_banner.setStyleSheet(
            "background:#e65100; color:#ffffff; padding:10px 12px; "
            "border:2px solid #bf360c; font-weight:700; font-size:13px;"
        )
        root.addWidget(self._proj_banner)

        # Transport: playhead only. Rare paths (record logs / SOR / follow file)
        # stay under File menu.
        transport = QHBoxLayout()
        self._btn_home = QPushButton("|◀")
        self._btn_home.setToolTip(t("跳到开头"))
        self._btn_home.clicked.connect(self._jump_start)
        self._btn_back = QPushButton("◀")
        self._btn_back.setToolTip(t("后退一步"))
        self._btn_back.clicked.connect(self._step_back)
        self._btn_play = QPushButton(t("播放"))
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_step = QPushButton("▶")
        self._btn_step.setToolTip(t("前进一步"))
        self._btn_step.clicked.connect(self._step_once)
        self._btn_end = QPushButton("▶|")
        self._btn_end.setToolTip(t("跳到末尾"))
        self._btn_end.clicked.connect(self._jump_end)
        self._btn_fox = QPushButton("Foxglove")
        self._btn_fox.clicked.connect(self._start_foxglove_replay)
        self._btn_mcap = QPushButton(t("导出 MCAP"))
        self._btn_mcap.clicked.connect(self._export_mcap)

        for w in (
            self._btn_home,
            self._btn_back,
            self._btn_play,
            self._btn_step,
            self._btn_end,
            self._btn_fox,
            self._btn_mcap,
        ):
            transport.addWidget(w)

        transport.addWidget(QLabel(t("倍速%")))
        self._rate = QSpinBox()
        self._rate.setRange(10, 800)
        self._rate.setValue(100)
        self._rate.setSuffix("%")
        self._rate.setToolTip(
            t(
                "播放速度：越大越快。100%=默认；"
                "未勾「按 Δt」时约 200ms/事件；勾选后按事件时间缩放。"
            )
        )
        transport.addWidget(self._rate)
        self._use_dt = QCheckBox(t("按 Δt"))
        self._use_dt.setToolTip(t("播放间隔按相邻事件真实 Δt，再乘倍速%"))
        transport.addWidget(self._use_dt)
        transport.addStretch(1)
        root.addLayout(transport)

        # Wall clock on its own row so transport buttons cannot clip it.
        clock_row = QHBoxLayout()
        self._t_label = QLabel("t=—")
        self._t_label.setMinimumWidth(520)
        self._t_label.setMinimumHeight(22)
        self._t_label.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )
        self._t_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._t_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        clock_row.addWidget(self._t_label, stretch=1)
        root.addLayout(clock_row)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setEnabled(False)
        self._slider.valueChanged.connect(self._on_slider)
        root.addWidget(self._slider)

        self._tabs = QTabWidget()
        self._order = OrderRaceView()
        self._order.seek_requested.connect(self._seek_index)
        self._dag = AnimDagView()
        self._tags = TagPanel()
        self._tags.request_load_clip.connect(self._load_clip_path)
        self._tags.seek_ns_requested.connect(self._seek_ns)
        self._inject_panel = InjectPanel()
        self._inject_panel.follow_playhead.toggled.connect(self._on_follow_playhead_toggled)
        self._inject_panel.seek_requested.connect(self._seek_index)
        self._ota_panel = OtaPanel()
        self._dlt_panel = DltLogPanel()
        self._dlt_panel.set_host_provider(
            lambda: self._host_edit.text().strip() or "127.0.0.1"
        )
        self._var_strip = VarStripView()
        self._var_strip.seek_ns_requested.connect(self._seek_ns)
        self._tabs.addTab(self._order, t("Order"))
        self._tabs.addTab(self._dag, t("DAG"))
        self._tabs.addTab(self._var_strip, t("图形"))
        self._tabs.addTab(self._tags, t("Tag"))
        self._tabs.addTab(self._inject_panel, t("Inject"))
        self._tabs.addTab(self._ota_panel, t("OTA/UDS"))
        self._tabs.addTab(self._dlt_panel, t("Logging"))
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, stretch=1)

        status = QStatusBar()
        self._path_label = QLabel(
            t("请先加载项目 → 填 Host → Live(ws:8766) / 回灌(tcp:8767) / OTA(DoIP)「连接」")
        )
        status.addWidget(self._path_label, stretch=1)
        self.setStatusBar(status)

        self._build_menus()
        self._refresh_project_gate()
        self._on_tab_changed(self._tabs.currentIndex())

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu(t("文件"))
        act_proj = QAction(t("加载项目…"), self)
        act_proj.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_proj.triggered.connect(self._open_project)
        file_menu.addAction(act_proj)
        act_proj_dir = QAction(t("加载项目目录…"), self)
        act_proj_dir.setToolTip(t("备选：直接选 SKU 目录（等价于该目录下的 project.yaml）"))
        act_proj_dir.triggered.connect(self._open_project_dir)
        file_menu.addAction(act_proj_dir)

        act_sess = QAction(t("打开 session JSONL…"), self)
        act_sess.setShortcut(QKeySequence.StandardKey.Open)
        act_sess.triggered.connect(self._open_session)
        file_menu.addAction(act_sess)

        file_menu.addSeparator()
        act_mcap = QAction(t("导出 MCAP…"), self)
        act_mcap.triggered.connect(self._export_mcap)
        file_menu.addAction(act_mcap)

        act_vcd = QAction(t("导出 VCD（GTKWave）…"), self)
        act_vcd.triggered.connect(self._export_vcd)
        file_menu.addAction(act_vcd)

        act_dot = QAction(t("导出 Graphviz .dot…"), self)
        act_dot.triggered.connect(self._export_dot)
        file_menu.addAction(act_dot)

        file_menu.addSeparator()
        act_quit = QAction(t("退出"), self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # 连接 / 视图：顶栏与下方 Tab 已覆盖，不再重复菜单

        replay_menu = self.menuBar().addMenu(t("回放"))
        act_play = QAction(t("播放 / 暂停"), self)
        act_play.setShortcut(QKeySequence(Qt.Key.Key_Space))
        act_play.triggered.connect(self._toggle_play)
        replay_menu.addAction(act_play)
        act_step = QAction(t("前进一步"), self)
        act_step.setShortcut(QKeySequence(Qt.Key.Key_Right))
        act_step.triggered.connect(self._step_once)
        replay_menu.addAction(act_step)
        act_back = QAction(t("后退一步"), self)
        act_back.setShortcut(QKeySequence(Qt.Key.Key_Left))
        act_back.triggered.connect(self._step_back)
        replay_menu.addAction(act_back)
        act_home = QAction(t("跳到开头"), self)
        act_home.setShortcut(QKeySequence(Qt.Key.Key_Home))
        act_home.triggered.connect(self._jump_start)
        replay_menu.addAction(act_home)
        act_end = QAction(t("跳到末尾"), self)
        act_end.setShortcut(QKeySequence(Qt.Key.Key_End))
        act_end.triggered.connect(self._jump_end)
        replay_menu.addAction(act_end)
        replay_menu.addSeparator()
        act_fox = QAction(t("打开 Foxglove 回放…"), self)
        act_fox.triggered.connect(self._start_foxglove_replay)
        replay_menu.addAction(act_fox)
        act_fox_stop = QAction(t("停止 Foxglove 回放进程"), self)
        act_fox_stop.triggered.connect(self._stop_foxglove)
        replay_menu.addAction(act_fox_stop)
        replay_menu.addSeparator()
        act_follow = QAction(t("切换跟随最新"), self)
        act_follow.setShortcut(QKeySequence(Qt.Key.Key_F))
        act_follow.triggered.connect(
            lambda: self._follow_latest.setChecked(
                not self._follow_latest.isChecked()
            )
        )
        replay_menu.addAction(act_follow)

        tag_menu = self.menuBar().addMenu("Tag")
        act_mark = QAction(t("钉标记点 ●"), self)
        act_mark.setShortcut(QKeySequence(Qt.Key.Key_M))
        act_mark.triggered.connect(self._live_tag_marker)
        tag_menu.addAction(act_mark)
        act_tag_from = QAction(t("片段 from ← playhead"), self)
        act_tag_from.setShortcut(QKeySequence(Qt.Key.Key_BracketLeft))
        act_tag_from.triggered.connect(self._live_tag_from)
        tag_menu.addAction(act_tag_from)
        act_tag_to = QAction(t("片段 to ← playhead 并保存"), self)
        act_tag_to.setShortcut(QKeySequence(Qt.Key.Key_BracketRight))
        act_tag_to.triggered.connect(self._live_tag_to)
        tag_menu.addAction(act_tag_to)

        lang_menu = self.menuBar().addMenu(t("语言"))
        act_zh = QAction(t("中文"), self)
        act_zh.setCheckable(True)
        act_zh.setChecked(get_language() == "zh")
        act_zh.triggered.connect(lambda: self._on_language("zh"))
        lang_menu.addAction(act_zh)
        act_en = QAction(t("English"), self)
        act_en.setCheckable(True)
        act_en.setChecked(get_language() == "en")
        act_en.triggered.connect(lambda: self._on_language("en"))
        lang_menu.addAction(act_en)

    def _on_language(self, lang: str) -> None:
        if lang == get_language():
            return
        switch_language_and_restart(lang)

    def _refresh_project_gate(self) -> None:
        """未加载项目：醒目提示；回灌 / OTA 连接由项目态禁用。"""
        has = self._project_dir is not None and self._sor is not None
        self._proj_banner.setVisible(not has)
        if has:
            self._btn_proj.setText(f'{t("项目")}: {self._project_dir.name}')
            self._btn_proj.setStyleSheet("font-weight:700;")
        else:
            self._proj_banner.setText(
                t("⚠ 请先「加载项目…」选择 project.yaml（回灌 / OTA 已禁用；Live 仍可旁观）")
            )
            self._btn_proj.setText(t("加载项目…"))
            self._btn_proj.setStyleSheet("")
        # OTA only needs project dir (diag.yaml); keep in sync even if SOR missing
        self._ota_panel.set_project_dir(self._project_dir if has else None)
        self._refresh_conn_bar_ui()
        self._refresh_status_for_tab()

    def _on_tab_changed(self, _index: int) -> None:
        self._refresh_status_for_tab()

    def _refresh_status_for_tab(self) -> None:
        """Status bar hint depends on active tab (OTA ≠ Live/回灌)."""
        w = self._tabs.currentWidget()
        proj = self._project_dir.name if self._project_dir else None
        if w is self._ota_panel:
            if proj and self._sor is not None:
                self._path_label.setText(
                    t(
                        "项目={name} · OTA/UDS：DoIP 连接后选 OTA / DEM / Collector"
                    ).format(name=proj)
                )
            else:
                self._path_label.setText(
                    t("OTA/UDS：请先加载项目，再填 DoIP Host:Port「连接」")
                )
            return
        if w is self._dlt_panel:
            self._dlt_panel.sync_host_from_bar()
            host = self._host_edit.text().strip() or "127.0.0.1"
            self._path_label.setText(
                t("Logging（DLT）：Host {host} → 连接 dlt-daemon（默认 TCP 3490）").format(
                    host=host
                )
            )
            return
        # Restore observability status when leaving OTA
        if self._session_path is not None:
            n = len(self._model.events)
            prefix = f"{proj} · " if proj else ""
            self._path_label.setText(f"{prefix}{self._session_path} · {n} events")
            return
        if self._live_active:
            n = len(self._model.events)
            prefix = f"{proj} · " if proj else ""
            live_lbl = (
                t("Live 录制中")
                if self._btn_live_rec.isChecked()
                else t("Live 旁观（未录制）")
            )
            self._path_label.setText(f"{prefix}{live_lbl} · {n} events")
            return
        if proj and self._sor is not None:
            if w is self._inject_panel:
                self._path_label.setText(
                    t("项目={name} · 回灌：Host + tcp 端口 →「连接」").format(name=proj)
                )
            else:
                self._path_label.setText(
                    t("项目={name} · Live ws / 回灌 tcp →「连接」").format(name=proj)
                )
            return
        self._path_label.setText(
            t("请先加载项目 → 填 Host → Live(ws:8766) / 回灌(tcp:8767) / OTA(DoIP)「连接」")
        )

    def _default_live_session(self) -> Path:
        return self._default_obs_dir() / "session_live.jsonl"

    def _set_live_ui(self, active: bool) -> None:
        self._live_active = active
        self._refresh_conn_bar_ui()

    def _set_inject_ui(self, active: bool) -> None:
        self._inject_active = active
        self._refresh_conn_bar_ui()

    def _refresh_conn_bar_ui(self) -> None:
        """Live 与回灌可并行。Inject 顶栏只表示 TCP 链路，与单帧成败无关。"""
        live_on = self._live_active
        inj_on = self._inject_active

        self._host_edit.setEnabled(not live_on and not inj_on)

        self._port_spin.setEnabled(not live_on)
        self._btn_live_connect.setEnabled(not live_on)
        self._btn_live_disconnect.setEnabled(live_on)
        self._btn_live_rec.setEnabled(live_on)
        if not live_on and self._btn_live_rec.isChecked():
            self._btn_live_rec.blockSignals(True)
            self._btn_live_rec.setChecked(False)
            self._btn_live_rec.blockSignals(False)
        self._style_live_record_btn()

        has_proj = self._project_dir is not None and self._sor is not None
        self._inject_port_spin.setEnabled(not inj_on and has_proj)
        self._btn_inject_connect.setEnabled(not inj_on and has_proj)
        self._btn_inject_disconnect.setEnabled(inj_on)
        if not has_proj:
            self._btn_inject_connect.setToolTip(t("请先加载 project.yaml 后再连接回灌"))
        else:
            self._btn_inject_connect.setToolTip(
                t("连 playhead inject（TCP JSON）；需 GF_INJECT_MODE=playhead")
            )

        green = "color:#2e7d32; font-weight:700;"
        idle_s = "color:#555;"

        if live_on:
            self._live_state.setText(t("已连接"))
            self._live_state.setStyleSheet(green)
        else:
            self._live_state.setText(t("空闲"))
            self._live_state.setStyleSheet(idle_s)

        # TCP link only — never paint Failed/red for per-frame inject skip/error.
        sock_ok = (
            inj_on
            and self._inject is not None
            and self._inject.connected
        )
        if sock_ok:
            self._inject_state.setText(t("已连接"))
            self._inject_state.setStyleSheet(green)
        else:
            self._inject_state.setText(t("空闲"))
            self._inject_state.setStyleSheet(idle_s)

        self._refresh_window_title()

    def _refresh_host_enabled(self) -> None:
        self._refresh_conn_bar_ui()

    def _refresh_window_title(self) -> None:
        host = self._host_edit.text().strip() or "127.0.0.1"
        bits: list[str] = []
        if self._live_active:
            bits.append(f"LIVE ws://{host}:{self._port_spin.value()}")
        if self._inject_active:
            bits.append(f"INJ tcp://{host}:{self._inject_port_spin.value()}")
        if bits:
            self.setWindowTitle("GMT — ● " + " · ".join(bits))
        else:
            self.setWindowTitle(t("GMT — 选项目 → Live / 回灌 / Tag / 回放"))

    def _refresh_live_state_label(self) -> None:
        self._refresh_conn_bar_ui()

    def _force_live_follow_off(self, *, reason: str) -> None:
        """回灌跟 playhead 时关掉 Live 跟随，避免拽走 playhead。"""
        if self._follow_latest.isChecked():
            self._follow_latest.blockSignals(True)
            self._follow_latest.setChecked(False)
            self._follow_latest.blockSignals(False)
        self._stick_tail = False
        self._refresh_conn_bar_ui()
        self.statusBar().showMessage(reason, 5000)

    def _on_follow_latest_toggled(self, on: bool) -> None:
        if on and self._inject_panel.wants_playhead_sync():
            self._follow_latest.blockSignals(True)
            self._follow_latest.setChecked(False)
            self._follow_latest.blockSignals(False)
            self._stick_tail = False
            self._refresh_conn_bar_ui()
            self.statusBar().showMessage(
                t("回灌「跟 playhead 灌」已开 → Live 跟随已禁用（仍可连 Live 旁观/录制）"),
                5000,
            )
            return
        self._stick_tail = on
        self._refresh_live_state_label()
        if not self._live_active:
            return
        if on and not self._model.empty:
            # Unfreeze: rebuild views that were skipped while frozen.
            self._resync_views_from_model()
            self._seek_index(len(self._model.events) - 1)
            self.statusBar().showMessage(t("跟随最新 ON — 贴最新事件"), 2500)
        else:
            self.statusBar().showMessage(
                t("跟随最新 OFF — 冻屏：继续收流/录制，视图不跳"),
                4000,
            )

    def _obs_json(self) -> Path | None:
        if self._project_dir is not None:
            p = self._project_dir / "generated" / "observability.json"
            if p.is_file():
                return p
        fallback = Path.cwd() / "projects/oem_a/afc_with_uss/generated/observability.json"
        return fallback if fallback.is_file() else None

    def _default_obs_dir(self) -> Path:
        # Align with run_sil: ${BUILD}/observability (SKU build-sil by default).
        if self._project_dir is not None:
            d = Path(self._project_dir) / "build-sil" / "observability"
        else:
            d = (
                Path.cwd()
                / "projects"
                / "oem_a"
                / "afc_with_uss"
                / "build-sil"
                / "observability"
            )
            if not d.parent.is_dir():
                d = Path.cwd() / "build-sil" / "observability"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def load_session_path(self, path: Path, *, sor_path: Path | None = None) -> None:
        if sor_path and sor_path.is_file():
            with sor_path.open(encoding="utf-8") as f:
                self._sor = json.load(f)
        self._session_path = path
        if path.is_file():
            self._model = load_session(path, sor=self._sor)
        else:
            self._model = SessionModel()
            self._model.path = path
            self._model.bind_sor(self._sor)
        self._apply_model()

    def _write_live_session_meta_if_needed(self, first_t_ns: int) -> None:
        """Scheme-1: one meta line at live session start (before first event)."""
        if self._model.clock.ready:
            return
        clock = SessionClock.now_anchor(first_t_ns)
        self._model.clock = clock
        if self._live_log_fp is not None:
            write_session_meta_line(self._live_log_fp, clock)


    def _close_live_log(self) -> None:
        if self._live_log_fp is not None:
            try:
                self._live_log_fp.close()
            except OSError:
                pass
            self._live_log_fp = None

    def _style_live_record_btn(self) -> None:
        recording = self._live_log_fp is not None
        if recording:
            self._btn_live_rec.setText(t("录制中"))
            self._btn_live_rec.setStyleSheet(
                "QPushButton { background:#c62828; color:#fff; font-weight:700; "
                "border:1px solid #8e0000; padding:2px 10px; }"
            )
        else:
            self._btn_live_rec.setText(t("录制"))
            self._btn_live_rec.setStyleSheet("")
        if self._btn_live_rec.isChecked() != recording:
            self._btn_live_rec.blockSignals(True)
            self._btn_live_rec.setChecked(recording)
            self._btn_live_rec.blockSignals(False)

    def _new_live_record_path(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._default_obs_dir() / f"session_live_{stamp}.jsonl"

    def _choose_live_record_path(self) -> Path | None:
        """Ask new/overwrite when default session_live.jsonl exists and is non-empty."""
        default = self._default_live_session()
        if default.is_file() and default.stat().st_size > 0:
            box = QMessageBox(self)
            box.setWindowTitle(t("Live 录制"))
            box.setIcon(QMessageBox.Icon.Question)
            box.setText(
                t("已存在 {name}（{n} 字节）。\n新建时间戳文件，还是覆盖？").format(
                    name=default.name, n=default.stat().st_size
                )
            )
            btn_new = box.addButton(t("新建"), QMessageBox.ButtonRole.AcceptRole)
            btn_over = box.addButton(t("覆盖"), QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(t("取消"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is btn_new:
                return self._new_live_record_path()
            if clicked is btn_over:
                return default
            return None
        return default

    def _start_live_record(self, path: Path) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        # New or overwrite: always start a clean file for the chosen path
        path.write_text("", encoding="utf-8")
        self._close_live_log()
        try:
            self._live_log_fp = path.open("a", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, t("Live 录制"), f'{t("无法写入")} {path}\n{exc}')
            return False
        self._session_path = path
        self._tags.set_session(path, clock=self._model.clock)
        self._model.path = path
        # If clock already ready from live view, persist meta for the new file
        if self._model.clock.ready:
            write_session_meta_line(self._live_log_fp, self._model.clock)
        self._style_live_record_btn()
        self._refresh_conn_bar_ui()
        self.statusBar().showMessage(f'{t("Live 录制中")} → {path}', 6000)
        return True

    def _stop_live_record(self, *, quiet: bool = False) -> None:
        path = self._session_path
        self._close_live_log()
        self._style_live_record_btn()
        self._refresh_conn_bar_ui()
        if not quiet:
            self.statusBar().showMessage(
                t("Live 录制已停止")
                + (f"：{path}" if path else ""),
                5000,
            )

    def _on_live_record_toggled(self, on: bool) -> None:
        if on:
            if not self._live_active:
                self._btn_live_rec.blockSignals(True)
                self._btn_live_rec.setChecked(False)
                self._btn_live_rec.blockSignals(False)
                return
            if self._live_log_fp is not None:
                return
            path = self._choose_live_record_path()
            if path is None:
                self._btn_live_rec.blockSignals(True)
                self._btn_live_rec.setChecked(False)
                self._btn_live_rec.blockSignals(False)
                return
            if not self._start_live_record(path):
                self._btn_live_rec.blockSignals(True)
                self._btn_live_rec.setChecked(False)
                self._btn_live_rec.blockSignals(False)
        else:
            if self._live_log_fp is not None:
                self._stop_live_record()

    def _begin_live_memory_session(self) -> None:
        """In-memory session for Live view without touching disk."""
        self._close_live_log()
        self._session_path = None
        self._model = SessionModel()
        self._model.bind_sor(self._sor)
        self._tags.set_session(None, clock=self._model.clock)
        self._dag.set_topology(self._sor)
        self._dag.set_model(self._model)
        self._inject_panel.set_model(self._model)
        self._var_strip.set_model(self._model)
        self._order.set_model(self._model)
        self._apply_model()
        self._stick_tail = self._follow_latest.isChecked()

    def _connect_live(self) -> None:
        """Primary UX: connect to external live bridge (view stream; record optional)."""
        if self._live_active:
            return
        if self._inject_panel.wants_playhead_sync():
            self._force_live_follow_off(
                reason=t("已开回灌 playhead → Live 以旁观方式连接（不跟随最新）")
            )
        if self._project_dir is None:
            reply = QMessageBox.question(
                self,
                "Live",
                t("尚未加载项目（SOR / 动画 DAG / 变量轨对齐）。\n"
                "是否现在打开 project.yaml？\n\n"
                "选「否」仍可旁观连接（无 DAG）。"),
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._open_project()
            if self._project_dir is None:
                self.statusBar().showMessage(
                    t("Live 无项目：仅旁观（动画 DAG 为空）"),
                    5000,
                )

        host = self._host_edit.text().strip() or "127.0.0.1"
        port = int(self._port_spin.value())
        # Open file session / inject authority must survive Live connect.
        preserve = self._session_path is not None or self._inject_active
        if preserve:
            self._live_observe_only = True
            self._force_live_follow_off(
                reason=t("已有 session/回灌 → Live 旁观（不覆盖时间轴）")
            )
        else:
            self._live_observe_only = False
            self._begin_live_memory_session()

        ws = LiveWsSession()
        try:
            ws.connect(host, port)
        except (OSError, TimeoutError, ConnectionError) as exc:
            self._live_observe_only = False
            self._close_live_log()
            QMessageBox.critical(
                self,
                "Live",
                t("无法连接 ws://{host}:{port}\n{exc}\n\n").format(
                    host=host, port=port, exc=exc
                )
                + t(
                    "Live = tap 旁路 WebSocket（默认 8766）。\n"
                    "回灌 playhead 时 SIL 默认仍开 live（只订下游）；"
                    "若连不上请看 run_sil 是否打印 downstream tap。\n"
                    "回灌控制请用顶栏「回灌 tcp:8767」。"
                ),
            )
            return

        self._ws = ws
        self._ws_timer.start()
        self._set_live_ui(True)
        if self._live_observe_only:
            self.statusBar().showMessage(
                t(
                    "Live 旁观 ws://{host}:{port}（保留 session/回灌；可录制落盘，不写入时间轴）"
                ).format(host=host, port=port),
                10000,
            )
        else:
            mode = t("跟随最新") if self._follow_latest.isChecked() else t("不跟播")
            self.statusBar().showMessage(
                t("Live 已连接 ws://{host}:{port}（{mode}；落盘请点「录制」）").format(
                    host=host, port=port, mode=mode
                ),
                8000,
            )

    def _disconnect_live(self) -> None:
        self._ws_timer.stop()
        if self._ws is not None:
            self._ws.close()
            self._ws = None
        was_rec = self._live_log_fp is not None
        self._stop_live_record(quiet=True) if was_rec else self._close_live_log()
        observe = self._live_observe_only
        self._live_observe_only = False
        self._set_live_ui(False)
        n = len(self._model.events)
        note = t("（旁观模式未改时间轴）") if observe else ""
        self.statusBar().showMessage(
            t("Live 已断开 · 保留 session（{n} events）").format(n=n)
            + note
            + (f"：{self._session_path}" if self._session_path else ""),
            8000,
        )

    def _on_ws_tick(self) -> None:
        if self._ws is None or not self._ws.connected:
            return
        lines = self._ws.poll_lines()
        if not lines:
            return
        rows: list[dict[str, Any]] = []
        for line in lines:
            row = parse_session_line(line)
            if row is None:
                continue
            if (
                not self._live_observe_only
                and row.get("type") != "session_meta"
                and not self._model.clock.ready
            ):
                self._write_live_session_meta_if_needed(int(row.get("t_ns") or 0))
            if self._live_log_fp is not None:
                self._live_log_fp.write(line + "\n")
                self._live_log_fp.flush()
            rows.append(row)
        if not rows:
            return
        # Keep inject/file session indices stable — Foxglove shows live topics.
        if self._live_observe_only:
            return
        self._append_live_rows(rows)

    def _on_inject_connect_clicked(self) -> None:
        if self._inject_active:
            return
        if self._project_dir is None or self._sor is None:
            reply = QMessageBox.warning(
                self,
                t("回灌"),
                t("回灌需要先加载 project.yaml（SOR / 事件对齐）。\n是否现在打开？"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._open_project()
            if self._project_dir is None or self._sor is None:
                return
        host = self._host_edit.text().strip() or "127.0.0.1"
        port = int(self._inject_port_spin.value())
        self._connect_inject(host, port)

    def _on_follow_playhead_toggled(self, on: bool) -> None:
        if on and self._inject_active:
            self._force_live_follow_off(
                reason=t("已开「跟 playhead 灌」→ Live 跟随已关")
            )
            if not self._model.empty:
                self._inject_seek(self._slider.value())
        self._refresh_conn_bar_ui()

    def _connect_inject(self, host: str, port: int) -> None:
        if self._inject is not None and self._inject.connected:
            return
        if self._model.empty:
            QMessageBox.warning(
                self,
                t("回灌"),
                t("请先打开 session JSONL（GMT 为权威源）。\n"
                "stream 模式下板端不必再设 GF_INJECT_SESSION。"),
            )
            return
        # Disable before blocking hello — avoid double-connect (new ephemeral ports)
        self._btn_inject_connect.setEnabled(False)
        self._inject_port_spin.setEnabled(False)
        client = InjectCtrlClient()
        try:
            client.connect(host, port)
        except (OSError, TimeoutError, ConnectionError) as exc:
            self._refresh_conn_bar_ui()
            QMessageBox.critical(
                self,
                t("回灌"),
                t("无法连接 inject ctrl tcp://{host}:{port}\n{exc}\n\n").format(
                    host=host, port=port, exc=exc
                )
                + t(
                    "远端请确认：\n"
                    "1) SIL 机 GF_INJECT_MODE=playhead，且 ss 能看到 0.0.0.0:8767\n"
                    "2) 防火墙放行 TCP 8767\n"
                    "3) 用本页「连接 inject」，不要点上方 Live（那是 ws://8766）"
                ),
            )
            return
        hello = client.last_hello or {}
        self._inject = client
        helper = InjectStreamHelper(client)
        helper.on_hello(hello)
        self._inject_helper = helper
        n_inj = hello.get("events", "?")
        n_gui = len(self._model.events)
        try:
            helper.configure_session(n_gui)
            # Prefetch A/B once so board logs LOAD A / LOAD B (not per-scrub)
            if n_gui > 0:
                helper.ensure_windows_around(self._model, 0)
        except ConnectionError as exc:
            self._refresh_conn_bar_ui()
            QMessageBox.critical(
                self,
                t("回灌"),
                t("stream session/reset 失败：{exc}").format(exc=exc),
            )
            client.close()
            self._inject = None
            self._inject_helper = None
            return
        detail = (
            f"tcp://{host}:{port} · "
            f"GMT events={n_gui} · board hint={n_inj} · "
            f"window≤{helper.window_size}"
        )
        self._inject_eof_asking = False
        self._inject_panel.set_connected(True, detail=detail)
        self._set_inject_ui(True)
        if self._inject_panel.wants_playhead_sync():
            self._force_live_follow_off(
                reason=t("回灌已连且跟 playhead → Live 跟随已关（可另连 Live 旁观/录制）")
            )
        self._inject_timer.start()
        self.statusBar().showMessage(
            t("Inject 已连接 tcp://{host}:{port}").format(host=host, port=port),
            6000,
        )
        if not self._model.empty and self._inject_panel.wants_playhead_sync():
            self._inject_seek(self._slider.value())

    def _pause_playback(self, *, reason: str = "") -> None:
        """Stop GMT playhead timer (does not disconnect Live/Inject)."""
        if not self._playing:
            return
        self._playing = False
        self._timer.stop()
        self._btn_play.setText(t("播放"))
        if reason:
            self.statusBar().showMessage(reason, 4000)

    def _disconnect_inject(self) -> None:
        self._inject_timer.stop()
        # Disconnect must stop 回灌：pause board + stop GMT playhead.
        if self._inject is not None and self._inject.connected:
            try:
                self._inject.pause()
            except (OSError, ConnectionError):
                pass
        self._pause_playback(reason=t("Inject 已断开 — 播放已停"))
        if self._inject is not None:
            self._inject.close()
            self._inject = None
        self._inject_helper = None
        self._inject_eof_asking = False
        self._inject_panel.set_connected(False, detail="—")
        self._set_inject_ui(False)
        if not self.statusBar().currentMessage():
            self.statusBar().showMessage(t("Inject 已断开"), 3000)

    def _poll_inject_msgs(self, msgs: list[dict[str, Any]]) -> None:
        for msg in msgs:
            op = msg.get("op")
            if op == "published":
                self._apply_inject_published(msg)
            elif op == "status":
                self._inject_panel.set_detail(
                    f"status index={msg.get('index')} "
                    f"state={msg.get('state')} sent={msg.get('sent')}"
                )
            elif op == "need_window":
                self._on_inject_need_window(msg)
            elif op == "eof":
                self._on_inject_eof(msg)
            elif op == "error":
                err = str(msg.get("msg") or "error")
                if err == "need_window":
                    # Prefetch signal — not a TCP link failure.
                    self._on_inject_need_window(
                        {
                            "from": msg.get("from", self._slider.value()),
                            "count": msg.get("count", 64),
                            "slot": msg.get("slot"),
                        }
                    )
                    continue
                self._inject_panel.set_detail(f'{t("回灌错误")}：{err}')
                idx = self._slider.value()
                if err in {"index out of range", "at end"} and idx >= 0:
                    self._inject_panel.record_result(
                        idx,
                        injected=False,
                        topic="",
                        reason=t("超出 session（{err}）").format(err=err),
                    )
                self.statusBar().showMessage(f'{t("回灌失败")}：{err}', 6000)

    def _on_inject_need_window(self, msg: dict[str, Any]) -> None:
        if (
            self._inject is None
            or self._inject_helper is None
            or self._model.empty
        ):
            return
        try:
            n = self._inject_helper.handle_need_window(self._model, msg)
            self._inject_panel.set_detail(
                f"need_window from={msg.get('from')} → pushed {n} EgoMotion"
            )
        except ConnectionError as exc:
            self.statusBar().showMessage(f'{t("填窗失败")}：{exc}', 4000)
            self._disconnect_inject()

    def _restart_inject_loop(self, *, keep_playing: bool) -> None:
        """Wrap to session start: reset board A/B, clear result table, seek 0."""
        self._inject_panel.clear_results()
        if (
            self._inject_helper is not None
            and self._inject is not None
            and self._inject.connected
            and not self._model.empty
        ):
            try:
                self._inject_helper.configure_session(len(self._model.events))
                self._inject_helper.ensure_windows_around(self._model, 0)
                self._poll_inject_msgs(self._inject.poll_messages())
            except ConnectionError:
                self._disconnect_inject()
                return
        was_playing = keep_playing and self._playing
        if was_playing:
            self._timer.stop()
        self._seek_index(0)
        self._inject_panel.set_detail(t("循环：已回到开头"))
        self.statusBar().showMessage(t("回灌循环 → #0"), 2500)
        if was_playing:
            self._timer.start(self._next_interval_ms())

    def _on_inject_eof(self, _msg: dict[str, Any]) -> None:
        if self._inject_eof_asking:
            return
        if not self._inject_panel.wants_loop_confirm():
            self._inject_panel.set_detail(t("eof（未勾选循环）"))
            self.statusBar().showMessage(t("回灌到结尾"), 4000)
            return
        self._inject_eof_asking = True
        try:
            self._restart_inject_loop(keep_playing=True)
        finally:
            self._inject_eof_asking = False

    def _on_inject_tick(self) -> None:
        if self._inject is None:
            return
        if not self._inject.connected:
            # Peer closed — same as user Disconnect (stops play + board pause).
            self._disconnect_inject()
            return
        self._poll_inject_msgs(self._inject.poll_messages())

    def _apply_inject_published(self, msg: dict[str, Any]) -> None:
        idx = msg.get("index")
        topic = str(msg.get("topic") or "?")
        injected = msg.get("injected")
        ok = injected is True or injected == "true"
        try:
            index_i = int(idx) if idx is not None else -1
        except (TypeError, ValueError):
            index_i = -1
        t_ns = msg.get("t_ns")
        try:
            t_i = int(t_ns) if t_ns is not None else None
        except (TypeError, ValueError):
            t_i = None
        reason = ""
        if index_i >= 0:
            if ok:
                reason = ""
            elif "EgoMotion" in topic:
                reason = t("白名单未命中 / Send 失败")
            else:
                reason = t("MVP 仅灌 EgoMotion，本 topic 跳过")
            self._inject_panel.record_result(
                index_i,
                injected=ok,
                topic=topic,
                reason=reason,
                t_ns=t_i,
            )
        if ok:
            self._inject_panel.set_detail(f"#{idx} {topic} t={msg.get('t_ns')}")
            self.statusBar().showMessage(
                t("回灌成功：#{idx} {topic} 已 Send").format(idx=idx, topic=topic),
                3000,
            )
        else:
            why = reason or "injected=false"
            self._inject_panel.set_detail(f"#{idx} {topic} ({why})")
            self.statusBar().showMessage(
                t("回灌跳过：#{idx} {topic}").format(idx=idx, topic=topic),
                4000,
            )

    def _inject_seek(self, index: int) -> None:
        if self._inject is None or not self._inject.connected:
            return
        if not self._inject_panel.wants_playhead_sync():
            return
        if self._inject_syncing:
            return
        self._inject_syncing = True
        try:
            if self._inject_helper is None:
                return
            # Scrub: inject_event for EgoMotion; local pink otherwise
            if self._model.empty or index < 0 or index >= len(self._model.events):
                return
            ev = self._model.events[int(index)]
            topic = ev.topic or ""
            if not is_injectable_topic(topic):
                self._inject_panel.record_result(
                    int(index),
                    injected=False,
                    topic=topic,
                    reason=t("MVP 仅 EgoMotion"),
                    t_ns=ev.t_ns,
                )
                self._inject_panel.set_detail(
                    t("跳过 #{index} {topic}（MVP 仅 EgoMotion）").format(
                        index=index, topic=topic
                    )
                )
                return
            # Keep board A/B covering playhead (session index); SIL logs LOAD A|B.
            if self._inject_helper.ensure_cover(self._model, int(index)):
                self._inject_panel.set_detail(
                    t("窗口重载 session_idx≈{idx}（A/B）").format(idx=index)
                )
                self._poll_inject_msgs(self._inject.poll_messages())
            kind, _topic = self._inject_helper.inject_model_index(
                self._model, int(index)
            )
            if kind == "sent":
                self._poll_inject_msgs(self._inject.poll_messages())
        except ConnectionError as exc:
            self.statusBar().showMessage(f'{t("inject seek 失败")}：{exc}', 4000)
            self._disconnect_inject()
        finally:
            self._inject_syncing = False

    def _resync_views_from_model(self) -> None:
        """Rebuild Order/DAG/Graphics after unfreezing Live view."""
        self._order.set_model(self._model)
        self._dag.set_model(self._model)
        self._inject_panel.set_model(self._model)
        self._var_strip.set_model(self._model)
        self._tags.set_clock(self._model.clock)

    def _append_live_rows(self, rows: list[dict[str, Any]]) -> None:
        follow = self._follow_latest.isChecked()
        keep_idx = self._slider.value()
        prev_n = len(self._model.events)
        added = self._model.append_rows(rows, sor=self._sor)
        if added <= 0:
            # session_meta-only update still refreshes clock on tags
            self._tags.set_clock(self._model.clock)
            return
        n = len(self._model.events)
        # Always grow timeline / keep recording path; freeze only skips view widgets.
        self._slider.blockSignals(True)
        self._slider.setEnabled(True)
        self._slider.setMaximum(max(0, n - 1))
        if not follow:
            self._slider.setValue(min(keep_idx, n - 1))
        self._slider.blockSignals(False)
        self._inject_panel.set_model(self._model)

        proj = f"{self._project_dir.name} · " if self._project_dir else ""
        mode = ""
        if self._live_active:
            mode = t(" [跟随]") if follow else t(" [冻屏]")
            if self._live_log_fp is not None:
                mode += t("·录制")
        if self._session_path:
            self._path_label.setText(f"{proj}{self._session_path} · {n} events{mode}")
        elif self._live_active:
            live_lbl = (
                t("Live 录制中")
                if self._btn_live_rec.isChecked()
                else t("Live 旁观（未录制）")
            )
            self._path_label.setText(f"{proj}{live_lbl} · {n} events{mode}")

        if not follow:
            # Freeze view: keep receiving into model (+ disk if Record), no UI jump.
            self._stick_tail = False
            return

        self._order.append_events(self._model, from_index=prev_n)
        self._dag.set_model(self._model)
        self._var_strip.notify_model_grew()
        self._tags.set_clock(self._model.clock)
        self._stick_tail = True
        now_ms = int(time.monotonic() * 1000)
        if now_ms - self._last_follow_seek_ms >= 100:
            self._last_follow_seek_ms = now_ms
            self._seek_index(n - 1)
        else:
            self._slider.blockSignals(True)
            self._slider.setValue(n - 1)
            self._slider.blockSignals(False)




    def _live_tag_marker(self) -> None:
        msg = self._tags.live_drop_marker()
        self.statusBar().showMessage(msg, 4000)
        self._tabs.setCurrentWidget(self._tags)

    def _live_tag_from(self) -> None:
        msg = self._tags.live_mark_from()
        self.statusBar().showMessage(msg, 4000)
        self._tabs.setCurrentWidget(self._tags)

    def _live_tag_to(self) -> None:
        msg = self._tags.live_mark_to()
        self.statusBar().showMessage(msg, 5000)
        self._tabs.setCurrentWidget(self._tags)

    def _seek_ns(self, t_ns: object) -> None:
        if self._model.empty:
            return
        try:
            seek_t = int(t_ns)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        self._pause_follow_latest()
        idx = self._model.nearest_index(seek_t)
        self._seek_index(idx)
        self.statusBar().showMessage(f'{t("跳转到")} t≈{seek_t}  → #{idx}', 3000)

    def load_project(
        self, project: Path, *, offer_session: bool = True
    ) -> None:
        """Accept project.yaml or its parent SKU directory (same as CLI --project)."""
        p = project.resolve()
        if p.is_file() and p.name in {"project.yaml", "project.yml"}:
            proj_dir = p.parent
        elif p.is_dir():
            proj_dir = p
            if not (proj_dir / "project.yaml").is_file() and not (
                proj_dir / "project.yml"
            ).is_file():
                QMessageBox.warning(
                    self,
                    t("项目"),
                    t("{dir}\n下未找到 project.yaml\n请选 SKU 目录或其 project.yaml（与 gf-config 同一入口）。").format(
                        dir=proj_dir
                    ),
                )
                return
        elif p.is_file():
            QMessageBox.warning(
                self,
                t("项目"),
                t("请选择 project.yaml，而不是：\n{name}").format(name=p.name),
            )
            return
        else:
            QMessageBox.warning(self, t("项目"), f'{t("路径不存在")}：\n{p}')
            return

        self._project_dir = proj_dir
        sor = proj_dir / "gf.sor.json"
        if not sor.is_file():
            QMessageBox.warning(
                self,
                t("项目"),
                t("未找到 {sor}\n请先在 gf-config Verify / Compose。").format(sor=sor),
            )
            self._path_label.setText(t("项目={dir}（无 SOR）").format(dir=proj_dir))
            self._refresh_project_gate()
            return
        with sor.open(encoding="utf-8") as f:
            self._sor = json.load(f)
        self._dag.set_topology(self._sor)
        if self._model.events:
            self._model.bind_sor(self._sor)
            self._order.set_model(self._model)
            self._inject_panel.set_model(self._model)
            self._var_strip.set_model(self._model)
            self._seek_index(self._slider.value())
        self._refresh_project_gate()
        # offer latest session if present (skip when CLI already passes --session)
        cand = self._default_obs_dir() / "session.jsonl"
        if (
            offer_session
            and cand.is_file()
            and self._session_path is None
        ):
            reply = QMessageBox.question(
                self,
                t("打开 session？"),
                t("发现 {cand}\n是否加载？（也可先 run_sil 再 GUI「连接」）").format(cand=cand),
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.load_session_path(cand)

    def _apply_model(self) -> None:
        self._order.set_model(self._model)
        self._dag.set_model(self._model)
        self._dag.set_topology(self._sor)
        self._tags.set_session(self._session_path, clock=self._model.clock)
        self._inject_panel.set_model(self._model)
        self._var_strip.set_model(self._model)
        n = len(self._model.events)
        self._slider.blockSignals(True)
        self._slider.setEnabled(n > 0)
        self._slider.setMinimum(0)
        self._slider.setMaximum(max(0, n - 1))
        self._slider.setValue(0)
        self._slider.blockSignals(False)
        proj = f"{self._project_dir.name} · " if self._project_dir else ""
        self._path_label.setText(
            f"{proj}{self._session_path} · {n} events"
            if self._session_path
            else f"{proj}{n} events"
        )
        # GMT session is authoritative — re-declare + reset board buffers
        if (
            self._inject_active
            and self._inject is not None
            and self._inject.connected
            and self._inject_helper is not None
        ):
            try:
                self._inject_helper.configure_session(n)
                self._inject_panel.clear_results()
                if n > 0:
                    self._inject_helper.ensure_windows_around(self._model, 0)
                detail = (
                    f"stream session events={n} · "
                    f"window≤{self._inject_helper.window_size}"
                )
                self._inject_panel.set_detail(detail)
            except ConnectionError as exc:
                self.statusBar().showMessage(f'{t("inject session 重置失败")}：{exc}', 4000)
                self._disconnect_inject()
                return
        if n:
            self._seek_index(0)
        self.statusBar().showMessage(t("已加载 session"), 3000)

    def _load_clip_path(self, path: object) -> None:
        p = Path(str(path))
        try:
            self._session_path = p
            self._model = load_session(p, sor=self._sor)
            self._apply_model()
            self._tabs.setCurrentWidget(self._order)
            QMessageBox.information(self, "clip", f'{t("已加载 clip")}：\n{p}')
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "clip", str(exc))

    def _open_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("打开 session JSONL"),
            str(self._default_obs_dir()),
            "JSONL (*.jsonl);;All (*)",
        )
        if not path:
            return
        try:
            self.load_session_path(Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("打开失败"), str(exc))

    def _open_project(self) -> None:
        start = self._project_dir or (Path.cwd() / "projects")
        hint = start / "project.yaml"
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("打开 project.yaml"),
            str(hint if hint.is_file() else start),
            "project.yaml (project.yaml);;YAML (*.yaml *.yml);;All (*)",
        )
        if path:
            self.load_project(Path(path))
            self.statusBar().showMessage(f'{t("已加载项目")} {path}', 4000)

    def _open_project_dir(self) -> None:
        start = str(self._project_dir or Path.cwd() / "projects")
        path = QFileDialog.getExistingDirectory(self, t("选择项目目录（备选）"), start)
        if path:
            self.load_project(Path(path))
            self.statusBar().showMessage(f'{t("已加载项目")} {path}', 4000)



    def _export_mcap(self) -> None:
        if self._session_path is None or not self._session_path.is_file():
            QMessageBox.information(self, t("导出"), t("请先打开 session"))
            return
        out, _ = QFileDialog.getSaveFileName(
            self,
            t("导出 MCAP"),
            str(self._session_path.with_suffix(".mcap")),
            "MCAP (*.mcap)",
        )
        if not out:
            return
        out_path = Path(out)
        if out_path.suffix.lower() != ".mcap":
            out_path = out_path.with_suffix(".mcap")
        try:
            export_session_jsonl(self._session_path, out_path)
            QMessageBox.information(self, t("导出"), f'{t("已写入")} {out_path}')
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("导出失败"), str(exc))

    def _export_vcd(self) -> None:
        if self._session_path is None or not self._session_path.is_file():
            QMessageBox.information(self, t("导出"), t("请先打开 session"))
            return
        from gf_gmt.measure_vcd import export_session_vcd

        out, _ = QFileDialog.getSaveFileName(
            self,
            t("导出 VCD（GTKWave）"),
            str(self._session_path.with_suffix(".vcd")),
            "VCD (*.vcd)",
        )
        if not out:
            return
        out_path = Path(out)
        if out_path.suffix.lower() != ".vcd":
            out_path = out_path.with_suffix(".vcd")
        try:
            path, n_vars, n_ev = export_session_vcd(self._session_path, out_path)
            QMessageBox.information(
                self,
                t("导出"),
                t("已写入 {path}\nvars={n_vars} events={n_ev}\n打开：gtkwave {path}").format(
                    path=path, n_vars=n_vars, n_ev=n_ev
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("导出失败"), str(exc))

    def _export_dot(self) -> None:
        if not self._sor:
            QMessageBox.information(self, t("导出"), t("请先加载 SOR / 项目"))
            return
        from gf_gmt.architect import dag_from_sor, dag_to_dot

        out, _ = QFileDialog.getSaveFileName(
            self,
            t("导出 Graphviz .dot"),
            str(self._default_obs_dir() / "dag.dot"),
            "Graphviz (*.dot)",
        )
        if not out:
            return
        out_path = Path(out)
        if out_path.suffix.lower() != ".dot":
            out_path = out_path.with_suffix(".dot")
        out_path.write_text(dag_to_dot(dag_from_sor(self._sor)), encoding="utf-8")
        QMessageBox.information(self, t("导出"), f'{t("已写入")} {out_path}')

    def _start_foxglove_replay(self) -> None:
        if self._session_path is None or not self._session_path.is_file():
            QMessageBox.information(self, "Foxglove", t("请先打开 session"))
            return
        self._stop_foxglove()
        # Prefer 8768 so GUI offline replay does not fight SIL live Foxglove (:8765).
        port = 8768
        try:
            import socket

            with socket.create_connection(("127.0.0.1", 8765), timeout=0.2):
                sil_live = True
        except OSError:
            sil_live = False
        if not sil_live:
            port = 8765
        gmt = shutil.which("GMT")
        cmd_base = [
            "bridge",
            "foxglove",
            "--ws",
            "--jsonl",
            str(self._session_path),
            "--synth-bev",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        if gmt:
            cmd = [gmt, *cmd_base]
        else:
            cmd = [sys.executable, "-m", "gf_gmt.cli", *cmd_base]
        self._fox_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.3)
        if self._fox_proc.poll() is not None:
            QMessageBox.critical(
                self,
                "Foxglove",
                t("进程已退出（码 {code}）。\n检查端口 {port} 是否被占用，或用 CLI 调试。").format(
                    code=self._fox_proc.returncode, port=port
                ),
            )
            self._fox_proc = None
            return
        tip = ""
        if port != 8765:
            tip = (
                t("\n（检测到 :8765 已被占用，多半是 SIL live；"
                "离线回放改用本端口，勿与 live 混连。）")
            )
        QMessageBox.information(
            self,
            "Foxglove",
            t("已启动 WS 回放：ws://127.0.0.1:{port}\n").format(port=port)
            + t("Foxglove Studio → Open connection。")
            + tip,
        )
        self.statusBar().showMessage(
            t("Foxglove 回放已启动 ws://127.0.0.1:{port}").format(port=port),
            5000,
        )

    def _stop_foxglove(self) -> None:
        if self._fox_proc is not None and self._fox_proc.poll() is None:
            self._fox_proc.terminate()
            try:
                self._fox_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._fox_proc.kill()
        self._fox_proc = None


    def _toggle_play(self) -> None:
        if self._model.empty:
            return
        self._playing = not self._playing
        self._btn_play.setText(t("暂停") if self._playing else t("播放"))
        if self._playing:
            self._timer.start(self._next_interval_ms())
        else:
            self._timer.stop()

    def _next_interval_ms(self) -> int:
        # Spinbox = speed percent (100 = default). Larger → shorter interval → faster.
        speed_pct = max(10, int(self._rate.value()))
        if not self._use_dt.isChecked() or self._model.empty:
            return max(1, int(200.0 * 100.0 / speed_pct))
        cur = self._slider.value()
        nxt = min(cur + 1, len(self._model.events) - 1)
        dt = self._model.events[nxt].dt_ns if nxt > cur else 0
        if dt <= 0:
            return max(1, int(200.0 * 100.0 / speed_pct))
        # 1e6 ns → 1 ms at 100%; scale by speed%
        scaled = int(dt / 1_000_000.0 * (100.0 / speed_pct))
        return max(1, min(scaled, 5000))

    def _on_tick(self) -> None:
        if self._model.empty:
            self._toggle_play()
            return
        cur = self._slider.value()
        if cur >= self._slider.maximum():
            # Loop only while inject TCP is up (checkbox lives on Inject tab).
            if (
                self._inject_active
                and self._inject is not None
                and self._inject.connected
                and self._inject_panel.wants_loop_confirm()
            ):
                self._restart_inject_loop(keep_playing=True)
                return
            self._toggle_play()
            return
        self._slider.setValue(cur + 1)
        if self._playing:
            self._timer.setInterval(self._next_interval_ms())

    def _step_once(self) -> None:
        if self._model.empty:
            return
        cur = self._slider.value()
        if cur < self._slider.maximum():
            self._slider.setValue(cur + 1)

    def _step_back(self) -> None:
        if self._model.empty:
            return
        self._pause_follow_latest()
        cur = self._slider.value()
        if cur > 0:
            self._slider.setValue(cur - 1)

    def _jump_start(self) -> None:
        if not self._model.empty:
            self._pause_follow_latest()
            self._slider.setValue(0)

    def _jump_end(self) -> None:
        if not self._model.empty:
            if not self._inject_panel.wants_playhead_sync():
                self._follow_latest.setChecked(True)
            self._slider.setValue(self._slider.maximum())

    def _pause_follow_latest(self) -> None:
        """Scrub / 单步后退时退出跟播，继续记盘。"""
        self._stick_tail = False
        if self._follow_latest.isChecked():
            self._follow_latest.blockSignals(True)
            self._follow_latest.setChecked(False)
            self._follow_latest.blockSignals(False)
            self._refresh_live_state_label()

    def _on_slider(self, value: int) -> None:
        # 拖离尾部 → 自动取消跟随最新
        if not self._model.empty and value < self._slider.maximum():
            self._pause_follow_latest()
        elif (
            value >= self._slider.maximum()
            and self._live_active
            and not self._inject_panel.wants_playhead_sync()
        ):
            # 拖回尾部：恢复跟随（回灌 playhead 时不恢复，避免冲突）
            if not self._follow_latest.isChecked():
                self._follow_latest.blockSignals(True)
                self._follow_latest.setChecked(True)
                self._follow_latest.blockSignals(False)
                self._refresh_live_state_label()
            self._stick_tail = True
        self._seek_index(value)

    def _seek_index(self, index: int) -> None:
        if self._model.empty:
            self._t_label.setText("t=—")
            self._tags.set_playhead_ns(None)
            return
        index = max(0, min(int(index), len(self._model.events) - 1))
        if self._slider.value() != index:
            self._slider.blockSignals(True)
            self._slider.setValue(index)
            self._slider.blockSignals(False)
        ev = self._model.events[index]
        live = ""
        if self._live_active:
            live = t(" 跟随") if self._follow_latest.isChecked() else ""
            if self._live_log_fp is not None:
                live += t(" 录制")
        wall = self._model.wall_str(ev.t_ns)
        # Dedicated clock row — full wall (not compact); tooltip mirrors text.
        clock_txt = (
            f'{t("Wall")}={wall}   t_ns={ev.t_ns}   '
            f"#{index}/{len(self._model.events) - 1}{live}"
        )
        self._t_label.setText(clock_txt)
        self._t_label.setToolTip(clock_txt)
        self._order.highlight_upto(index)
        self._dag.set_playhead_index(index)
        self._var_strip.set_playhead_index(index)
        self._inject_panel.highlight_upto(index)
        self._tags.set_playhead_ns(ev.t_ns)
        self._inject_seek(index)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        try:
            self._dlt_panel.shutdown()
        except Exception:
            pass
        self._ws_timer.stop()
        self._inject_timer.stop()
        if self._live_active:
            self._disconnect_live()
        if self._inject is not None:
            self._disconnect_inject()
        self._stop_foxglove()
        super().closeEvent(event)


def run_gui(
    *,
    session: Path | None = None,
    sor: Path | None = None,
    project: Path | None = None,
) -> int:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication
    from gf_gmt.i18n import load_language

    QCoreApplication.setOrganizationName("GiraffeFlow")
    QCoreApplication.setApplicationName("gf-gmt")
    load_language()
    app = QApplication.instance() or QApplication(sys.argv)
    win = GmtMainWindow()
    if project:
        win.load_project(project, offer_session=session is None)
    if sor and sor.is_file():
        with sor.open(encoding="utf-8") as f:
            win._sor = json.load(f)
        win._dag.set_topology(win._sor)
    if session and session.is_file():
        win.load_session_path(session, sor_path=sor)
    win.show()
    return app.exec()
