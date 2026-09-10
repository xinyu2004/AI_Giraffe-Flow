"""Main window: 1 · 信号与应用 / 2 · 平台配置."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession
from gf_config.gui.doc_history import (
    DocHistory,
    apply_snapshot,
    capture_snapshot,
    locate_doc_change,
)
from gf_config.gui.ara_cfg_editor import AraCfgEditor
from gf_config.gui.pipeline import compose_validated, save_validated
from gf_config.gui.req_editor import ReqEditor
from gf_config.gui.wiring_graph import WiringGraphView
from gf_config.i18n import get_language, save_language, t


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("gf-config — Giraffe Flow（信号与应用 / 平台）"))
        self.resize(1400, 860)
        self._session: ProjectSession | None = None
        self._skip_close_prompt = False
        # Set by cli quiet boot: suppress deferred fit until reveal.
        self._quiet_booting = False
        self._history = DocHistory()
        self._history.bind(
            lambda: self._session,
            lambda: self._graph.flush_canvas(),
        )

        self._tabs = QTabWidget(self)
        self._req = ReqEditor(self)
        self._graph = WiringGraphView(self)
        self._ara_cfg_ed = AraCfgEditor(self)

        # 页 1：左 SKU（默认展开）| 箭头 | 画布（右侧连线默认收起）
        self._sku_panel = QWidget(self)
        sku_l = QVBoxLayout(self._sku_panel)
        sku_l.setContentsMargins(0, 0, 0, 0)
        sku_l.setSpacing(0)
        sku_l.addWidget(self._req)
        # 定宽：英文标签更长（Live scope / Record services），按语言留足列宽
        self._sku_panel.setFixedWidth(420 if get_language() == "en" else 320)
        self._sku_panel.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        self._btn_toggle_sku = QToolButton(self)
        # 面板在左：展开时 ◀=收起；收起后 ▶=展开
        self._btn_toggle_sku.setText("◀")
        self._btn_toggle_sku.setToolTip(t("折叠 / 展开左侧 SKU"))
        self._btn_toggle_sku.setFixedWidth(22)
        self._btn_toggle_sku.clicked.connect(self._toggle_sku_panel)
        self._sku_collapsed = False
        self._sku_panel.setVisible(True)

        signals_page = QWidget(self)
        signals_l = QHBoxLayout(signals_page)
        signals_l.setContentsMargins(0, 0, 0, 0)
        signals_l.setSpacing(0)
        signals_l.addWidget(self._sku_panel, stretch=0)
        signals_l.addWidget(self._btn_toggle_sku, stretch=0)
        signals_l.addWidget(self._graph, stretch=1)
        self._signals_page: QWidget = signals_page

        self._tabs.addTab(self._signals_page, t("1 · 信号与应用"))
        self._tabs.addTab(self._ara_cfg_ed, t("2 · 平台配置"))
        self.setCentralWidget(self._tabs)

        self._path_label = QLabel(t("未打开项目"), self)
        status = QStatusBar(self)
        # Permanent (right): path must not share the left strip with showMessage,
        # or temporary text like「已打开」paints over the path and looks missing.
        status.addPermanentWidget(self._path_label, 1)
        self.setStatusBar(status)

        self._graph.set_history_hooks(
            self._history.checkpoint,
            self._history.end_edit,
            self._history.clear,
        )
        self._req.set_history_hooks(self._history.checkpoint, self._history.end_edit)
        self._ara_cfg_ed.set_history_hooks(
            self._history.checkpoint, self._history.end_edit
        )

        self._req.changed.connect(self._on_req_changed)
        self._graph.changed.connect(self._on_graph_changed)
        self._ara_cfg_ed.changed.connect(self._mark_dirty)

        self._build_menu()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu(t("文件"))

        act_open = QAction(t("打开 giraffe.yaml…"), self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_open.triggered.connect(self._browse_open)
        file_menu.addAction(act_open)

        act_new = QAction(t("新建 Giraffe 工程…"), self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_new.triggered.connect(self._browse_new_project)
        file_menu.addAction(act_new)

        act_save = QAction(t("保存（Verify 通过后写盘）"), self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_save.triggered.connect(self._save)
        file_menu.addAction(act_save)

        file_menu.addSeparator()

        act_verify = QAction(t("Verify（合成 SOR / 检查闭环）"), self)
        act_verify.setShortcut("Ctrl+R")
        act_verify.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_verify.triggered.connect(lambda: self._verify(show_dialog=True))
        file_menu.addAction(act_verify)

        act_gen = QAction(t("Generate（Proxy/Skeleton）…"), self)
        act_gen.setShortcut("Ctrl+G")
        act_gen.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_gen.triggered.connect(self._generate)
        file_menu.addAction(act_gen)

        file_menu.addSeparator()

        act_import_hpp = QAction(t("导入 hpp/h…"), self)
        act_import_hpp.triggered.connect(self._graph.import_hpp)
        file_menu.addAction(act_import_hpp)

        act_import_fidl = QAction(t("导入 fidl…"), self)
        act_import_fidl.triggered.connect(self._graph.import_fidl)
        file_menu.addAction(act_import_fidl)

        file_menu.addSeparator()

        act_export_dot = QAction(t("导出 Graphviz .dot…"), self)
        act_export_dot.triggered.connect(lambda: self._export_graph(kind="dot"))
        file_menu.addAction(act_export_dot)

        act_export_svg = QAction(t("导出 Graphviz SVG…"), self)
        act_export_svg.triggered.connect(lambda: self._export_graph(kind="svg"))
        file_menu.addAction(act_export_svg)

        file_menu.addSeparator()
        act_quit = QAction(t("退出"), self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        edit_menu = self.menuBar().addMenu(t("编辑"))
        act_undo = QAction(t("撤销"), self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_undo.triggered.connect(self._undo_doc)
        edit_menu.addAction(act_undo)
        act_redo = QAction(t("重做"), self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_redo.triggered.connect(self._redo_doc)
        edit_menu.addAction(act_redo)

        view_menu = self.menuBar().addMenu(t("视图"))

        act_fit = QAction(t("适应窗口"), self)
        act_fit.setShortcut("Ctrl+0")
        act_fit.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_fit.triggered.connect(self._fit_graph)
        view_menu.addAction(act_fit)

        act_reset_zoom = QAction(t("恢复默认大小"), self)
        act_reset_zoom.setShortcut("Ctrl+H")
        act_reset_zoom.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_reset_zoom.triggered.connect(self._graph.reset_zoom)
        view_menu.addAction(act_reset_zoom)

        act_reload = QAction(t("重载信号图"), self)
        act_reload.setShortcut("F5")
        act_reload.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_reload.triggered.connect(lambda: self._graph.rebuild(fit_view=False))
        view_menu.addAction(act_reload)

        view_menu.addSeparator()

        act_flows = QAction(t("右侧 · 连线列表"), self)
        act_flows.triggered.connect(self._show_flows_panel)
        view_menu.addAction(act_flows)

        act_lineage = QAction(t("右侧 · Lineage 报告"), self)
        act_lineage.setShortcut("Ctrl+L")
        act_lineage.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        act_lineage.triggered.connect(self._show_lineage_panel)
        view_menu.addAction(act_lineage)

        act_toggle_sku = QAction(t("折叠/展开左侧 SKU"), self)
        act_toggle_sku.triggered.connect(self._toggle_sku_panel)
        view_menu.addAction(act_toggle_sku)

        act_toggle_right = QAction(t("折叠/展开右侧面板"), self)
        act_toggle_right.triggered.connect(self._graph.toggle_right_panel)
        view_menu.addAction(act_toggle_right)

        view_menu.addSeparator()

        # Del/Backspace live on WiringGraph (WidgetWithChildren) so they don't
        # fight this menu action or fire while editing tables on tab 2.
        act_del_edge = QAction(t("删除选中边"), self)
        act_del_edge.triggered.connect(self._graph.delete_selection)
        view_menu.addAction(act_del_edge)

        lang_menu = self.menuBar().addMenu(t("语言"))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        act_zh = QAction(t("中文"), self)
        act_zh.setCheckable(True)
        act_zh.setChecked(get_language() == "zh")
        act_zh.triggered.connect(lambda: self._on_language("zh"))
        lang_group.addAction(act_zh)
        lang_menu.addAction(act_zh)
        act_en = QAction(t("English"), self)
        act_en.setCheckable(True)
        act_en.setChecked(get_language() == "en")
        act_en.triggered.connect(lambda: self._on_language("en"))
        lang_group.addAction(act_en)
        lang_menu.addAction(act_en)

    def _on_language(self, lang: str) -> None:
        if lang == get_language():
            return
        project_path: str | None = None
        if self._session is not None:
            self._graph.flush_canvas()
            project_path = str(self._session.paths.project_file.resolve())
            if self._session.is_dirty():
                reply = QMessageBox.question(
                    self,
                    t("语言"),
                    t("切换语言将刷新界面。有未保存的更改，是否保存？"),
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return
                if reply == QMessageBox.StandardButton.Save:
                    try:
                        result = save_validated(
                            self._session,
                            flush_canvas=self._graph.flush_canvas,
                        )
                    except Exception as exc:  # noqa: BLE001
                        QMessageBox.critical(self, t("保存失败"), str(exc))
                        return
                    if not result.ok:
                        QMessageBox.warning(
                            self,
                            t("无法保存"),
                            t("校验未通过，未写入磁盘（更改仍在内存）。")
                            + "\n\n"
                            + result.format_errors(),
                        )
                        return
        self.persist_window_geometry()
        self._switch_language_in_process(lang, project_path)

    def _switch_language_in_process(
        self, lang: str, project_path: str | None
    ) -> None:
        """Rebuild MainWindow in-process (avoids process-restart dual-window flash)."""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        save_language(lang)
        geo = self.saveGeometry()
        new = MainWindow()
        new.restoreGeometry(geo)
        new._quiet_booting = True
        new.setUpdatesEnabled(False)
        new._graph._view.setUpdatesEnabled(False)
        new.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        new.show()
        app.processEvents()

        if project_path:
            try:
                new.open_project(Path(project_path))
            except Exception as exc:  # noqa: BLE001
                new._skip_close_prompt = True
                new.close()
                QMessageBox.critical(self, t("打开失败"), str(exc))
                return
            new.finish_quiet_boot()

        new.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        new._quiet_booting = False
        wh = new.windowHandle()
        if wh is not None:
            wh.setVisible(True)
        new._graph._view.setUpdatesEnabled(True)
        new.setUpdatesEnabled(True)
        new.show()
        new.raise_()
        new.activateWindow()
        app.processEvents()

        self._skip_close_prompt = True
        self.hide()
        self.close()
        app.setProperty("gf_config_main_window", new)

    def restore_window_geometry(self) -> bool:
        """Restore last session geometry from QSettings. False if none/invalid."""
        from PySide6.QtCore import QSettings

        raw = QSettings("GiraffeFlow", "gf-config").value("ui/main_geometry")
        if raw is None:
            return False
        return bool(self.restoreGeometry(raw))

    def persist_window_geometry(self) -> None:
        from PySide6.QtCore import QSettings

        QSettings("GiraffeFlow", "gf-config").setValue(
            "ui/main_geometry", self.saveGeometry()
        )

    def _toggle_sku_panel(self) -> None:
        self._sku_collapsed = not self._sku_collapsed
        self._sku_panel.setVisible(not self._sku_collapsed)
        # 收起 ▶ / 展开 ◀（与右侧 ▶收起 / ◀展开 对称）
        self._btn_toggle_sku.setText("▶" if self._sku_collapsed else "◀")

    def _fit_graph(self) -> None:
        self._tabs.setCurrentWidget(self._signals_page)
        self._graph.fit_in_window()

    def _undo_doc(self) -> None:
        if not self._history.can_undo() or self._session is None:
            self.statusBar().showMessage(t("没有可撤销的操作"), 2000)
            return
        before = capture_snapshot(self._session)
        snap = self._history.undo()
        if snap is None:
            return
        self._apply_doc_snapshot(snap)
        self._navigate_after_history(before, snap, action="undo")

    def _redo_doc(self) -> None:
        if not self._history.can_redo() or self._session is None:
            self.statusBar().showMessage(t("没有可重做的操作"), 2000)
            return
        before = capture_snapshot(self._session)
        snap = self._history.redo()
        if snap is None:
            return
        self._apply_doc_snapshot(snap)
        self._navigate_after_history(before, snap, action="redo")

    def _navigate_after_history(
        self, before: dict, after: dict, *, action: str
    ) -> None:
        """Jump to the page that changed so undo/redo is visible; hint in status bar."""
        area, plat_key, hint = locate_doc_change(before, after)
        if area == "ara_cfg":
            self._tabs.setCurrentWidget(self._ara_cfg_ed)
            if plat_key:
                self._ara_cfg_ed.select_nav(plat_key)
        else:
            self._tabs.setCurrentWidget(self._signals_page)
            if area == "req" and self._sku_collapsed:
                self._toggle_sku_panel()
            elif area == "wiring" and not self._sku_collapsed:
                # Prefer canvas when the edit was on the graph
                pass
        verb = t("已撤销") if action == "undo" else t("已重做")
        self.statusBar().showMessage(f"{verb} — {hint}", 5000)

    def _apply_doc_snapshot(self, snap: dict) -> None:
        assert self._session is not None
        apply_snapshot(self._session, snap)
        self._history.suppress = True
        try:
            self._req.set_session(self._session)
            self._ara_cfg_ed.set_session(self._session)
            self._graph.apply_session_restore(self._session)
        finally:
            self._history.suppress = False
            self._history.end_edit()

    def _show_flows_panel(self) -> None:
        self._tabs.setCurrentWidget(self._signals_page)
        self._graph.focus_flows()

    def _show_lineage_panel(self) -> None:
        self._tabs.setCurrentWidget(self._signals_page)
        self._graph.focus_lineage()

    def _browse_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("选择 giraffe.yaml"),
            str(Path.cwd()),
            "Giraffe (giraffe.yaml);;YAML (*.yaml);;All (*)",
        )
        if path:
            try:
                self.open_project(Path(path))
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, t("打开失败"), str(exc))

    def _browse_new_project(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        from gf_codegen.scaffold_project import scaffold_project

        parent = QFileDialog.getExistingDirectory(
            self,
            t("选择新建工程的父目录"),
            str(Path.cwd()),
        )
        if not parent:
            return
        name, ok = QInputDialog.getText(
            self,
            t("新建 Giraffe 工程"),
            t("工程目录名（project_id）："),
            text="new_sku",
        )
        if not ok or not str(name).strip():
            return
        slug = str(name).strip()
        dest = Path(parent) / slug
        try:
            if dest.exists() and any(dest.iterdir()):
                QMessageBox.warning(
                    self,
                    t("新建失败"),
                    t("目录非空：") + str(dest),
                )
                return
            dest.mkdir(parents=True, exist_ok=True)
            entry = scaffold_project(dest, project_id=slug, product=slug.upper())
            self.open_project(entry)
            QMessageBox.information(
                self,
                t("新建 Giraffe 工程"),
                t("已生成最小完备树：")
                + f"\n{entry}\n\n"
                + t("含 cfg/req.yaml · cfg/wiring.yaml · cfg/gf_ara_cfg/*\n"
                    "请补 OEM DBC 后 Verify。"),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("新建失败"), str(exc))

    def open_project(self, project_file: Path) -> None:
        self._history.clear()
        try:
            session = ProjectSession.open(project_file)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("打开失败"), str(exc))
            return
        gate = session.validate()
        if not gate.ok:
            QMessageBox.critical(
                self,
                t("工程非法，已拒绝打开"),
                t("磁盘配置未通过校验（不会自动修补）。请用 gf-config 修正后重开。")
                + "\n\n"
                + gate.format_errors(),
            )
            return
        self._session = session
        self._history.suppress = True
        painted = self.updatesEnabled()
        self.setUpdatesEnabled(False)
        self._graph.begin_batch_update()
        try:
            self._req.set_session(self._session)
            self._graph.set_session(self._session)
            self._ara_cfg_ed.set_session(self._session)
            self._path_label.setText(str(self._session.paths.project_file))
            self.setWindowTitle(f"gf-config — {self._session.paths.project_dir.name}")
            lr = self._session.paths.lineage_report
            if lr.is_file():
                self._graph.set_lineage_report(lr.read_text(encoding="utf-8"))
            else:
                self._graph.set_lineage_placeholder(
                    t("尚无 lineage。菜单：文件 → Verify（Ctrl+R）")
                )
            self._tabs.setCurrentWidget(self._signals_page)
        finally:
            self._history.suppress = False
            # Fit while paints are still frozen (quiet boot / batch).
            self._graph.end_batch_update(fit=True)
            self.setUpdatesEnabled(painted)
        if self._session.is_dirty():
            self.statusBar().showMessage(
                t("已打开（已自动迁移旧格式，请保存）"), 8000
            )
        else:
            self.statusBar().showMessage(t("已打开"), 3000)

    def finish_quiet_boot(self) -> None:
        """After DSS show + open_project: ensure graph fit before reveal."""
        from PySide6.QtWidgets import QApplication

        ok = self._graph.fit_now()
        if not ok:
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
            self._graph.fit_now()

    def _on_req_changed(self) -> None:
        self._mark_dirty()
        # 拓扑 ap_only / ap_mcu_cp 切换时刷新 MCU 可见性
        self._graph.sync_topology_visibility()
        # iceoryx binding ↔ host.iox_roudi
        self._ara_cfg_ed.sync_capability_hosts()

    def _on_graph_changed(self) -> None:
        self._mark_dirty()
        # frame_ingest ↔ host.frame_ingest
        self._ara_cfg_ed.sync_capability_hosts()

    def _mark_dirty(self) -> None:
        if self._session is None or not self._session.is_dirty():
            return
        self.statusBar().showMessage(
            t("有未保存更改 — Ctrl+S 保存（须校验通过）"), 5000
        )

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.persist_window_geometry()
        if self._skip_close_prompt:
            event.accept()
            return
        if self._session is not None:
            self._graph.flush_canvas()
            if self._session.is_dirty():
                reply = QMessageBox.question(
                    self,
                    t("退出"),
                    t("有未保存的 SKU / 连线 / ARA cfg 更改，是否保存？"),
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                if reply == QMessageBox.StandardButton.Save:
                    try:
                        result = save_validated(
                            self._session,
                            flush_canvas=self._graph.flush_canvas,
                        )
                    except Exception as exc:  # noqa: BLE001
                        QMessageBox.critical(self, t("保存失败"), str(exc))
                        event.ignore()
                        return
                    if not result.ok:
                        QMessageBox.warning(
                            self,
                            t("无法保存"),
                            t("校验未通过，未写入磁盘。可丢弃更改后退出，或取消继续编辑。")
                            + "\n\n"
                            + result.format_errors(),
                        )
                        event.ignore()
                        return
        event.accept()

    def _saved_paths_summary(self) -> str:
        assert self._session is not None
        lines = [
            f"• {self._session.paths.req}",
            f"• {self._session.paths.wiring}",
        ]
        for key, p in sorted(self._session.paths.gf_ara_cfg.items()):
            lines.append(f"• {p}  ({key})")
        return "\n".join(lines)

    def _save(self) -> None:
        """Validate → write disk → compose (lineage). Fail keeps memory, no write."""
        if not self._session:
            QMessageBox.information(self, t("保存"), t("请先打开项目"))
            return
        self._graph.flush_canvas()
        if not self._session.is_dirty():
            self.statusBar().showMessage(t("没有未保存更改"), 4000)
            QMessageBox.information(self, t("保存"), t("没有未保存的更改。"))
            return
        try:
            result = save_validated(self._session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("保存失败"), str(exc))
            return
        if not result.ok:
            self.statusBar().showMessage(t("校验未通过 — 未写盘"), 8000)
            QMessageBox.warning(
                self,
                t("无法保存"),
                t("校验未通过，未写入磁盘（更改仍在内存）。")
                + "\n\n"
                + result.format_errors(),
            )
            return
        self._ara_cfg_ed.rebaseline_spins()
        self._path_label.setText(
            f"{self._session.paths.project_file}  ·  {t('✓ 已保存')}"
        )
        self._verify(show_dialog=False, already_saved=True)

    def _verify(self, *, show_dialog: bool = False, already_saved: bool = False) -> bool:
        """Validate memory; persist if needed; compose_project for lineage."""
        if not self._session:
            QMessageBox.information(self, t("Verify"), t("请先打开项目"))
            return False
        try:
            if already_saved:
                from gf_codegen.compose.pipeline import compose_project

                rc = compose_project(
                    self._session.paths.project_file,
                    repo_root=self._session.paths.repo_root,
                )
                report = ""
                if self._session.paths.lineage_report.is_file():
                    report = self._session.paths.lineage_report.read_text(
                        encoding="utf-8"
                    )
            else:
                rc, report, result = compose_validated(
                    self._session,
                    flush_canvas=self._graph.flush_canvas,
                )
                if not result.ok:
                    QMessageBox.warning(
                        self,
                        t("Verify"),
                        t("校验未通过，未写入磁盘（更改仍在内存）。")
                        + "\n\n"
                        + result.format_errors(),
                    )
                    self.statusBar().showMessage(t("校验未通过 — 未写盘"), 8000)
                    return False
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("Verify 失败"), str(exc))
            return False
        self._ara_cfg_ed.rebaseline_spins()
        self._graph.set_lineage_report(report or "")
        self._graph.rebuild()
        self._tabs.setCurrentWidget(self._signals_page)
        self._graph.focus_lineage()
        if rc == 0:
            self.statusBar().showMessage(
                t(
                    "Verify OK — 作者态完成（见右侧 Lineage）。"
                    "需要 C++ API 时再 Generate (Ctrl+G)；然后 compile_sil"
                ),
                8000,
            )
            if show_dialog:
                QMessageBox.information(
                    self,
                    t("Verify"),
                    t(
                        "成功。请查看右侧「Lineage」。\n\n"
                        "拓扑图见页 1 画布；评审附件可用「文件 → 导出 Graphviz」。\n"
                        "运行时序/回放请用 GMT GUI。\n\n"
                        "若要生成 Proxy/Skeleton：文件 → Generate 或 Ctrl+G。"
                    ),
                )
            return True
        self.statusBar().showMessage(
            t("Verify 退出码 {rc} — 见右侧 Lineage 红项").format(rc=rc), 8000
        )
        QMessageBox.warning(
            self, t("Verify"), t("退出码 {rc}。请查看右侧 Lineage 红项。").format(rc=rc)
        )
        return False

    def _generate(self) -> None:
        if not self._session:
            QMessageBox.information(self, t("Generate"), t("请先打开项目"))
            return
        self._graph.flush_canvas()
        out = self._session.paths.project_dir / "generated"
        try:
            rc, report, result = self._session.generate(out)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("Generate 失败"), str(exc))
            return
        if not result.ok:
            QMessageBox.warning(
                self,
                t("Generate"),
                t("校验未通过，未写入磁盘（更改仍在内存）。")
                + "\n\n"
                + result.format_errors(),
            )
            return
        self._ara_cfg_ed.rebaseline_spins()
        self._graph.set_lineage_report(report or "")
        self._graph.rebuild()
        self._tabs.setCurrentWidget(self._signals_page)
        self._graph.focus_lineage()
        if rc != 0:
            QMessageBox.warning(
                self,
                "Generate",
                f"Verify/Generate 失败（码 {rc}）。请先修好右侧 Lineage。",
            )
            return
        self.statusBar().showMessage(
            t("Generate OK → {out}/include/gf_gen/").format(out=out), 8000
        )
        QMessageBox.information(
            self,
            "Generate",
            f"已生成 Proxy/Skeleton：\n{out}/include/gf_gen/\n\n"
            "可用 gf-codegen generate 在无 GUI 时同样产出。",
        )

    def _export_graph(self, *, kind: str) -> None:
        """Export SOR topology as Graphviz .dot or SVG (no in-app DAG page)."""
        if not self._session:
            QMessageBox.information(self, t("导出"), t("请先打开项目"))
            return
        sor = self._session.paths.out_sor
        if not sor.is_file():
            QMessageBox.warning(
                self,
                "导出",
                f"尚无 {sor.name}。请先 Verify（Ctrl+R）生成 SOR。",
            )
            return
        from gf_config.export_dag import export_sor_graph

        default_name = f"{self._session.paths.project_dir.name}_dag"
        if kind == "dot":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "导出 Graphviz .dot",
                str(Path.cwd() / f"{default_name}.dot"),
                "Graphviz (*.dot);;All (*)",
            )
            if not path:
                return
            out = Path(path)
            if out.suffix.lower() != ".dot":
                out = out.with_suffix(".dot")
            try:
                export_sor_graph(sor, dot_out=out)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, t("导出失败"), str(exc))
                return
            self.statusBar().showMessage(f"已导出 {out}", 8000)
            QMessageBox.information(self, t("导出"), t("已写入：\n{path}").format(path=out))
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Graphviz SVG",
            str(Path.cwd() / f"{default_name}.svg"),
            "SVG (*.svg);;All (*)",
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != ".svg":
            out = out.with_suffix(".svg")
        try:
            export_sor_graph(sor, svg_out=out)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("导出失败"), str(exc))
            return
        self.statusBar().showMessage(f"已导出 {out}", 8000)
        QMessageBox.information(self, t("导出"), t("已写入：\n{path}").format(path=out))
