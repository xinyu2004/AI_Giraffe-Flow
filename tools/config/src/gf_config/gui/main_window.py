"""Main window: open project, SKU + signal graph + lineage."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
)

from gf_config.core import ProjectSession
from gf_config.gui.lineage_view import LineageView
from gf_config.gui.req_editor import ReqEditor
from gf_config.gui.wiring_graph import WiringGraphView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("gf-config — Giraffe Flow（SKU + 信号链接）")
        self.resize(1280, 800)
        self._session: ProjectSession | None = None

        self._tabs = QTabWidget()
        self._req = ReqEditor()
        self._graph = WiringGraphView()
        self._lineage = LineageView()

        self._tabs.addTab(self._req, "A · SKU / 中间件")
        self._tabs.addTab(self._graph, "B · 信号链接")
        self._tabs.addTab(self._lineage, "C · Lineage")
        self.setCentralWidget(self._tabs)

        self._path_label = QLabel("未打开项目")
        status = QStatusBar()
        status.addWidget(self._path_label, stretch=1)
        self.setStatusBar(status)

        self._req.changed.connect(self._mark_dirty)
        self._graph.changed.connect(self._mark_dirty)

        self._build_menu()
        self._build_toolbar()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        act_open = QAction("打开 project.yaml…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._browse_open)
        file_menu.addAction(act_open)

        act_save = QAction("保存", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._save)
        file_menu.addAction(act_save)

        act_compose = QAction("Compose + Lineage", self)
        act_compose.setShortcut("Ctrl+R")
        act_compose.triggered.connect(self._compose)
        file_menu.addAction(act_compose)

        view_menu = self.menuBar().addMenu("视图")
        act_reset_zoom = QAction("信号图恢复默认大小", self)
        act_reset_zoom.setShortcut("Ctrl+H")
        act_reset_zoom.triggered.connect(self._graph.reset_zoom)
        view_menu.addAction(act_reset_zoom)

        file_menu.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

    def _build_toolbar(self) -> None:
        tb = QToolBar("main")
        self.addToolBar(tb)
        open_btn = QAction("打开", self)
        open_btn.triggered.connect(self._browse_open)
        tb.addAction(open_btn)
        save_btn = QAction("保存", self)
        save_btn.triggered.connect(self._save)
        tb.addAction(save_btn)
        compose_btn = QAction("Compose", self)
        compose_btn.triggered.connect(self._compose)
        tb.addAction(compose_btn)
        import_btn = QAction("导入 hpp", self)
        import_btn.triggered.connect(self._graph.import_hpp)
        tb.addAction(import_btn)

    def _browse_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 project.yaml",
            str(Path.cwd()),
            "Project (project.yaml);;YAML (*.yaml);;All (*)",
        )
        if path:
            try:
                self.open_project(Path(path))
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "打开失败", str(exc))

    def open_project(self, project_file: Path) -> None:
        self._session = ProjectSession.open(project_file)
        self._req.set_session(self._session)
        self._graph.set_session(self._session)
        self._path_label.setText(str(self._session.paths.project_file))
        self.setWindowTitle(f"gf-config — {self._session.paths.project_dir.name}")
        lr = self._session.paths.lineage_report
        if lr.is_file():
            self._lineage.set_report_text(lr.read_text(encoding="utf-8"))
        else:
            self._lineage.set_placeholder("尚无 lineage 报告。点击 Compose 生成。")
        self.statusBar().showMessage("已打开", 3000)

    def _mark_dirty(self) -> None:
        self.statusBar().showMessage("有未保存更改（保存或 Compose 会写盘）", 5000)

    def _save(self) -> None:
        if not self._session:
            QMessageBox.information(self, "保存", "请先打开项目")
            return
        self._session.save_all()
        self.statusBar().showMessage(
            f"已写入 {self._session.paths.req.name} / {self._session.paths.wiring.name}",
            5000,
        )

    def _compose(self) -> None:
        if not self._session:
            QMessageBox.information(self, "Compose", "请先打开项目")
            return
        try:
            rc, report = self._session.compose()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Compose 失败", str(exc))
            return
        self._lineage.set_report_text(report or "")
        self._tabs.setCurrentWidget(self._lineage)
        self._graph.rebuild()
        if rc == 0:
            self.statusBar().showMessage("Compose OK", 5000)
            QMessageBox.information(self, "Compose", "成功。请查看 Lineage 页签。")
        else:
            QMessageBox.warning(self, "Compose", f"退出码 {rc}。请查看 Lineage 红项。")
