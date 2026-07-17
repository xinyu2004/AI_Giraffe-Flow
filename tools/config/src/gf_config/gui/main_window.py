"""Main window: open project, SKU + signal graph（Lineage 在右侧面板）。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
)

from gf_config.core import ProjectSession
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

        self._tabs.addTab(self._req, "A · SKU / 中间件")
        self._tabs.addTab(self._graph, "B · 信号链接")
        self.setCentralWidget(self._tabs)

        self._path_label = QLabel("未打开项目")
        status = QStatusBar()
        status.addWidget(self._path_label, stretch=1)
        self.setStatusBar(status)

        self._req.changed.connect(self._mark_dirty)
        self._graph.changed.connect(self._mark_dirty)

        self._build_menu()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")

        act_open = QAction("打开 project.yaml…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_open.triggered.connect(self._browse_open)
        file_menu.addAction(act_open)

        act_save = QAction("保存（只写盘，不检查）", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_save.triggered.connect(self._save)
        file_menu.addAction(act_save)

        act_save_verify = QAction("保存并 Verify…", self)
        act_save_verify.setShortcut("Ctrl+Shift+S")
        act_save_verify.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_save_verify.triggered.connect(self._save_and_verify)
        file_menu.addAction(act_save_verify)

        file_menu.addSeparator()

        act_verify = QAction("Verify（合成 SOR / 检查闭环）", self)
        act_verify.setShortcut("Ctrl+R")
        act_verify.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_verify.triggered.connect(lambda: self._verify(show_dialog=True))
        file_menu.addAction(act_verify)

        act_gen = QAction("Generate（Proxy/Skeleton）…", self)
        act_gen.setShortcut("Ctrl+G")
        act_gen.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_gen.triggered.connect(self._generate)
        file_menu.addAction(act_gen)

        file_menu.addSeparator()

        act_import_hpp = QAction("导入 hpp/h…", self)
        act_import_hpp.triggered.connect(self._graph.import_hpp)
        file_menu.addAction(act_import_hpp)

        act_import_fidl = QAction("导入 fidl…", self)
        act_import_fidl.triggered.connect(self._graph.import_fidl)
        file_menu.addAction(act_import_fidl)

        file_menu.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = self.menuBar().addMenu("视图")

        act_fit = QAction("适应窗口", self)
        act_fit.setShortcut("Ctrl+0")
        act_fit.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_fit.triggered.connect(self._fit_graph)
        view_menu.addAction(act_fit)

        act_reset_zoom = QAction("恢复默认大小", self)
        act_reset_zoom.setShortcut("Ctrl+H")
        act_reset_zoom.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_reset_zoom.triggered.connect(self._graph.reset_zoom)
        view_menu.addAction(act_reset_zoom)

        act_reload = QAction("重载信号图", self)
        act_reload.setShortcut("F5")
        act_reload.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_reload.triggered.connect(lambda: self._graph.rebuild(fit_view=False))
        view_menu.addAction(act_reload)

        view_menu.addSeparator()

        act_flows = QAction("右侧 · 连线列表", self)
        act_flows.triggered.connect(self._show_flows_panel)
        view_menu.addAction(act_flows)

        act_lineage = QAction("右侧 · Lineage 报告", self)
        act_lineage.setShortcut("Ctrl+L")
        act_lineage.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_lineage.triggered.connect(self._show_lineage_panel)
        view_menu.addAction(act_lineage)

        act_toggle_right = QAction("折叠/展开右侧面板", self)
        act_toggle_right.triggered.connect(self._graph.toggle_right_panel)
        view_menu.addAction(act_toggle_right)

        view_menu.addSeparator()

        act_del_edge = QAction("删除选中边", self)
        act_del_edge.setShortcut(QKeySequence.StandardKey.Delete)
        act_del_edge.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_del_edge.triggered.connect(self._graph.delete_selection)
        view_menu.addAction(act_del_edge)

    def _fit_graph(self) -> None:
        self._tabs.setCurrentWidget(self._graph)
        self._graph.fit_in_window()

    def _show_flows_panel(self) -> None:
        self._tabs.setCurrentWidget(self._graph)
        self._graph.focus_flows()

    def _show_lineage_panel(self) -> None:
        self._tabs.setCurrentWidget(self._graph)
        self._graph.focus_lineage()

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
            self._graph.set_lineage_report(lr.read_text(encoding="utf-8"))
        else:
            self._graph.set_lineage_placeholder(
                "尚无 lineage。菜单：文件 → Verify（Ctrl+R）"
            )
        self._tabs.setCurrentWidget(self._graph)
        self.statusBar().showMessage("已打开", 3000)

    def _mark_dirty(self) -> None:
        self.statusBar().showMessage("有未保存更改 — Ctrl+S 只保存；Verify 另点", 5000)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._session is not None:
            self._graph.flush_canvas()
            if self._session.dirty_wiring or self._session.dirty_req:
                reply = QMessageBox.question(
                    self,
                    "退出",
                    "有未保存的连线/布局/SKU 更改，是否保存？",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                if reply == QMessageBox.StandardButton.Save:
                    self._session.save_all()
        event.accept()

    def _save(self) -> None:
        """写盘 only — 不跑 lineage / 不拦不合理连线。"""
        if not self._session:
            QMessageBox.information(self, "保存", "请先打开项目")
            return
        self._graph.flush_canvas()
        had_dirty = bool(self._session.dirty_wiring or self._session.dirty_req)
        try:
            self._session.save_all()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        wiring = self._session.paths.wiring
        req = self._session.paths.req
        if had_dirty:
            self._path_label.setText(f"{self._session.paths.project_file}  ·  ✓ 已保存")
            self.statusBar().showMessage(
                f"✓ 已保存 {wiring.name} / {req.name}（未 Verify）",
                8000,
            )
            QMessageBox.information(
                self,
                "保存",
                f"已写入磁盘：\n• {wiring}\n• {req}\n\n"
                "（未跑 Verify；需要检查时再按 Ctrl+R）",
            )
        else:
            self.statusBar().showMessage("没有未保存更改", 4000)
            QMessageBox.information(self, "保存", "没有未保存的更改。")

    def _save_and_verify(self) -> None:
        if not self._session:
            QMessageBox.information(self, "保存", "请先打开项目")
            return
        self._graph.flush_canvas()
        self._session.save_all()
        self.statusBar().showMessage("已保存，正在 Verify…", 2000)
        self._verify(show_dialog=False)

    def _verify(self, *, show_dialog: bool = False) -> bool:
        """GUI 名 Verify；底层仍调用 session.compose()（CI 命令不变）。"""
        if not self._session:
            QMessageBox.information(self, "Verify", "请先打开项目")
            return False
        try:
            rc, report = self._session.compose()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Verify 失败", str(exc))
            return False
        self._graph.set_lineage_report(report or "")
        self._graph.rebuild()
        self._tabs.setCurrentWidget(self._graph)
        self._graph.focus_lineage()
        if rc == 0:
            self.statusBar().showMessage(
                "Verify OK — 右侧 Lineage 页。需要 C++ API 时点 Generate (Ctrl+G)",
                8000,
            )
            if show_dialog:
                QMessageBox.information(
                    self,
                    "Verify",
                    "成功。请查看右侧「Lineage」页。\n\n"
                    "若要生成 Proxy/Skeleton：文件 → Generate 或 Ctrl+G。",
                )
            return True
        self.statusBar().showMessage(f"Verify 退出码 {rc} — 见右侧 Lineage 红项", 8000)
        QMessageBox.warning(self, "Verify", f"退出码 {rc}。请查看右侧 Lineage 红项。")
        return False

    def _generate(self) -> None:
        if not self._session:
            QMessageBox.information(self, "Generate", "请先打开项目")
            return
        out = self._session.paths.project_dir / "generated"
        try:
            rc, report = self._session.generate(out)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Generate 失败", str(exc))
            return
        self._graph.set_lineage_report(report or "")
        self._graph.rebuild()
        self._tabs.setCurrentWidget(self._graph)
        self._graph.focus_lineage()
        if rc != 0:
            QMessageBox.warning(
                self,
                "Generate",
                f"Verify/Generate 失败（码 {rc}）。请先修好右侧 Lineage。",
            )
            return
        self.statusBar().showMessage(f"Generate OK → {out}/include/gf_gen/", 8000)
        QMessageBox.information(
            self,
            "Generate",
            f"已生成 Proxy/Skeleton：\n{out}/include/gf_gen/\n\n"
            "可用 gf-codegen generate 在无 GUI 时同样产出。",
        )
