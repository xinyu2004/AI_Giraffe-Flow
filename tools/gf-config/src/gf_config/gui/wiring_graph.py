"""Signal-link graph shell: session, fit/batch, selection, rebuild.

Items: ``wiring_graph_items``. Rebuild: ``wiring_rebuild``.
Mixins: interaction / menus / nodes. Zoom view: ``wiring_zoom``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession
from gf_config.gui.editor_history import HistoryHooksMixin
from gf_config.gui.lineage_view import LineageView
from gf_config.gui.wiring_graph_items import (
    ChannelEdge,
    EdgeCurve,
    MissingEdge,
    McuPeerLink,
    PortItem,
    ProcessCard,
    _qt_alive,
)
from gf_config.gui.wiring_interaction import WiringInteractionMixin
from gf_config.gui.wiring_menus import WiringMenusMixin
from gf_config.gui.wiring_nodes import WiringNodesMixin
from gf_config.gui.wiring_zoom import ZoomGraphicsView
from gf_config.i18n import t

class WiringGraphView(
    HistoryHooksMixin,
    WiringInteractionMixin,
    WiringMenusMixin,
    WiringNodesMixin,
    QWidget,
):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_history_hooks()
        self._session: ProjectSession | None = None
        self._nodes: dict[str, ProcessCard] = {}
        self._edges: list[EdgeCurve] = []
        self._channel_edges: list[ChannelEdge] = []
        self._missing: list[MissingEdge] = []
        self._peers: list[McuPeerLink] = []
        self._wire_src: PortItem | None = None
        self._wire_line: QGraphicsLineItem | None = None
        self._wire_forbid_mark: QGraphicsSimpleTextItem | None = None
        self._reloc_port: PortItem | None = None
        self._reloc_card_was_movable = True
        # 是否持有 QApplication override cursor（压过 PortItem 自带光标）
        self._app_cursor_pushed = False
        # process_name -> (x, y); survives rebuild so edits don't reset layout
        self._layout_pos: dict[str, tuple[float, float]] = {}
        # process_name -> QColor; filled each rebuild (anti-adjacent hues)
        self._process_color_map: dict[str, Any] = {}
        # 打开项目时 Tab 可能尚未显示，viewport=0 → fitInView 无效；显示后再 fit
        self._need_fit_on_show = False
        self._fit_scheduled = False
        self._batch_depth = 0
        self._undo_suppress = False
        self._drag_undo_armed = False
        # Mid-edge signal name size (pt); synced from wiring.canvas.edge_label_font_pt
        self._signal_label_pt = ProjectSession.DEFAULT_EDGE_LABEL_FONT_PT
        self._lineage_report_text = ""
        self._lineage_placeholder = t("尚无 lineage。菜单：文件 → Verify（Ctrl+R）")

        self._scene = QGraphicsScene(self)
        self._view = ZoomGraphicsView(self._scene, self)
        self._scene.selectionChanged.connect(self._on_selection_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view, stretch=1)

        # Ctrl 按下/松开即时切光标（不依赖 view 焦点、不必先挪鼠标）
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Ctrl+H reset-zoom: MainWindow View menu (ApplicationShortcut) only —
        # a second QShortcut here caused Ambiguous shortcut overload.
        sc_del = QShortcut(QKeySequence.StandardKey.Delete, self)
        sc_del.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_del.activated.connect(self._delete_selection)
        sc_back = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        sc_back.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_back.activated.connect(self._delete_selection)
        # Undo/Redo: ApplicationShortcut in MainWindow「编辑」菜单（Ctrl+Z / Ctrl+Y）

    def reset_zoom(self) -> None:
        self._view.reset_to_default_zoom()
        # 默认缩放若来自「未显示时的坏 fit」，再补一次完整适应
        if self._nodes:
            self._refresh_scene_rect()
            self._view.ensureVisible(self._nodes_content_rect(), 60, 60)

    def fit_in_window(self) -> None:
        self._fit_and_remember()

    def delete_selection(self) -> None:
        self._delete_selection()

    def _push_undo(self) -> None:
        if self._undo_suppress or self._session is None:
            return
        self._checkpoint(coalesce=False)

    def begin_card_drag(self, card: ProcessCard) -> None:
        """Remember press pose. Undo/session write only if the card actually moved."""
        if not _qt_alive(card):
            return
        p = card.pos()
        self._drag_start_xy = (round(p.x(), 1), round(p.y(), 1))

    def apply_session_restore(self, session: ProjectSession) -> None:
        """Reload canvas from session after doc undo/redo (keep DocHistory)."""
        self._session = session
        self._undo_suppress = True
        try:
            self._layout_pos.clear()
            nodes = (session.wiring.get("canvas") or {}).get("nodes") or {}
            if isinstance(nodes, dict):
                for name, ui in nodes.items():
                    if isinstance(ui, dict) and "x" in ui and "y" in ui:
                        self._layout_pos[str(name)] = (float(ui["x"]), float(ui["y"]))
            self._sync_signal_label_font_from_session()
            self.rebuild(fit_view=False, keep_layout_pos=True)
        finally:
            self._undo_suppress = False
            self._drag_undo_armed = False

    def signal_label_font_pt(self) -> int:
        """Point size for mid-edge signal name labels."""
        return int(self._signal_label_pt)

    def _sync_signal_label_font_from_session(self) -> None:
        pt = ProjectSession.DEFAULT_EDGE_LABEL_FONT_PT
        if self._session is not None:
            pt = self._session.get_edge_label_font_pt()
        self._signal_label_pt = pt

    def bump_signal_label_font(self, delta: int) -> None:
        """Increase/decrease mid-edge label size by ``delta`` pt (one undo step)."""
        if self._session is None or self._undo_suppress:
            return
        pt_i = max(7, min(18, int(self._signal_label_pt) + int(delta)))
        if pt_i == self._signal_label_pt:
            return
        self._push_undo()
        self._signal_label_pt = pt_i
        self._session.set_edge_label_font_pt(pt_i)
        self._apply_edge_label_fonts()
        self.relayout_edge_labels()
        self.changed.emit()
        self._end_doc_edit()

    def _apply_edge_label_fonts(self) -> None:
        """Refresh live edge/peer/missing labels without full rebuild."""
        from gf_config.gui.wiring_graph_items import _edge_label_font

        font = _edge_label_font(self)
        for e in (*self._edges, *self._channel_edges, *self._missing, *self._peers):
            lab = getattr(e, "_label", None)
            if lab is not None and _qt_alive(lab):
                lab.setFont(font)

    def clear_undo_history(self) -> None:
        self._drag_undo_armed = False
        self._clear_doc_history()

    def _is_quiet_boot(self) -> bool:
        """True while cli maps the window off-screen and suppresses deferred fit."""
        win = self.window()
        if win is None:
            return False
        if getattr(win, "_quiet_booting", False):
            return True
        return win.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        if self._is_quiet_boot():
            return
        if self._batch_depth:
            return
        if self._need_fit_on_show:
            self.schedule_fit()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        if self._batch_depth:
            return
        if self._is_quiet_boot():
            return
        if self._need_fit_on_show and self._view.viewport().width() > 40:
            self.schedule_fit()

    def begin_batch_update(self) -> None:
        """Freeze view paints during rebuild (open / quiet boot)."""
        self._batch_depth += 1
        if self._batch_depth == 1:
            self._view.setUpdatesEnabled(False)
            self._fit_scheduled = False

    def end_batch_update(self, *, fit: bool = True) -> None:
        if self._batch_depth <= 0:
            return
        self._batch_depth -= 1
        if self._batch_depth:
            return
        if fit:
            self.fit_now()
        # During quiet boot the CLI keeps paints frozen until reveal; do not
        # re-enable here or a pre-fit paint can slip out early.
        if not self._is_quiet_boot():
            self._view.setUpdatesEnabled(True)

    def fit_now(self) -> bool:
        """Synchronous fit; returns True if applied (viewport large enough)."""
        self._fit_scheduled = False
        if not self._nodes:
            self._need_fit_on_show = False
            return True
        vw = self._view.viewport().width()
        vh = self._view.viewport().height()
        if vw < 40 or vh < 40:
            self._need_fit_on_show = True
            self._refresh_scene_rect()
            return False
        self._fit_and_remember()
        return not self._need_fit_on_show

    def schedule_fit(self) -> None:
        """Coalesce fitInView to a single deferred call."""
        self._need_fit_on_show = True
        if self._batch_depth:
            return
        if self._fit_scheduled:
            return
        self._fit_scheduled = True
        QTimer.singleShot(0, self._fit_after_show)

    def _fit_after_show(self) -> None:
        self._fit_scheduled = False
        if self._batch_depth or not self._need_fit_on_show:
            return
        if self._is_quiet_boot():
            return
        if self._view.viewport().width() < 40:
            return
        self._fit_and_remember()

    def set_lineage_report(self, text: str) -> None:
        self._lineage_report_text = text or ""

    def set_lineage_placeholder(self, text: str) -> None:
        self._lineage_placeholder = text or ""

    def focus_lineage(self) -> None:
        """Show lineage report in a dialog (no docked right panel)."""
        dlg = QDialog(self.window())
        dlg.setWindowTitle(t("Lineage"))
        dlg.resize(720, 520)
        lay = QVBoxLayout(dlg)
        view = LineageView(dlg)
        if self._lineage_report_text.strip():
            view.set_report_text(self._lineage_report_text)
        else:
            view.set_placeholder(
                self._lineage_placeholder
                or t("尚无 lineage。菜单：文件 → Verify（Ctrl+R）")
            )
        lay.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        buttons.clicked.connect(dlg.accept)
        lay.addWidget(buttons)
        dlg.exec()

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        self._layout_pos.clear()
        self.clear_undo_history()
        self._last_topo: str | None = None
        self._sync_signal_label_font_from_session()
        # Rebuild without fit; open_project batch / quiet boot fits once.
        self.rebuild(fit_view=False)
        if self._batch_depth == 0:
            self._need_fit_on_show = True

    def _topology(self) -> str:
        if not self._session:
            return "ap_only"
        return self._session.topology()

    def _show_external_mcu(self) -> bool:
        """ap_mcu_cp shows MCU card; ap_only hides it (gateway 对外端口仍可见)."""
        return self._topology() == "ap_mcu_cp"

    def sync_topology_visibility(self) -> None:
        """SKU 拓扑变更后：有/无 MCU 显示与 YAML 对齐。"""
        if not self._session:
            return
        topo = self._topology()
        if topo == getattr(self, "_last_topo", None):
            return
        self.rebuild(fit_view=False)

    def note_card_pos_live(self, card: ProcessCard) -> None:
        """拖动过程中只记内存坐标，绝不改 sceneRect / 滚视口。"""
        if not _qt_alive(card):
            return
        p = card.pos()
        self._layout_pos[card.process_name] = (p.x(), p.y())

    def finalize_card_drag(self, card: ProcessCard) -> None:
        """鼠标松开：真拖过才写 session；单击不伪造坐标。"""
        if not _qt_alive(card):
            return
        p = card.pos()
        nx, ny = round(p.x(), 1), round(p.y(), 1)
        self._layout_pos[card.process_name] = (p.x(), p.y())
        start = getattr(self, "_drag_start_xy", None)
        moved = start is not None and (nx != start[0] or ny != start[1])
        self._drag_start_xy = None
        if moved and self._session is not None:
            self._push_undo()
            self._session.set_node_ui(card.process_name, x=nx, y=ny)
            self.changed.emit()
        self._refresh_scene_rect()
        self._drag_undo_armed = False
        self._end_doc_edit()
        # Drop ScrollHandDrag "closed hand" residual after item drag.
        self._view.viewport().unsetCursor()
        if moved:
            self.relayout_edge_labels()

    def _nodes_content_rect(self) -> QRectF:
        """以模块卡片为准算包围盒（含负坐标 MCU，不依赖细线 path）。"""
        rect = QRectF()
        for card in self._nodes.values():
            if not _qt_alive(card):
                continue
            # 用 pos + card 几何，避免 sceneBoundingRect 在未布局时偏小
            p = card.pos()
            br = QRectF(p.x() - 8, p.y() - 4, card.card_width + 16, card._height + 8)
            rect = br if rect.isNull() else rect.united(br)
        for peer in self._peers:
            if not _qt_alive(peer):
                continue
            br = peer.sceneBoundingRect()
            if not br.isNull():
                rect = br if rect.isNull() else rect.united(br)
            label = getattr(peer, "_label", None)
            if label is not None and _qt_alive(label):
                rect = rect.united(label.sceneBoundingRect())
        for e in self._edges:
            if not _qt_alive(e):
                continue
            br = e.sceneBoundingRect()
            if not br.isNull():
                rect = rect.united(br)
        for e in self._channel_edges:
            if not _qt_alive(e):
                continue
            br = e.sceneBoundingRect()
            if not br.isNull():
                rect = rect.united(br)
        if rect.isNull():
            return QRectF(0, 0, 400, 300)
        return rect

    # 场景边距：过大 → 内容已 fit 仍出现四向滚动条；过小 → 拖到边缘易被裁切
    _SCENE_PAD = 72.0

    def _refresh_scene_rect(self) -> None:
        if not self._nodes and not self._scene.items():
            self._scene.setSceneRect(QRectF())
            return
        pad = self._SCENE_PAD
        r = self._nodes_content_rect().adjusted(-pad, -pad, pad, pad)
        self._scene.setSceneRect(r)

    def _fit_and_remember(self) -> None:
        if not self._nodes:
            return
        vw = self._view.viewport().width()
        vh = self._view.viewport().height()
        if vw < 40 or vh < 40:
            # Tab 未显示时 fitInView 会得到错误缩放；延后到 showEvent
            self._need_fit_on_show = True
            self._refresh_scene_rect()
            return
        # sceneRect 与 fit 目标一致，避免「图已在框内却仍有拖动条」
        pad = self._SCENE_PAD
        content = self._nodes_content_rect().adjusted(-pad, -pad, pad, pad)
        self._scene.setSceneRect(content)
        self._view.fitInView(content, Qt.AspectRatioMode.KeepAspectRatio)
        # Bad fit (viewport still collapsing) → defer; do not remember tiny scale.
        if self._view.transform().m11() < 0.08:
            self._need_fit_on_show = True
            return
        self._view.remember_default_transform()
        self._need_fit_on_show = False

    def _clear_visual_emphasis(self) -> None:
        for card in list(self._nodes.values()):
            if _qt_alive(card):
                card.set_visual_state(emphasis=False, dimmed=False)
        for e in list(self._edges):
            if _qt_alive(e):
                e.set_visual_state(highlight=False, dimmed=False)
        for e in list(self._channel_edges):
            if _qt_alive(e):
                e.set_visual_state(highlight=False, dimmed=False)
        for m in list(self._missing):
            if _qt_alive(m):
                m.set_visual_state(highlight=False, dimmed=False)
        for p in list(self._peers):
            if _qt_alive(p):
                p.set_visual_state(highlight=False, dimmed=False)

    def relayout_edge_labels(self) -> None:
        """Re-run label deconflict after any path refresh that resets anchors."""
        from gf_config.gui.wiring_graph_items import deconflict_edge_labels

        deconflict_edge_labels([*self._edges, *self._channel_edges])

    def _on_selection_changed(self) -> None:
        # During rebuild/scene.clear, wrappers may outlive C++ objects.
        selected_missing = [
            i
            for i in self._scene.selectedItems()
            if isinstance(i, MissingEdge) and _qt_alive(i)
        ]
        selected_edges = [
            i for i in self._scene.selectedItems() if isinstance(i, EdgeCurve) and _qt_alive(i)
        ]
        selected_channels = [
            i
            for i in self._scene.selectedItems()
            if isinstance(i, ChannelEdge) and _qt_alive(i)
        ]
        selected_peers = [
            i for i in self._scene.selectedItems() if isinstance(i, McuPeerLink) and _qt_alive(i)
        ]
        selected_cards = [
            i for i in self._scene.selectedItems() if isinstance(i, ProcessCard) and _qt_alive(i)
        ]

        if selected_missing and not selected_cards and not selected_edges and not selected_peers:
            miss = selected_missing[0]
            self._focus_missing(miss, select=False, center=False)
            return

        if selected_channels and not selected_cards:
            edge = selected_channels[0]
            self._focus_channel_edge(edge, select=False, center=False)
            return

        if selected_edges and not selected_cards:
            edge = selected_edges[0]
            self._focus_edge(edge, select=False, center=False)
            return

        if selected_peers and not selected_cards:
            peer = selected_peers[0]
            self._focus_peer(peer, select=False, center=False)
            return

        if not selected_cards:
            self._clear_visual_emphasis()
            return

        focus = selected_cards[0]
        connected: set[EdgeCurve] = set()
        channel_hit: set[ChannelEdge] = set()
        neighbors: set[ProcessCard] = {focus}
        for e in self._edges:
            if e.src is focus or e.dst is focus:
                connected.add(e)
                neighbors.add(e.src)
                neighbors.add(e.dst)
        for e in self._channel_edges:
            if e.src is focus or e.dst is focus:
                channel_hit.add(e)
                neighbors.add(e.src)
                neighbors.add(e.dst)
        for m in self._missing:
            if m.src is focus or m.dst is focus:
                neighbors.add(m.src)
                neighbors.add(m.dst)
        peer_hit: set[McuPeerLink] = set()
        for p in self._peers:
            if p.mcu is focus or p.gateway is focus:
                peer_hit.add(p)
                neighbors.add(p.mcu)
                neighbors.add(p.gateway)

        for card in self._nodes.values():
            if card is focus:
                card.set_visual_state(emphasis=True, dimmed=False)
            elif card in neighbors:
                card.set_visual_state(emphasis=False, dimmed=False)
            else:
                card.set_visual_state(emphasis=False, dimmed=True)

        for e in self._edges:
            if e not in connected:
                e.set_visual_state(highlight=False, dimmed=True, role="")
            elif e.src is focus:
                # 从本节点出去 = Out → 绿
                e.set_visual_state(highlight=True, dimmed=False, role="out")
            else:
                # 进入本节点 = In → 橙
                e.set_visual_state(highlight=True, dimmed=False, role="in")

        for e in self._channel_edges:
            if e not in channel_hit:
                e.set_visual_state(highlight=False, dimmed=True, role="")
            elif e.src is focus:
                e.set_visual_state(highlight=True, dimmed=False, role="out")
            else:
                e.set_visual_state(highlight=True, dimmed=False, role="in")

        for p in self._peers:
            p.set_visual_state(highlight=(p in peer_hit), dimmed=(p not in peer_hit))

        for m in self._missing:
            hit = m.src is focus or m.dst is focus
            m.set_visual_state(highlight=hit, dimmed=not hit)

    # --- wiring drag ---

    def eventFilter(self, obj, event) -> bool:  # type: ignore[no-untyped-def]
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            key = event.key()
            if key in (Qt.Key.Key_Control, Qt.Key.Key_Meta):
                self.refresh_port_hover_cursor()
        return super().eventFilter(obj, event)

    def rebuild(
        self,
        *,
        fit_view: bool = False,
        reset_layout: bool = False,
        keep_layout_pos: bool = False,
    ) -> None:
        from gf_config.gui.wiring_rebuild import rebuild_wiring_graph

        rebuild_wiring_graph(
            self,
            fit_view=fit_view,
            reset_layout=reset_layout,
            keep_layout_pos=keep_layout_pos,
        )


    @staticmethod
    def _compute_depths(procs: list[str], flows: list[dict[str, Any]]) -> dict[str, int]:
        depth = {p: 0 for p in procs}
        for _ in range(len(procs) + 2):
            changed = False
            for fl in flows:
                a, b = str(fl.get("from") or ""), str(fl.get("to") or "")
                if a in depth and b in depth and depth[a] + 1 > depth[b]:
                    depth[b] = depth[a] + 1
                    changed = True
            if not changed:
                break
        return depth

# ProcessCard / PortItem refer to WiringGraphView via from __future__ annotations
