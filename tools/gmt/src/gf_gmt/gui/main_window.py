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
from gf_gmt.gui.inject_panel import InjectPanel
from gf_gmt.gui.live_client import LiveWsSession
from gf_gmt.gui.order_view import OrderRaceView
from gf_gmt.gui.session_model import (
    SessionFileTail,
    SessionModel,
    load_session,
    write_session_meta_line,
)
from gf_gmt.gui.tag_panel import TagPanel
from gf_gmt.gui.var_strip_view import VarStripView
from gf_gmt.gui.wall_time import SessionClock
from gf_gmt.measure_export import export_session_jsonl
from gf_gmt.measure_ndjson import parse_session_line, record_from_ndjson
from gf_gmt.measure_record import record_from_sil_logs


class GmtMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GMT — 选项目 → Live / 回灌 / Tag / 回放")
        self.resize(1380, 780)
        self._model = SessionModel()
        self._sor: dict[str, Any] | None = None
        self._session_path: Path | None = None
        self._project_dir: Path | None = None
        self._fox_proc: subprocess.Popen[bytes] | None = None
        self._ws: LiveWsSession | None = None
        self._live_log_fp: TextIO | None = None
        self._live_active = False
        self._inject: InjectCtrlClient | None = None
        self._inject_helper: InjectStreamHelper | None = None
        self._inject_stream = False  # hello caps contains stream_window
        self._inject_active = False
        self._inject_syncing = False  # avoid re-entrant seek storms
        self._inject_last_ok: bool | None = None  # None=unknown, True=green, False=red
        self._inject_eof_asking = False  # avoid stacked eof dialogs
        self._playing = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._tail = SessionFileTail()
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(250)
        self._follow_timer.timeout.connect(self._on_follow_tick)
        self._ws_timer = QTimer(self)
        self._ws_timer.setInterval(50)
        self._ws_timer.timeout.connect(self._on_ws_tick)
        self._inject_timer = QTimer(self)
        self._inject_timer.setInterval(100)
        self._inject_timer.timeout.connect(self._on_inject_tick)
        self._stick_tail = True  # when following, keep playhead at end

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # —— 统一连接条：共用 Host；Live ws:8766 与 回灌 tcp:8767 同级 ——
        conn = QHBoxLayout()
        self._btn_proj = QPushButton("加载项目…")
        self._btn_proj.setToolTip(
            "选择 project.yaml（与 gf-config / codegen 同一入口；SOR 在同目录）"
        )
        self._btn_proj.clicked.connect(self._open_project)
        conn.addWidget(self._btn_proj)
        conn.addWidget(QLabel("Host"))
        self._host_edit = QLineEdit("127.0.0.1")
        self._host_edit.setToolTip(
            "SIL / 观测机地址（本机 127.0.0.1；远端填局域网 IP）\n"
            "Live 与回灌共用此 Host"
        )
        self._host_edit.setMaximumWidth(140)
        conn.addWidget(self._host_edit)

        conn.addWidget(QLabel("│ Live ws"))
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(DEFAULT_LIVE_PORT)
        self._port_spin.setToolTip(f"Live WebSocket 端口（默认 {DEFAULT_LIVE_PORT}）")
        self._port_spin.setMaximumWidth(72)
        conn.addWidget(self._port_spin)
        self._btn_live_connect = QPushButton("连接")
        self._btn_live_connect.setToolTip(
            "连 live_tap 旁路（ws:8766）；默认只看流不落盘，需落盘请点「录制」"
        )
        self._btn_live_connect.clicked.connect(self._connect_live)
        self._btn_live_disconnect = QPushButton("断开")
        self._btn_live_disconnect.setEnabled(False)
        self._btn_live_disconnect.clicked.connect(self._disconnect_live)
        self._btn_live_rec = QPushButton("录制")
        self._btn_live_rec.setCheckable(True)
        self._btn_live_rec.setEnabled(False)
        self._btn_live_rec.setToolTip(
            "将 Live 流落盘；已有 session_live.jsonl 时可新建或覆盖"
        )
        self._btn_live_rec.toggled.connect(self._on_live_record_toggled)
        self._live_state = QLabel("空闲")
        self._live_state.setStyleSheet("color:#555; min-width: 4.5em;")
        conn.addWidget(self._btn_live_connect)
        conn.addWidget(self._btn_live_disconnect)
        conn.addWidget(self._btn_live_rec)
        conn.addWidget(self._live_state)

        conn.addWidget(QLabel("│ 回灌 tcp"))
        self._inject_port_spin = QSpinBox()
        self._inject_port_spin.setRange(1, 65535)
        self._inject_port_spin.setValue(DEFAULT_INJECT_PORT)
        self._inject_port_spin.setToolTip(
            f"inject 控制口（默认 {DEFAULT_INJECT_PORT}，GF_INJECT_PORT）"
        )
        self._inject_port_spin.setMaximumWidth(72)
        conn.addWidget(self._inject_port_spin)
        self._btn_inject_connect = QPushButton("连接")
        self._btn_inject_connect.setToolTip(
            "连 playhead inject（TCP JSON）；需 GF_INJECT_MODE=playhead"
        )
        self._btn_inject_connect.clicked.connect(self._on_inject_connect_clicked)
        self._btn_inject_disconnect = QPushButton("断开")
        self._btn_inject_disconnect.setEnabled(False)
        self._btn_inject_disconnect.clicked.connect(self._disconnect_inject)
        self._inject_state = QLabel("空闲")
        self._inject_state.setStyleSheet("color:#555; min-width: 4.5em;")
        conn.addWidget(self._btn_inject_connect)
        conn.addWidget(self._btn_inject_disconnect)
        conn.addWidget(self._inject_state)

        self._follow_latest = QCheckBox("跟随最新")
        self._follow_latest.setChecked(True)
        self._follow_latest.setToolTip(
            "仅影响 playhead：开=贴最新；关=停在当前帧（与是否录制落盘无关）"
        )
        self._follow_latest.toggled.connect(self._on_follow_latest_toggled)
        conn.addWidget(self._follow_latest)
        conn.addStretch(1)
        root.addLayout(conn)

        self._proj_banner = QLabel(
            "⚠ 请先「加载项目…」选择 project.yaml（回灌已禁用；Live 仍可旁观）"
        )
        self._proj_banner.setWordWrap(True)
        self._proj_banner.setStyleSheet(
            "background:#e65100; color:#ffffff; padding:10px 12px; "
            "border:2px solid #bf360c; font-weight:700; font-size:13px;"
        )
        root.addWidget(self._proj_banner)

        transport = QHBoxLayout()
        self._btn_open = QPushButton("打开 session…")
        self._btn_open.clicked.connect(self._open_session)
        self._btn_record = QPushButton("从日志录制…")
        self._btn_record.clicked.connect(self._record_from_logs)
        self._btn_sor = QPushButton("加载 SOR…")
        self._btn_sor.clicked.connect(self._open_sor)
        self._btn_live = QPushButton("仅跟随文件…")
        self._btn_live.setToolTip("高级：不连 WS，只尾随已有 JSONL")
        self._btn_live.clicked.connect(self._open_live_follow)
        self._btn_home = QPushButton("|◀")
        self._btn_home.setToolTip("跳到开头")
        self._btn_home.clicked.connect(self._jump_start)
        self._btn_back = QPushButton("◀")
        self._btn_back.setToolTip("后退一步")
        self._btn_back.clicked.connect(self._step_back)
        self._btn_play = QPushButton("播放")
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_step = QPushButton("▶")
        self._btn_step.setToolTip("前进一步")
        self._btn_step.clicked.connect(self._step_once)
        self._btn_end = QPushButton("▶|")
        self._btn_end.setToolTip("跳到末尾")
        self._btn_end.clicked.connect(self._jump_end)
        self._btn_fox = QPushButton("Foxglove")
        self._btn_fox.clicked.connect(self._start_foxglove_replay)
        self._btn_mcap = QPushButton("导出 MCAP")
        self._btn_mcap.clicked.connect(self._export_mcap)

        for w in (
            self._btn_open,
            self._btn_record,
            self._btn_sor,
            self._btn_live,
            self._btn_home,
            self._btn_back,
            self._btn_play,
            self._btn_step,
            self._btn_end,
            self._btn_fox,
            self._btn_mcap,
        ):
            transport.addWidget(w)

        transport.addWidget(QLabel("速率"))
        self._rate = QSpinBox()
        self._rate.setRange(1, 2000)
        self._rate.setValue(200)
        self._rate.setToolTip("事件步进：毫秒/步；勾选「按 Δt」时为相对时间倍速分母")
        transport.addWidget(self._rate)
        self._use_dt = QCheckBox("按 Δt")
        self._use_dt.setToolTip("播放间隔按相邻事件 Δt（缩放：rate 为 ms 对应 1e6 ns 的基准）")
        transport.addWidget(self._use_dt)
        self._follow = QCheckBox("跟随文件")
        self._follow.setToolTip(
            "轮询 JSONL 新行（「仅跟随 live 文件」用）。"
            "是否跳到最新由上方「跟随最新」决定。"
        )
        self._follow.toggled.connect(self._on_follow_toggled)
        transport.addWidget(self._follow)
        transport.addStretch(1)
        self._t_label = QLabel("t=—")
        transport.addWidget(self._t_label)
        root.addLayout(transport)

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
        self._var_strip = VarStripView()
        self._var_strip.seek_ns_requested.connect(self._seek_ns)
        self._tabs.addTab(self._order, "先后 / 竞态")
        self._tabs.addTab(self._dag, "动画 DAG")
        self._tabs.addTab(self._var_strip, "变量轨")
        self._tabs.addTab(self._tags, "Tag 编辑")
        self._tabs.addTab(self._inject_panel, "回灌")
        root.addWidget(self._tabs, stretch=1)

        status = QStatusBar()
        self._path_label = QLabel(
            "请先加载项目 → 填 Host → Live(ws:8766) 或 回灌(tcp:8767) 点「连接」"
        )
        status.addWidget(self._path_label, stretch=1)
        self.setStatusBar(status)

        self._build_menus()
        self._refresh_project_gate()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        act_proj = QAction("加载项目…", self)
        act_proj.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_proj.triggered.connect(self._open_project)
        file_menu.addAction(act_proj)
        act_proj_dir = QAction("加载项目目录…", self)
        act_proj_dir.setToolTip("备选：直接选 SKU 目录（等价于该目录下的 project.yaml）")
        act_proj_dir.triggered.connect(self._open_project_dir)
        file_menu.addAction(act_proj_dir)

        act_sess = QAction("打开 session JSONL…", self)
        act_sess.setShortcut(QKeySequence.StandardKey.Open)
        act_sess.triggered.connect(self._open_session)
        file_menu.addAction(act_sess)

        act_rec = QAction("从 SIL 日志录制…", self)
        act_rec.triggered.connect(self._record_from_logs)
        file_menu.addAction(act_rec)

        act_ndjson = QAction("从 tap NDJSON 导入…", self)
        act_ndjson.triggered.connect(self._import_ndjson)
        file_menu.addAction(act_ndjson)

        act_live = QAction("仅跟随 live 文件…", self)
        act_live.triggered.connect(self._open_live_follow)
        file_menu.addAction(act_live)

        act_sor = QAction("加载 gf.sor.json…", self)
        act_sor.triggered.connect(self._open_sor)
        file_menu.addAction(act_sor)

        file_menu.addSeparator()
        act_mcap = QAction("导出 MCAP…", self)
        act_mcap.triggered.connect(self._export_mcap)
        file_menu.addAction(act_mcap)

        act_vcd = QAction("导出 VCD（GTKWave）…", self)
        act_vcd.triggered.connect(self._export_vcd)
        file_menu.addAction(act_vcd)

        act_dot = QAction("导出 Graphviz .dot…", self)
        act_dot.triggered.connect(self._export_dot)
        file_menu.addAction(act_dot)

        file_menu.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        conn_menu = self.menuBar().addMenu("连接")
        act_start = QAction("连接 Live (ws)", self)
        act_start.setShortcut(QKeySequence("Ctrl+R"))
        act_start.triggered.connect(self._connect_live)
        conn_menu.addAction(act_start)
        act_stop = QAction("断开 Live", self)
        act_stop.setShortcut(QKeySequence("Ctrl+Shift+R"))
        act_stop.triggered.connect(self._disconnect_live)
        conn_menu.addAction(act_stop)
        conn_menu.addSeparator()
        act_inj = QAction("连接回灌 (tcp)", self)
        act_inj.setShortcut(QKeySequence("Ctrl+I"))
        act_inj.triggered.connect(self._on_inject_connect_clicked)
        conn_menu.addAction(act_inj)
        act_inj_off = QAction("断开回灌", self)
        act_inj_off.setShortcut(QKeySequence("Ctrl+Shift+I"))
        act_inj_off.triggered.connect(self._disconnect_inject)
        conn_menu.addAction(act_inj_off)

        replay_menu = self.menuBar().addMenu("回放")
        act_play = QAction("播放 / 暂停", self)
        act_play.setShortcut(QKeySequence(Qt.Key.Key_Space))
        act_play.triggered.connect(self._toggle_play)
        replay_menu.addAction(act_play)
        act_step = QAction("前进一步", self)
        act_step.setShortcut(QKeySequence(Qt.Key.Key_Right))
        act_step.triggered.connect(self._step_once)
        replay_menu.addAction(act_step)
        act_back = QAction("后退一步", self)
        act_back.setShortcut(QKeySequence(Qt.Key.Key_Left))
        act_back.triggered.connect(self._step_back)
        replay_menu.addAction(act_back)
        act_home = QAction("跳到开头", self)
        act_home.setShortcut(QKeySequence(Qt.Key.Key_Home))
        act_home.triggered.connect(self._jump_start)
        replay_menu.addAction(act_home)
        act_end = QAction("跳到末尾", self)
        act_end.setShortcut(QKeySequence(Qt.Key.Key_End))
        act_end.triggered.connect(self._jump_end)
        replay_menu.addAction(act_end)
        replay_menu.addSeparator()
        act_fox = QAction("打开 Foxglove 回放…", self)
        act_fox.triggered.connect(self._start_foxglove_replay)
        replay_menu.addAction(act_fox)
        act_fox_stop = QAction("停止 Foxglove 回放进程", self)
        act_fox_stop.triggered.connect(self._stop_foxglove)
        replay_menu.addAction(act_fox_stop)
        replay_menu.addSeparator()
        act_follow = QAction("切换跟随最新", self)
        act_follow.setShortcut(QKeySequence(Qt.Key.Key_F))
        act_follow.triggered.connect(
            lambda: self._follow_latest.setChecked(
                not self._follow_latest.isChecked()
            )
        )
        replay_menu.addAction(act_follow)

        tag_menu = self.menuBar().addMenu("Tag")
        act_mark = QAction("钉标记点 ●", self)
        act_mark.setShortcut(QKeySequence(Qt.Key.Key_M))
        act_mark.triggered.connect(self._live_tag_marker)
        tag_menu.addAction(act_mark)
        act_tag_from = QAction("片段 from ← playhead", self)
        act_tag_from.setShortcut(QKeySequence(Qt.Key.Key_BracketLeft))
        act_tag_from.triggered.connect(self._live_tag_from)
        tag_menu.addAction(act_tag_from)
        act_tag_to = QAction("片段 to ← playhead 并保存", self)
        act_tag_to.setShortcut(QKeySequence(Qt.Key.Key_BracketRight))
        act_tag_to.triggered.connect(self._live_tag_to)
        tag_menu.addAction(act_tag_to)

        view_menu = self.menuBar().addMenu("视图")
        view_menu.addAction("先后 / 竞态", lambda: self._tabs.setCurrentWidget(self._order))
        view_menu.addAction("动画 DAG", lambda: self._tabs.setCurrentWidget(self._dag))
        view_menu.addAction("变量轨", lambda: self._tabs.setCurrentWidget(self._var_strip))
        view_menu.addAction("Tag 编辑", lambda: self._tabs.setCurrentWidget(self._tags))
        view_menu.addAction("回灌", lambda: self._tabs.setCurrentWidget(self._inject_panel))

    def _refresh_project_gate(self) -> None:
        """未加载项目：醒目提示；回灌连接由 _refresh_conn_bar_ui 按项目态禁用。"""
        has = self._project_dir is not None and self._sor is not None
        self._proj_banner.setVisible(not has)
        if has:
            self._btn_proj.setText(f"项目: {self._project_dir.name}")
            self._btn_proj.setStyleSheet("font-weight:700;")
        else:
            self._proj_banner.setText(
                "⚠ 请先「加载项目…」选择 project.yaml（回灌已禁用；Live 仍可旁观）"
            )
            self._btn_proj.setText("加载项目…")
            self._btn_proj.setStyleSheet("")
        self._refresh_conn_bar_ui()

    def _default_live_session(self) -> Path:
        return self._default_obs_dir() / "session_live.jsonl"

    def _set_live_ui(self, active: bool) -> None:
        self._live_active = active
        self._refresh_conn_bar_ui()

    def _set_inject_ui(self, active: bool) -> None:
        self._inject_active = active
        self._refresh_conn_bar_ui()

    def _refresh_conn_bar_ui(self) -> None:
        """Live 与回灌可并行；回灌按最近一帧红/绿。"""
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
            self._btn_inject_connect.setToolTip("请先加载 project.yaml 后再连接回灌")
        else:
            self._btn_inject_connect.setToolTip(
                "连 playhead inject（TCP JSON）；需 GF_INJECT_MODE=playhead"
            )

        green = "color:#2e7d32; font-weight:700; min-width: 5em;"
        idle_s = "color:#555; min-width: 5em;"

        if live_on:
            self._live_state.setText("已连接")
            self._live_state.setStyleSheet(green)
        else:
            self._live_state.setText("空闲")
            self._live_state.setStyleSheet(idle_s)

        if inj_on:
            self._inject_state.setText("已连接")
            self._inject_state.setStyleSheet(green)
        else:
            self._inject_state.setText("空闲")
            self._inject_state.setStyleSheet(idle_s)
            self._inject_last_ok = None

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
            self.setWindowTitle("GMT — 选项目 → Live / 回灌 / Tag / 回放")

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
                "回灌「跟 playhead 灌」已开 → Live 跟随已禁用（仍可连 Live 旁观/录制）",
                5000,
            )
            return
        self._stick_tail = on
        self._refresh_live_state_label()
        if not self._live_active:
            return
        if on and not self._model.empty:
            self._seek_index(len(self._model.events) - 1)
            self.statusBar().showMessage("跟随最新 ON — 贴最新事件", 2500)
        else:
            self.statusBar().showMessage(
                "跟随最新 OFF — playhead 不跟播（可 scrub / Tag）",
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
        d = Path.cwd() / "build" / "observability"
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
        self._tail.reset(path)
        if path.is_file():
            self._tail.offset = path.stat().st_size
            self._tail.partial = ""
        self._apply_model()

    def _write_live_session_meta_if_needed(self, first_t_ns: int) -> None:
        """Scheme-1: one meta line at live session start (before first event)."""
        if self._model.clock.ready:
            return
        clock = SessionClock.now_anchor(first_t_ns)
        self._model.clock = clock
        if self._live_log_fp is not None:
            write_session_meta_line(self._live_log_fp, clock)

    def start_follow(self, path: Path | None = None) -> None:
        """Open path (default session_live.jsonl) and enable tail follow."""
        p = path or self._default_live_session()
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.is_file():
            p.touch()
        self._session_path = p
        self._model = SessionModel()
        self._model.path = p
        self._model.bind_sor(self._sor)
        self._tail.reset(p)
        self._tags.set_session(p, clock=self._model.clock)
        self._dag.set_topology(self._sor)
        self._dag.set_model(self._model)
        self._inject_panel.set_model(self._model)
        self._var_strip.set_model(self._model)
        self._apply_model()
        self._follow.blockSignals(True)
        self._follow.setChecked(True)
        self._follow.blockSignals(False)
        self._stick_tail = self._follow_latest.isChecked()
        self._follow_timer.start()
        self._on_follow_tick()
        mode = "跟随最新" if self._stick_tail else "不跟播"
        self.statusBar().showMessage(f"跟随 live（{mode}）：{p}", 5000)

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
            self._btn_live_rec.setText("录制中")
            self._btn_live_rec.setStyleSheet(
                "QPushButton { background:#c62828; color:#fff; font-weight:700; "
                "border:1px solid #8e0000; padding:2px 10px; }"
            )
        else:
            self._btn_live_rec.setText("录制")
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
            box.setWindowTitle("Live 录制")
            box.setIcon(QMessageBox.Icon.Question)
            box.setText(
                f"已存在 {default.name}（{default.stat().st_size} 字节）。\n"
                "新建时间戳文件，还是覆盖？"
            )
            btn_new = box.addButton("新建", QMessageBox.ButtonRole.AcceptRole)
            btn_over = box.addButton("覆盖", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
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
            QMessageBox.critical(self, "Live 录制", f"无法写入 {path}\n{exc}")
            return False
        self._session_path = path
        self._tags.set_session(path, clock=self._model.clock)
        self._model.path = path
        # If clock already ready from live view, persist meta for the new file
        if self._model.clock.ready:
            write_session_meta_line(self._live_log_fp, self._model.clock)
        self._style_live_record_btn()
        self._refresh_conn_bar_ui()
        self.statusBar().showMessage(f"Live 录制中 → {path}", 6000)
        return True

    def _stop_live_record(self, *, quiet: bool = False) -> None:
        path = self._session_path
        self._close_live_log()
        self._style_live_record_btn()
        self._refresh_conn_bar_ui()
        if not quiet:
            self.statusBar().showMessage(
                f"Live 录制已停止"
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
        self._follow.blockSignals(True)
        self._follow.setChecked(False)
        self._follow.blockSignals(False)
        self._follow_timer.stop()
        self._stick_tail = self._follow_latest.isChecked()

    def _connect_live(self) -> None:
        """Primary UX: connect to external live bridge (view stream; record optional)."""
        if self._live_active:
            return
        if self._inject_panel.wants_playhead_sync():
            self._force_live_follow_off(
                reason="已开回灌 playhead → Live 以旁观方式连接（不跟随最新）"
            )
        if self._project_dir is None:
            reply = QMessageBox.question(
                self,
                "Live",
                "尚未加载项目（SOR / 动画 DAG / 变量轨对齐）。\n"
                "是否现在打开 project.yaml？\n\n"
                "选「否」仍可旁观连接（无 DAG）。",
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._open_project()
            if self._project_dir is None:
                self.statusBar().showMessage(
                    "Live 无项目：仅旁观（动画 DAG 为空）",
                    5000,
                )

        host = self._host_edit.text().strip() or "127.0.0.1"
        port = int(self._port_spin.value())
        self._begin_live_memory_session()

        ws = LiveWsSession()
        try:
            ws.connect(host, port)
        except (OSError, TimeoutError, ConnectionError) as exc:
            self._close_live_log()
            QMessageBox.critical(
                self,
                "Live",
                f"无法连接 ws://{host}:{port}\n{exc}\n\n"
                "Live = tap 旁路 WebSocket（默认 8766）。\n"
                "回灌 playhead 时 SIL 默认仍开 live（只订下游）；"
                "若连不上请看 run_sil 是否打印 downstream tap。\n"
                "回灌控制请用顶栏「回灌 tcp:8767」。",
            )
            return

        self._ws = ws
        self._ws_timer.start()
        self._set_live_ui(True)
        mode = "跟随最新" if self._follow_latest.isChecked() else "不跟播"
        self.statusBar().showMessage(
            f"Live 已连接 ws://{host}:{port}（{mode}；落盘请点「录制」）",
            8000,
        )

    def _disconnect_live(self) -> None:
        self._ws_timer.stop()
        if self._ws is not None:
            self._ws.close()
            self._ws = None
        was_rec = self._live_log_fp is not None
        self._stop_live_record(quiet=True) if was_rec else self._close_live_log()
        self._follow_timer.stop()
        self._follow.blockSignals(True)
        self._follow.setChecked(False)
        self._follow.blockSignals(False)
        self._set_live_ui(False)
        n = len(self._model.events)
        self.statusBar().showMessage(
            f"Live 已断开 · 保留 session（{n} events）"
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
            if row.get("type") != "session_meta" and not self._model.clock.ready:
                self._write_live_session_meta_if_needed(int(row.get("t_ns") or 0))
            if self._live_log_fp is not None:
                self._live_log_fp.write(line + "\n")
                self._live_log_fp.flush()
            rows.append(row)
        if not rows:
            return
        self._append_live_rows(rows)

    def _on_inject_connect_clicked(self) -> None:
        if self._inject_active:
            return
        if self._project_dir is None or self._sor is None:
            reply = QMessageBox.warning(
                self,
                "回灌",
                "回灌需要先加载 project.yaml（SOR / 事件对齐）。\n是否现在打开？",
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
                reason="已开「跟 playhead 灌」→ Live 跟随已关"
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
                "回灌",
                "请先打开 session JSONL（GMT 为权威源）。\n"
                "stream 模式下板端不必再设 GF_INJECT_SESSION。",
            )
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
                "回灌",
                f"无法连接 inject ctrl tcp://{host}:{port}\n{exc}\n\n"
                "远端请确认：\n"
                "1) SIL 机 GF_INJECT_MODE=playhead，且 ss 能看到 0.0.0.0:8767\n"
                "2) 防火墙放行 TCP 8767\n"
                "3) 用本页「连接 inject」，不要点上方 Live（那是 ws://8766）",
            )
            return
        self._inject = client
        helper = InjectStreamHelper(client)
        hello = client.last_hello or {}
        helper.on_hello(hello)
        self._inject_helper = helper
        self._inject_stream = helper.stream_mode
        n_inj = hello.get("events", "?")
        n_gui = len(self._model.events)
        warn = ""
        if self._inject_stream:
            try:
                helper.configure_session(n_gui)
                # Prefetch A/B once so board logs LOAD A / LOAD B (not per-scrub)
                if n_gui > 0:
                    helper.ensure_windows_around(self._model, 0)
            except ConnectionError as exc:
                self._refresh_conn_bar_ui()
                QMessageBox.critical(
                    self,
                    "回灌",
                    f"stream session/reset 失败：{exc}",
                )
                client.close()
                self._inject = None
                self._inject_helper = None
                self._inject_stream = False
                return
            detail = (
                f"tcp://{host}:{port} · stream_window · "
                f"GMT events={n_gui} · board hint={n_inj} · "
                f"window≤{helper.window_size}"
            )
        else:
            if isinstance(n_inj, int) and n_gui and n_inj != n_gui:
                warn = f"\n⚠ 事件数不一致：inject={n_inj} GUI={n_gui}（请用同一 session）"
                QMessageBox.warning(
                    self,
                    "回灌 session 不一致",
                    f"inject 侧事件数 = {n_inj}，GMT 当前 session = {n_gui}。\n\n"
                    "legacy（无 stream_window）两边必须打开同一 JSONL。\n"
                    "stream 模式请升级板端 inject，由 GMT 下发窗口。",
                )
            detail = f"tcp://{host}:{port} · inject events={n_inj} · GUI={n_gui}{warn}"
        self._inject_last_ok = None
        self._inject_eof_asking = False
        self._inject_panel.set_connected(True, detail=detail)
        self._set_inject_ui(True)
        if self._inject_panel.wants_playhead_sync():
            self._force_live_follow_off(
                reason="回灌已连且跟 playhead → Live 跟随已关（可另连 Live 旁观/录制）"
            )
        self._inject_timer.start()
        mode = "stream" if self._inject_stream else "legacy"
        self.statusBar().showMessage(
            f"Inject 已连接 tcp://{host}:{port} ({mode})",
            6000,
        )
        if not self._model.empty and self._inject_panel.wants_playhead_sync():
            self._inject_seek(self._slider.value())

    def _disconnect_inject(self) -> None:
        self._inject_timer.stop()
        if self._inject is not None:
            self._inject.close()
            self._inject = None
        self._inject_helper = None
        self._inject_stream = False
        self._inject_last_ok = None
        self._inject_eof_asking = False
        self._inject_panel.set_connected(False, detail="—")
        self._set_inject_ui(False)
        self.statusBar().showMessage("Inject 已断开", 3000)

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
                self._inject_last_ok = False
                self._refresh_conn_bar_ui()
                err = str(msg.get("msg") or "error")
                if err == "need_window":
                    # board may send error alongside need_window; fill if helper ready
                    self._on_inject_need_window(
                        {
                            "from": msg.get("from", self._slider.value()),
                            "count": msg.get("count", 64),
                            "slot": msg.get("slot"),
                        }
                    )
                    continue
                self._inject_panel.set_detail(f"回灌错误：{err}")
                idx = self._slider.value()
                if err in {"index out of range", "at end"} and idx >= 0:
                    reason = (
                        f"超出 session（{err}）"
                        if self._inject_stream
                        else (
                            f"超出 inject session（{err}）— "
                            "请确认 GF_INJECT_SESSION 与 GUI 同一文件"
                        )
                    )
                    self._inject_panel.record_result(
                        idx,
                        injected=False,
                        topic="",
                        reason=reason,
                    )
                self.statusBar().showMessage(f"回灌失败：{err}", 6000)

    def _on_inject_need_window(self, msg: dict[str, Any]) -> None:
        if (
            self._inject is None
            or self._inject_helper is None
            or not self._inject_stream
            or self._model.empty
        ):
            return
        try:
            n = self._inject_helper.handle_need_window(self._model, msg)
            self._inject_panel.set_detail(
                f"need_window from={msg.get('from')} → pushed {n} EgoMotion"
            )
        except ConnectionError as exc:
            self.statusBar().showMessage(f"填窗失败：{exc}", 4000)
            self._disconnect_inject()

    def _on_inject_eof(self, _msg: dict[str, Any]) -> None:
        if self._inject_eof_asking:
            return
        if not self._inject_panel.wants_loop_confirm():
            self._inject_panel.set_detail("eof（未勾选循环）")
            self.statusBar().showMessage("回灌到结尾", 4000)
            return
        self._inject_eof_asking = True
        try:
            reply = QMessageBox.question(
                self,
                "回灌到结尾",
                "已到 session 结尾。是否从开头继续循环？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._inject_panel.clear_results()
                if (
                    self._inject_helper is not None
                    and self._inject is not None
                    and self._inject.connected
                    and self._inject_stream
                ):
                    try:
                        self._inject_helper.configure_session(len(self._model.events))
                    except ConnectionError:
                        self._disconnect_inject()
                        return
                self._seek_index(0)
            else:
                self._inject_panel.set_detail("eof — 已停止")
        finally:
            self._inject_eof_asking = False

    def _on_inject_tick(self) -> None:
        if self._inject is None:
            return
        if not self._inject.connected:
            # Peer closed (or replaced); sync UI — do not auto-reconnect
            self._disconnect_inject()
            self.statusBar().showMessage("Inject 连接已断开", 4000)
            return
        self._poll_inject_msgs(self._inject.poll_messages())

    def _apply_inject_published(self, msg: dict[str, Any]) -> None:
        idx = msg.get("index")
        topic = str(msg.get("topic") or "?")
        injected = msg.get("injected")
        ok = injected is True or injected == "true"
        self._inject_last_ok = bool(ok)
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
                reason = "白名单未命中 / Send 失败"
            else:
                reason = "MVP 仅灌 EgoMotion，本 topic 跳过"
            self._inject_panel.record_result(
                index_i,
                injected=ok,
                topic=topic,
                reason=reason,
                t_ns=t_i,
            )
        if ok:
            self._inject_panel.set_detail(f"已发布 #{idx} {topic} t={msg.get('t_ns')}")
            self.statusBar().showMessage(f"回灌成功：#{idx} {topic} 已 Send", 3000)
        else:
            why = reason or "injected=false"
            self._inject_panel.set_detail(f"跳过 #{idx} {topic}（{why}）")
            self.statusBar().showMessage(
                f"回灌跳过：#{idx} {topic}",
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
            if self._inject_stream and self._inject_helper is not None:
                # Primary scrub path: inject_event for EgoMotion; local pink otherwise
                if self._model.empty or index < 0 or index >= len(self._model.events):
                    return
                ev = self._model.events[int(index)]
                topic = ev.topic or ""
                if not is_injectable_topic(topic):
                    self._inject_last_ok = False
                    self._refresh_conn_bar_ui()
                    self._inject_panel.record_result(
                        int(index),
                        injected=False,
                        topic=topic,
                        reason="MVP 仅 EgoMotion",
                        t_ns=ev.t_ns,
                    )
                    self._inject_panel.set_detail(
                        f"跳过 #{index} {topic}（MVP 仅 EgoMotion）"
                    )
                    return
                kind, _topic = self._inject_helper.inject_model_index(
                    self._model, int(index)
                )
                if kind == "sent":
                    self._poll_inject_msgs(self._inject.poll_messages())
            else:
                self._inject.seek(int(index))
                self._poll_inject_msgs(self._inject.poll_messages())
        except ConnectionError as exc:
            self.statusBar().showMessage(f"inject seek 失败：{exc}", 4000)
            self._disconnect_inject()
        finally:
            self._inject_syncing = False

    def _append_live_rows(self, rows: list[dict[str, Any]]) -> None:
        follow = self._follow_latest.isChecked()
        keep_idx = self._slider.value()
        added = self._model.append_rows(rows, sor=self._sor)
        if added <= 0:
            # session_meta-only update still refreshes clock on tags
            self._tags.set_clock(self._model.clock)
            return
        n = len(self._model.events)
        self._order.set_model(self._model)
        self._dag.set_model(self._model)
        self._inject_panel.set_model(self._model)
        self._var_strip.set_model(self._model)
        self._tags.set_clock(self._model.clock)
        self._slider.blockSignals(True)
        self._slider.setEnabled(True)
        self._slider.setMaximum(max(0, n - 1))
        if not follow:
            # 不跟播：扩大 timeline，playhead 不动
            self._slider.setValue(min(keep_idx, n - 1))
        self._slider.blockSignals(False)
        proj = f"{self._project_dir.name} · " if self._project_dir else ""
        mode = ""
        if self._live_active or self._follow.isChecked():
            mode = " [跟随]" if follow else " [不跟播]"
            if self._live_log_fp is not None:
                mode += "·录制"
        if self._session_path:
            self._path_label.setText(f"{proj}{self._session_path} · {n} events{mode}")
        elif self._live_active:
            self._path_label.setText(f"{proj}Live 旁观（未录制） · {n} events{mode}")
        if follow:
            self._stick_tail = True
            self._seek_index(n - 1)
        else:
            self._stick_tail = False
            # 刷新当前帧视图（事件表已变），不追尾
            self._seek_index(min(keep_idx, n - 1))

    def _open_live_follow(self) -> None:
        start = str(self._default_live_session())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "跟随 live session JSONL",
            start,
            "JSONL (*.jsonl);;All (*)",
        )
        if not path:
            # still offer default even if missing
            self.start_follow(self._default_live_session())
            return
        self.start_follow(Path(path))

    def _on_follow_toggled(self, on: bool) -> None:
        if on:
            if self._session_path is None:
                self.start_follow()
                return
            self._tail.reset(self._session_path)
            if self._session_path.is_file() and self._model.events:
                # continue from EOF of already-loaded content
                self._tail.offset = self._session_path.stat().st_size
            self._stick_tail = self._follow_latest.isChecked()
            self._follow_timer.start()
            self.statusBar().showMessage(
                "跟随文件 ON"
                + (
                    "（跟随最新）"
                    if self._follow_latest.isChecked()
                    else "（不跟播）"
                ),
                2500,
            )
        else:
            self._follow_timer.stop()
            self.statusBar().showMessage("跟随文件 OFF", 2000)

    def _on_follow_tick(self) -> None:
        if self._session_path is None:
            return
        # detect truncate → full reload
        if self._session_path.is_file():
            size = self._session_path.stat().st_size
            if size < self._tail.offset:
                self._model.clear_events()
                self._tail.reset(self._session_path)
        lines = self._tail.poll_lines()
        if not lines:
            return
        rows: list[dict[str, Any]] = []
        for line in lines:
            row = parse_session_line(line)
            if row is not None:
                rows.append(row)
        if not rows:
            return
        self._append_live_rows(rows)

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
            t = int(t_ns)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        self._pause_follow_latest()
        idx = self._model.nearest_index(t)
        self._seek_index(idx)
        self.statusBar().showMessage(f"跳转到 t≈{t}  → #{idx}", 3000)

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
                    "项目",
                    f"{proj_dir}\n下未找到 project.yaml\n"
                    "请选 SKU 目录或其 project.yaml（与 gf-config 同一入口）。",
                )
                return
        elif p.is_file():
            QMessageBox.warning(
                self,
                "项目",
                f"请选择 project.yaml，而不是：\n{p.name}",
            )
            return
        else:
            QMessageBox.warning(self, "项目", f"路径不存在：\n{p}")
            return

        self._project_dir = proj_dir
        sor = proj_dir / "gf.sor.json"
        if not sor.is_file():
            QMessageBox.warning(
                self,
                "项目",
                f"未找到 {sor}\n请先在 gf-config Verify / Compose。",
            )
            self._path_label.setText(f"项目={proj_dir}（无 SOR）")
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
        self._path_label.setText(
            f"项目={proj_dir.name} · project.yaml · SOR={sor.name} — 填 host:port 后「连接」"
        )
        # offer latest session if present (skip when CLI already passes --session)
        cand = Path.cwd() / "build" / "observability" / "session.jsonl"
        if (
            offer_session
            and cand.is_file()
            and self._session_path is None
        ):
            reply = QMessageBox.question(
                self,
                "打开 session？",
                f"发现 {cand}\n是否加载？（也可先 run_sil 再 GUI「连接」）",
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
        # Stream mode: GMT session is authoritative — re-declare + reset board buffers
        if (
            self._inject_active
            and self._inject is not None
            and self._inject.connected
            and self._inject_stream
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
                self.statusBar().showMessage(f"inject session 重置失败：{exc}", 4000)
                self._disconnect_inject()
                return
        if n:
            self._seek_index(0)
        self.statusBar().showMessage("已加载 session", 3000)

    def _load_clip_path(self, path: object) -> None:
        p = Path(str(path))
        try:
            self._session_path = p
            self._model = load_session(p, sor=self._sor)
            self._apply_model()
            self._tabs.setCurrentWidget(self._order)
            QMessageBox.information(self, "clip", f"已加载 clip：\n{p}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "clip", str(exc))

    def _open_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 session JSONL",
            str(self._default_obs_dir()),
            "JSONL (*.jsonl);;All (*)",
        )
        if not path:
            return
        try:
            self.load_session_path(Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", str(exc))

    def _open_project(self) -> None:
        start = self._project_dir or (Path.cwd() / "projects")
        hint = start / "project.yaml"
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 project.yaml",
            str(hint if hint.is_file() else start),
            "project.yaml (project.yaml);;YAML (*.yaml *.yml);;All (*)",
        )
        if path:
            self.load_project(Path(path))
            self.statusBar().showMessage(f"已加载项目 {path}", 4000)

    def _open_project_dir(self) -> None:
        start = str(self._project_dir or Path.cwd() / "projects")
        path = QFileDialog.getExistingDirectory(self, "选择项目目录（备选）", start)
        if path:
            self.load_project(Path(path))
            self.statusBar().showMessage(f"已加载项目 {path}", 4000)

    def _record_from_logs(self) -> None:
        start_logs = Path.cwd() / "build"
        if self._project_dir is not None:
            # prefer multiproc / sil logs under build
            pass
        log_dir = QFileDialog.getExistingDirectory(
            self,
            "选择 SIL multiproc / iox_*_logs 目录",
            str(start_logs),
        )
        if not log_dir:
            return
        out, _ = QFileDialog.getSaveFileName(
            self,
            "保存 session.jsonl",
            str(self._default_obs_dir() / "session.jsonl"),
            "JSONL (*.jsonl)",
        )
        if not out:
            return
        out_path = Path(out)
        if out_path.suffix.lower() != ".jsonl":
            out_path = out_path.with_suffix(".jsonl")
        obs = self._obs_json()
        try:
            path, n = record_from_sil_logs(
                Path(log_dir),
                out_path,
                observability_json=obs,
            )
            self.load_session_path(path)
            note = f"observability={obs}" if obs else "无 whitelist（全量解析）"
            if n == 0:
                QMessageBox.warning(
                    self,
                    "录制",
                    f"写入 {path}\n事件数=0\n({note})\n"
                    "检查日志目录或 record.services / mode=off。",
                )
            else:
                QMessageBox.information(self, "录制", f"写入 {path}\n事件数={n}\n{note}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "录制失败", str(exc))

    def _import_ndjson(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入 tap NDJSON",
            str(Path.cwd()),
            "JSONL/NDJSON (*.jsonl *.ndjson);;All (*)",
        )
        if not path:
            return
        out, _ = QFileDialog.getSaveFileName(
            self,
            "保存为 session.jsonl",
            str(self._default_obs_dir() / "session_from_tap.jsonl"),
            "JSONL (*.jsonl)",
        )
        if not out:
            return
        out_path = Path(out)
        if out_path.suffix.lower() != ".jsonl":
            out_path = out_path.with_suffix(".jsonl")
        try:
            path_out, n = record_from_ndjson(Path(path), out_path)
            self.load_session_path(path_out)
            QMessageBox.information(self, "导入", f"写入 {path_out}\n事件数={n}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导入失败", str(exc))

    def _export_mcap(self) -> None:
        if self._session_path is None or not self._session_path.is_file():
            QMessageBox.information(self, "导出", "请先打开 session")
            return
        out, _ = QFileDialog.getSaveFileName(
            self,
            "导出 MCAP",
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
            QMessageBox.information(self, "导出", f"已写入 {out_path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(exc))

    def _export_vcd(self) -> None:
        if self._session_path is None or not self._session_path.is_file():
            QMessageBox.information(self, "导出", "请先打开 session")
            return
        from gf_gmt.measure_vcd import export_session_vcd

        out, _ = QFileDialog.getSaveFileName(
            self,
            "导出 VCD（GTKWave）",
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
                "导出",
                f"已写入 {path}\nvars={n_vars} events={n_ev}\n"
                f"打开：gtkwave {path}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(exc))

    def _export_dot(self) -> None:
        if not self._sor:
            QMessageBox.information(self, "导出", "请先加载 SOR / 项目")
            return
        from gf_gmt.architect import dag_from_sor, dag_to_dot

        out, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Graphviz .dot",
            str(self._default_obs_dir() / "dag.dot"),
            "Graphviz (*.dot)",
        )
        if not out:
            return
        out_path = Path(out)
        if out_path.suffix.lower() != ".dot":
            out_path = out_path.with_suffix(".dot")
        out_path.write_text(dag_to_dot(dag_from_sor(self._sor)), encoding="utf-8")
        QMessageBox.information(self, "导出", f"已写入 {out_path}")

    def _start_foxglove_replay(self) -> None:
        if self._session_path is None or not self._session_path.is_file():
            QMessageBox.information(self, "Foxglove", "请先打开 session")
            return
        self._stop_foxglove()
        gmt = shutil.which("GMT")
        if gmt:
            cmd = [
                gmt,
                "bridge",
                "foxglove",
                "--ws",
                "--jsonl",
                str(self._session_path),
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ]
        else:
            cmd = [
                sys.executable,
                "-m",
                "gf_gmt.cli",
                "bridge",
                "foxglove",
                "--ws",
                "--jsonl",
                str(self._session_path),
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ]
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
                f"进程已退出（码 {self._fox_proc.returncode}）。\n"
                "检查端口 8765 是否被占用，或用 CLI 调试。",
            )
            self._fox_proc = None
            return
        QMessageBox.information(
            self,
            "Foxglove",
            "已启动 WS 回放：ws://127.0.0.1:8765\n"
            "Foxglove Studio → Open connection。\n"
            "勿与 live bridge 同时占同一端口。",
        )
        self.statusBar().showMessage("Foxglove 回放进程已启动", 5000)

    def _stop_foxglove(self) -> None:
        if self._fox_proc is not None and self._fox_proc.poll() is None:
            self._fox_proc.terminate()
            try:
                self._fox_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._fox_proc.kill()
        self._fox_proc = None

    def _open_sor(self) -> None:
        start = str(self._project_dir or Path.cwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "加载 gf.sor.json",
            start,
            "JSON (*.json);;All (*)",
        )
        if not path:
            return
        try:
            with Path(path).open(encoding="utf-8") as f:
                self._sor = json.load(f)
            self._model.bind_sor(self._sor)
            self._order.set_model(self._model)
            self._dag.set_topology(self._sor)
            self._dag.set_model(self._model)
            if self._model.events:
                self._seek_index(self._slider.value())
            self.statusBar().showMessage(f"已加载 SOR {path}", 4000)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "SOR 失败", str(exc))

    def _toggle_play(self) -> None:
        if self._model.empty:
            return
        self._playing = not self._playing
        self._btn_play.setText("暂停" if self._playing else "播放")
        if self._playing:
            self._timer.start(self._next_interval_ms())
        else:
            self._timer.stop()

    def _next_interval_ms(self) -> int:
        base = max(1, int(self._rate.value()))
        if not self._use_dt.isChecked() or self._model.empty:
            return base
        cur = self._slider.value()
        nxt = min(cur + 1, len(self._model.events) - 1)
        dt = self._model.events[nxt].dt_ns if nxt > cur else 0
        # map 1e6 ns → rate ms (user rate scales wall clock)
        if dt <= 0:
            return base
        scaled = int(dt / 1_000_000.0 * (base / 200.0))
        return max(1, min(scaled, 5000))

    def _on_tick(self) -> None:
        if self._model.empty:
            self._toggle_play()
            return
        cur = self._slider.value()
        if cur >= self._slider.maximum():
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
            and (self._live_active or self._follow.isChecked())
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
        if self._follow.isChecked() or self._live_active:
            live = " 跟随" if self._follow_latest.isChecked() else ""
            if self._live_log_fp is not None:
                live += " 录制"
        wall = self._model.wall_str(ev.t_ns)
        self._t_label.setText(
            f"墙钟={wall}  t={ev.t_ns}  #{index}/{len(self._model.events) - 1}{live}"
        )
        self._order.highlight_upto(index)
        self._dag.set_playhead_index(index)
        self._var_strip.set_playhead_index(index)
        self._inject_panel.highlight_upto(index)
        self._tags.set_playhead_ns(ev.t_ns)
        self._inject_seek(index)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._follow_timer.stop()
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
    follow: bool = False,
) -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    win = GmtMainWindow()
    if project:
        win.load_project(project, offer_session=session is None and not follow)
    if sor and sor.is_file():
        with sor.open(encoding="utf-8") as f:
            win._sor = json.load(f)
        win._dag.set_topology(win._sor)
    if follow:
        live = session or win._default_live_session()
        win.start_follow(live)
    elif session and session.is_file():
        win.load_session_path(session, sor_path=sor)
    win.show()
    return app.exec()
