"""Signal-link graph view: canvas widget, wiring UX, import/hpp.

Graphics items live in ``wiring_graph_items`` (ProcessCard / PortItem / edges).
This module owns the view, session wiring, Ctrl+drag relocate, and dialogs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QEvent, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QShortcut,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import (
    ProjectSession,
    canon_service,
    is_channel_svc,
    normalize_channel_slot,
    short_service,
)
from gf_config.gui.cursors import port_move_cursor, wire_link_cursor
from gf_config.gui.editor_history import HistoryHooksMixin
from gf_config.gui.lineage_view import LineageView
from gf_config.gui.wiring_dialogs import (
    AddNodeDialog,
    FrameIngestDialog,
    ImportPortsDialog,
    PortEditDialog,
)
from gf_config.gui.wiring_graph_items import (
    ChannelEdge,
    DeselectableListWidget,
    EdgeCurve,
    MissingEdge,
    McuPeerLink,
    PortItem,
    ProcessCard,
    RouteHandle,
    _norm_side,
    _qt_alive,
    is_camera_source,
    is_external_node,
    is_frame_ingest_node,
    port_label,
    port_link_key,
)
from gf_config.i18n import t

class ZoomGraphicsView(QGraphicsView):
    """Ctrl+wheel zoom; wire-drag mouse routing; stores default transform."""

    def __init__(self, scene: QGraphicsScene, graph: WiringGraphView, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self._graph = graph
        self._default_transform = QTransform()
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#0b1612")))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # fit 后上下左右居中（勿 AlignTop，否则会偏上）
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # AsNeeded：内容已 fit 时不占滚动条；放大后仍可拖动画布
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._graph._on_view_context_menu)

    def remember_default_transform(self) -> None:
        # Never lock "default zoom" to a broken cold-start fit (tiny m11).
        if self.transform().m11() < 0.08:
            return
        self._default_transform = QTransform(self.transform())

    def reset_to_default_zoom(self) -> None:
        self.setTransform(QTransform(self._default_transform))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                return
            zoom_in = delta > 0
            factor = 1.15 if zoom_in else 1 / 1.15
            cur = self.transform().m11()
            # If stuck below the floor after a bad fit, still allow zoom-in.
            if zoom_in:
                if cur * factor > 4.0:
                    event.accept()
                    return
            else:
                if cur * factor < 0.25:
                    event.accept()
                    return
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().keyPressEvent(event)
        if event.key() in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Meta,
        ):
            self._graph.refresh_port_hover_cursor()

    def keyReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().keyReleaseEvent(event)
        if event.key() in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Meta,
        ):
            self._graph.refresh_port_hover_cursor()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._graph._reloc_port is not None:
            self._graph.update_port_relocate(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._graph._wire_src is not None:
            self._graph.update_wire_preview(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if (
            self._graph._wire_src is None
            and self._graph._reloc_port is None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            item = self.itemAt(event.position().toPoint())
            cur: QGraphicsItem | None = item
            interactive = False
            while cur is not None:
                if isinstance(
                    cur, (EdgeCurve, MissingEdge, McuPeerLink, PortItem, ProcessCard)
                ):
                    interactive = True
                    break
                cur = cur.parentItem()
            # allow selecting edges/cards instead of always panning
            self.setDragMode(
                QGraphicsView.DragMode.NoDrag
                if interactive
                else QGraphicsView.DragMode.ScrollHandDrag
            )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            if self._graph._reloc_port is not None:
                self._graph.finish_port_relocate()
                event.accept()
                return
            if self._graph._wire_src is not None:
                self._graph.finish_wire(self.mapToScene(event.position().toPoint()))
                event.accept()
                return
        super().mouseReleaseEvent(event)
        if self._graph._wire_src is None and self._graph._reloc_port is None:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)


class WiringGraphView(HistoryHooksMixin, QWidget):
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
        # 打开项目时 Tab 可能尚未显示，viewport=0 → fitInView 无效；显示后再 fit
        self._need_fit_on_show = False
        self._fit_scheduled = False
        self._batch_depth = 0
        self._undo_suppress = False
        self._drag_undo_armed = False

        self._scene = QGraphicsScene(self)
        self._view = ZoomGraphicsView(self._scene, self)
        self._scene.selectionChanged.connect(self._on_selection_changed)

        self._flow_list = DeselectableListWidget(self)
        self._flow_list.setMinimumWidth(340)
        self._flow_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText(t("搜索信号（模糊匹配名 / 进程）…"))
        self._search.textChanged.connect(self._on_search_text)
        self._search_hits = QListWidget(self)
        self._search_hits.setMaximumHeight(140)
        self._search_hits.itemClicked.connect(self._on_search_hit_clicked)
        self._search_hits.setVisible(False)

        self._legend = QLabel(
            t(
                "Out=绿 · In=橙 · !=未连\n"
                "线色=源模块（同卡扇出同色）· 蓝点划线=GfChannel\n"
                "拖拽连线 · Ctrl+拖改边/同边调序 · Ctrl+Z/Y 撤销"
            ),
            self,
        )
        self._legend.setWordWrap(True)
        self._legend.setStyleSheet("color: #a9cfc0; font-size: 11px;")

        flows_page = QWidget(self)
        flows_page.setObjectName("gf_flows_page")
        flows_l = QVBoxLayout(flows_page)
        flows_l.setContentsMargins(4, 4, 4, 4)
        flows_l.addWidget(self._legend)
        flows_l.addWidget(self._search)
        flows_l.addWidget(self._search_hits)
        flows_l.addWidget(QLabel(t("dataflows / channel_flows")))
        flows_l.addWidget(self._flow_list)

        self._lineage = LineageView(self)
        self._lineage.set_placeholder(t("尚无 lineage。菜单：文件 → Verify（Ctrl+R）"))

        self._right_tabs = QTabWidget(self)
        self._right_tabs.addTab(flows_page, t("连线"))
        self._right_tabs.addTab(self._lineage, t("Lineage"))

        self._right_panel = QWidget(self)
        self._right_panel.setObjectName("gf_right_panel")
        right = QVBoxLayout(self._right_panel)
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(self._right_tabs)
        self._right_panel.setMinimumWidth(280)
        self._right_panel.setMaximumWidth(420)
        self._right_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )

        self._btn_toggle_right = QToolButton(self)
        # 面板在右：展开时 ▶=收起；收起后 ◀=展开。默认收起，画布优先。
        self._btn_toggle_right.setText("◀")
        self._btn_toggle_right.setToolTip(t("折叠 / 展开右侧面板（连线 + Lineage）"))
        self._btn_toggle_right.setFixedWidth(22)
        self._btn_toggle_right.clicked.connect(self._toggle_right_panel)
        self._right_collapsed = True
        self._right_panel.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(self._btn_toggle_right, stretch=0)
        layout.addWidget(self._right_panel, stretch=0)

        self._flow_list.currentRowChanged.connect(self._highlight_list_edge)
        # Ctrl 按下/松开即时切光标（不依赖 view 焦点、不必先挪鼠标）
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        sc = QShortcut(QKeySequence("Ctrl+H"), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.reset_zoom)
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

    def toggle_right_panel(self) -> None:
        self._toggle_right_panel()

    def delete_selection(self) -> None:
        self._delete_selection()

    def _push_undo(self) -> None:
        if self._undo_suppress or self._session is None:
            return
        self._checkpoint(coalesce=False)

    def begin_card_drag(self, card: ProcessCard) -> None:
        """Arm one undo snapshot per drag gesture."""
        if self._drag_undo_armed:
            return
        self._push_undo()
        self._drag_undo_armed = True

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
            self.rebuild(fit_view=False, keep_layout_pos=True)
        finally:
            self._undo_suppress = False
            self._drag_undo_armed = False

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

    def _toggle_right_panel(self) -> None:
        self._right_collapsed = not self._right_collapsed
        self._right_panel.setVisible(not self._right_collapsed)
        self._btn_toggle_right.setText("◀" if self._right_collapsed else "▶")

    def ensure_right_panel(self) -> None:
        if self._right_collapsed:
            self._toggle_right_panel()

    def set_lineage_report(self, text: str) -> None:
        self._lineage.set_report_text(text or "")

    def set_lineage_placeholder(self, text: str) -> None:
        self._lineage.set_placeholder(text)

    def focus_lineage(self) -> None:
        """Verify/Generate 后切到右侧 Lineage 页。"""
        self.ensure_right_panel()
        self._right_tabs.setCurrentWidget(self._lineage)

    def focus_flows(self) -> None:
        self.ensure_right_panel()
        self._right_tabs.setCurrentIndex(0)

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        self._layout_pos.clear()
        self.clear_undo_history()
        self._last_topo: str | None = None
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
        """鼠标松开：写 session、扩 sceneRect；不 ensureVisible（避免拖飞）。"""
        if not _qt_alive(card):
            return
        p = card.pos()
        self._layout_pos[card.process_name] = (p.x(), p.y())
        if self._session is not None:
            fields: dict[str, Any] = {
                "x": round(p.x(), 1),
                "y": round(p.y(), 1),
                "out_side": card.out_side,
                "in_side": card.in_side,
            }
            if card.port_sides:
                fields["port_sides"] = dict(card.port_sides)
            if card.kind and card.kind != "process":
                fields["kind"] = card.kind
            if card.label:
                fields["label"] = card.label
            self._session.set_node_ui(card.process_name, **fields)
            self.changed.emit()
        self._refresh_scene_rect()
        self._drag_undo_armed = False
        self._end_doc_edit()
        # Drop ScrollHandDrag "closed hand" residual after item drag.
        self._view.viewport().unsetCursor()

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

    def refresh_port_hover_cursor(self) -> None:
        """Ctrl press/release while hovering a port → swap link vs move cursor."""
        if self._wire_src is not None or self._reloc_port is not None:
            return
        gp = QCursor.pos()
        vp = self._view.viewport().mapFromGlobal(gp)
        if not self._view.viewport().rect().contains(vp):
            return
        item = self._view.itemAt(vp)
        cur: QGraphicsItem | None = item
        while cur is not None:
            if isinstance(cur, PortItem) and _qt_alive(cur):
                mods = QApplication.queryKeyboardModifiers()
                cur.setCursor(
                    port_move_cursor()
                    if mods & Qt.KeyboardModifier.ControlModifier
                    else wire_link_cursor()
                )
                return
            cur = cur.parentItem()

    def _set_wire_forbid_mark(self, scene_pos: QPointF | None) -> None:
        """Illegal drop: red ✕ near apex (keep hand cursor — no ForbiddenCursor)."""
        mark = self._wire_forbid_mark
        if scene_pos is None:
            if mark is not None and _qt_alive(mark):
                mark.hide()
            return
        if mark is None or not _qt_alive(mark):
            mark = QGraphicsSimpleTextItem("✕")
            font = QFont()
            font.setPointSize(22)
            font.setBold(True)
            mark.setFont(font)
            mark.setBrush(QBrush(QColor("#c0392b")))
            mark.setZValue(200)
            mark.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            self._scene.addItem(mark)
            self._wire_forbid_mark = mark
        mark.setPos(scene_pos.x() + 10, scene_pos.y() - 28)
        mark.show()

    def _clear_wire_forbid_mark(self) -> None:
        mark = self._wire_forbid_mark
        self._wire_forbid_mark = None
        if mark is not None and _qt_alive(mark) and mark.scene():
            self._scene.removeItem(mark)

    def _port_at(self, scene_pos: QPointF) -> PortItem | None:
        """Nearest PortItem near scene_pos (fat pick), skipping wire preview."""
        r = float(PortItem.HIT)
        rect = QRectF(scene_pos.x() - r, scene_pos.y() - r, 2 * r, 2 * r)
        best: PortItem | None = None
        best_d = 1e18
        for item in self._scene.items(rect):
            if item is self._wire_line:
                continue
            cur: QGraphicsItem | None = item
            port: PortItem | None = None
            while cur is not None:
                if isinstance(cur, PortItem):
                    port = cur
                    break
                cur = cur.parentItem()
            if port is None or not _qt_alive(port):
                continue
            c = port.scene_center()
            d = (c.x() - scene_pos.x()) ** 2 + (c.y() - scene_pos.y()) ** 2
            if d < best_d:
                best_d = d
                best = port
        return best

    def begin_wire(self, src_port: PortItem) -> None:
        self.cancel_port_relocate()
        self.cancel_wire()
        self._wire_src = src_port
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Override beats PortItem hover cursors for the whole drag.
        self._push_app_cursor(wire_link_cursor())
        line = QGraphicsLineItem()
        line.setPen(QPen(QColor("#f7dc6f"), 2.0, Qt.PenStyle.DashLine))
        line.setZValue(100)
        line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        c = src_port.scene_center()
        line.setLine(c.x(), c.y(), c.x(), c.y())
        self._scene.addItem(line)
        self._wire_line = line

    def update_wire_preview(self, scene_pos: QPointF) -> None:
        if self._wire_src is None or self._wire_line is None:
            return
        c = self._wire_src.scene_center()
        self._wire_line.setLine(c.x(), c.y(), scene_pos.x(), scene_pos.y())
        target = self._port_at(scene_pos)
        src = self._wire_src
        if target is None:
            ok: bool | None = None  # blank = searching
        else:
            ok = self._wire_pair_ok(src, target)
        # Legal → green; illegal → red dash + ✕; searching → yellow dash. Cursor stays hand.
        if ok is True:
            pen = QPen(QColor("#2ecc71"), 2.5, Qt.PenStyle.SolidLine)
        elif ok is False:
            pen = QPen(QColor("#c0392b"), 2.8, Qt.PenStyle.DashLine)
        else:
            pen = QPen(QColor("#f7dc6f"), 2.0, Qt.PenStyle.DashLine)
        self._wire_line.setPen(pen)
        self._set_wire_forbid_mark(scene_pos if ok is False else None)

    def _wire_pair_ok(self, src: PortItem, target: PortItem) -> bool:
        if target is src or target.card is src.card:
            return False
        if target.direction == src.direction:
            return False
        out_port = src if src.direction == "out" else target
        in_port = target if src.direction == "out" else src
        out_cam = out_port.card.is_frame_ingest()
        in_cam = in_port.card.is_frame_ingest()
        if out_cam and in_cam:
            return False
        if in_cam:
            return False  # frame_ingest 只出不进
        if out_cam:
            return not in_port.card.is_external()
        if out_port.card.is_external() or in_port.card.is_external():
            return True
        # SOA: Out→In；禁止把 GfChannel 口当普通服务边混连
        if is_channel_svc(out_port.service) or is_channel_svc(in_port.service):
            return out_cam  # only frame_ingest Out owns channel svc
        return True

    def finish_wire(self, scene_pos: QPointF) -> None:
        src = self._wire_src
        # hit-test before cancel clears the preview line
        target = self._port_at(scene_pos)
        self.cancel_wire()
        if src is None or not self._session:
            return
        if target is None or not self._wire_pair_ok(src, target):
            return

        out_port = src if src.direction == "out" else target
        in_port = target if src.direction == "out" else src

        # GfChannel: frame_ingest Out → consumer（不写 dataflows / deployments）
        if out_port.card.is_frame_ingest():
            slot = (out_port.service or "").strip()
            if not is_channel_svc(slot):
                sid = ProjectSession.slot_id_from_camera_process(
                    out_port.card.process_name
                )
                slot = ProjectSession.gf_channel_slot_name(sid)
            self._push_undo()
            ok = self._session.add_channel_flow(
                out_port.card.process_name,
                in_port.card.process_name,
                slot=slot,
            )
            if not ok:
                QMessageBox.information(self, t("连线"), t("该 GfChannel 边已存在"))
                return
            self.rebuild()
            self.changed.emit()
            return

        self._push_undo()
        out_svc = canon_service(out_port.service)
        in_svc = (in_port.service or "").strip()
        # Simulink-like: connection carries the Out signal; In port name follows Out.
        if not in_svc:
            new_req = list(in_port.card.requires) + [out_svc]
            # 保留画布上的 GfChannel In
            new_req = self._merge_channel_requires(
                in_port.card.process_name, new_req
            )
            soa_req = [r for r in new_req if not is_channel_svc(r)]
            self._session.set_ports(
                in_port.card.process_name,
                [p for p in in_port.card.provides if not is_channel_svc(p)],
                soa_req,
            )
        elif short_service(in_svc) != short_service(out_svc) and not is_channel_svc(
            in_svc
        ):
            new_req = [
                out_svc if short_service(r) == short_service(in_svc) else r
                for r in in_port.card.requires
                if not is_channel_svc(r)
            ]
            self._session.set_ports(
                in_port.card.process_name,
                [p for p in in_port.card.provides if not is_channel_svc(p)],
                new_req,
            )

        ok = self._session.add_dataflow(
            out_port.card.process_name,
            out_svc,
            in_port.card.process_name,
        )
        if not ok:
            QMessageBox.information(self, t("连线"), t("该 dataflow 已存在"))
            return
        self.rebuild()
        self.changed.emit()

    def _merge_channel_requires(self, process: str, requires: list[str]) -> list[str]:
        """Keep existing channel In slots from channel_flows when editing SOA ports."""
        if not self._session:
            return requires
        extra: list[str] = []
        for fl in self._session.channel_flows():
            if str(fl.get("to")) != process:
                continue
            slot = str(fl.get("slot") or "").strip()
            if not slot and str(fl.get("from") or "").startswith("camera."):
                slot = ProjectSession.gf_channel_slot_name(
                    ProjectSession.slot_id_from_camera_process(str(fl.get("from")))
                )
            if slot and slot not in requires and slot not in extra:
                extra.append(slot)
        return list(requires) + extra

    def cancel_wire(self) -> None:
        self._wire_src = None
        if self._wire_line is not None:
            if self._wire_line.scene():
                self._scene.removeItem(self._wire_line)
            self._wire_line = None
        self._clear_wire_forbid_mark()
        self._pop_app_cursor()
        for card in self._nodes.values():
            for p in card._out_ports + card._in_ports:
                if _qt_alive(p):
                    p.setCursor(wire_link_cursor())
        if self._reloc_port is None:
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def _push_app_cursor(self, cursor: QCursor) -> None:
        self._pop_app_cursor()
        QApplication.setOverrideCursor(cursor)
        self._app_cursor_pushed = True

    def _pop_app_cursor(self) -> None:
        if self._app_cursor_pushed:
            QApplication.restoreOverrideCursor()
            self._app_cursor_pushed = False

    # --- port side relocate + same-side reorder (Ctrl+drag) ---

    def begin_port_relocate(self, port: PortItem) -> None:
        self.cancel_wire()
        self.cancel_port_relocate()
        self._reloc_port = port
        port._home_pos = QPointF(port.pos())
        port._origin_side = port.side
        peers = self._ports_on_side_unified(port.card, port.side, exclude=None)
        try:
            port._origin_index = peers.index(port)
        except ValueError:
            port._origin_index = 0
        port._pending_side = port.side
        port._pending_index = port._origin_index
        self._reloc_card_was_movable = bool(
            port.card.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        )
        port.card.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Snapshot once at gesture start (finish must stay cheap for cursor restore).
        if not self._drag_undo_armed:
            self._push_undo()
            self._drag_undo_armed = True
        self._push_app_cursor(port_move_cursor())

    def _services_list(self, card: ProcessCard, direction: str) -> list[str]:
        return list(card.provides if direction == "out" else card.requires)

    def _ports_on_side_unified(
        self,
        card: ProcessCard,
        side: str,
        *,
        exclude: PortItem | None = None,
    ) -> list[PortItem]:
        """Same-side Out+In peers in current slot order (allows interleave)."""
        side_n = _norm_side(side, "left")
        by_key = {
            ProcessCard.slot_key(p.direction, p.service): p
            for p in (card._out_ports + card._in_ports)
            if p.side == side_n
        }
        ex_key = (
            ProcessCard.slot_key(exclude.direction, exclude.service)
            if exclude is not None
            else ""
        )
        out: list[PortItem] = []
        for raw in card.port_slot_order.get(side_n, []):
            if ex_key and raw == ex_key:
                continue
            p = by_key.pop(raw, None)
            if p is not None:
                out.append(p)
        for key, p in list(by_key.items()):
            if ex_key and key == ex_key:
                continue
            out.append(p)
        return out

    def _insert_index_on_side(
        self, port: PortItem, side: str, scene_pos: QPointF
    ) -> int:
        """Insert index among same-side Out+In peers."""
        card = port.card
        local = card.mapFromScene(scene_pos)
        peers = self._ports_on_side_unified(card, side, exclude=port)
        if side in ("left", "right"):
            coord = local.y()
            for i, p in enumerate(peers):
                if coord < p.pos().y():
                    return i
            return len(peers)
        coord = local.x()
        for i, p in enumerate(peers):
            if coord < p.pos().x():
                return i
        return len(peers)

    def _preview_port_layout(
        self, moving: PortItem, new_side: str, new_index: int
    ) -> None:
        """Live-preview side + order without mutating YAML yet."""
        from collections import defaultdict

        card = moving.card
        new_side = _norm_side(new_side, moving.side)
        groups: dict[str, list[PortItem]] = defaultdict(list)
        for p in card._out_ports + card._in_ports:
            if p is moving:
                continue
            groups[p.side].append(p)
        # Keep each side's relative order from current slot list when possible.
        for side in list(groups.keys()):
            ordered = self._ports_on_side_unified(card, side, exclude=moving)
            groups[side] = [p for p in ordered if p in groups[side]] + [
                p for p in groups[side] if p not in ordered
            ]
        dest = list(groups.get(new_side, []))
        new_index = max(0, min(int(new_index), len(dest)))
        dest.insert(new_index, moving)
        groups[new_side] = dest
        for side, plist in groups.items():
            n = len(plist)
            for i, p in enumerate(plist):
                p.side = side
                p.index = i
                p.setPos(card._place_on_side(side, i, n))
        moving._pending_side = new_side
        moving._pending_index = new_index
        for e in list(card._edges):
            if hasattr(e, "update_path"):
                e.update_path()

    @staticmethod
    def _reorder_services_on_side(
        services: list[str],
        moved: str,
        new_side: str,
        new_index: int,
        side_of,
    ) -> list[str]:
        """Reorder `moved` among services that share `new_side`; keep others stable."""
        key = short_service(moved)
        moved_c = next((s for s in services if short_service(s) == key), moved)
        rest = [s for s in services if short_service(s) != key]
        same = [s for s in rest if side_of(s) == new_side]
        new_index = max(0, min(int(new_index), len(same)))
        same.insert(new_index, moved_c)
        result: list[str] = []
        emitted = False
        for s in rest:
            if side_of(s) == new_side:
                if not emitted:
                    result.extend(same)
                    emitted = True
            else:
                result.append(s)
        if not emitted:
            result.extend(same)
        return result

    def update_port_relocate(self, scene_pos: QPointF) -> None:
        port = self._reloc_port
        if port is None or not _qt_alive(port):
            return
        side = port.nearest_card_side(scene_pos)
        idx = self._insert_index_on_side(port, side, scene_pos)
        self._preview_port_layout(port, side, idx)

    def finish_port_relocate(self) -> None:
        port = self._reloc_port
        if port is None:
            self.cancel_port_relocate()
            return
        pending = port._pending_side
        pending_idx = port._pending_index
        origin = port._origin_side
        origin_idx = port._origin_index
        card = port.card
        # Clear reloc mode first so mouse/view stop treating this as a drag.
        self._reloc_port = None
        if self._reloc_card_was_movable and _qt_alive(card):
            card.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # Keep override until persist/rebuild finishes — otherwise PortItem's
        # Ctrl move cursor flashes during deepcopy and feels "stuck".
        try:
            if not _qt_alive(port) or not _qt_alive(card):
                return
            side_changed = bool(pending and pending != origin)
            order_changed = (
                pending_idx is not None and int(pending_idx) != int(origin_idx)
            )
            if pending and (side_changed or order_changed):
                self.apply_port_side_and_order(
                    port, pending, int(pending_idx or 0), card=card
                )
            else:
                port._pending_side = None
                port._pending_index = None
                card._rebuild_ports()
                for e in list(card._edges):
                    if hasattr(e, "update_path"):
                        e.update_path()
        finally:
            self._pop_app_cursor()
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._drag_undo_armed = False
            self._end_doc_edit()
            self.refresh_port_hover_cursor()

    def cancel_port_relocate(self) -> None:
        port = self._reloc_port
        self._reloc_port = None
        card = port.card if port is not None and _qt_alive(port) else None
        try:
            if port is not None and _qt_alive(port):
                port._pending_side = None
                port._pending_index = None
                if self._reloc_card_was_movable and card is not None and _qt_alive(card):
                    card.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                if card is not None and _qt_alive(card):
                    card._rebuild_ports()
                    for e in list(card._edges):
                        if hasattr(e, "update_path"):
                            e.update_path()
        finally:
            self._pop_app_cursor()
            if self._wire_src is None:
                self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # Cancelled gesture: drop the armed undo snapshot usability by
            # keeping stack as-is (snapshot == current). Clear armed flag.
            self._drag_undo_armed = False
            self._end_doc_edit()
            self.refresh_port_hover_cursor()

    def apply_port_side_and_order(
        self,
        port: PortItem,
        new_side: str,
        new_index: int,
        *,
        card: ProcessCard | None = None,
    ) -> None:
        """Persist port edge + same-side Out/In slot order (may interleave)."""
        from collections import defaultdict

        if not self._session:
            return
        card = card if card is not None else port.card
        if not _qt_alive(card):
            return
        # Capture identity before any rebuild destroys PortItem
        direction = port.direction
        moved_svc = port.service
        key = short_service(moved_svc)
        moved_slot = ProcessCard.slot_key(direction, moved_svc)
        side_n = _norm_side(new_side, "right" if direction == "out" else "left")
        dir_key = ProcessCard.port_side_key(direction, moved_svc)
        card.port_sides[dir_key] = side_n
        # 去掉旧版无方向键，避免同名 In/Out 再被绑在一起
        card.port_sides.pop(key, None)

        # Drop moved from all side orders, then insert on destination side.
        for s, keys in list(card.port_slot_order.items()):
            card.port_slot_order[s] = [k for k in keys if k != moved_slot]
            if not card.port_slot_order[s]:
                card.port_slot_order.pop(s, None)

        out_by: dict[str, list[str]] = defaultdict(list)
        in_by: dict[str, list[str]] = defaultdict(list)
        for svc in card.provides:
            if direction == "out" and short_service(svc) == key:
                continue
            out_by[card.port_side_for(svc, "out")].append(svc)
        for svc in card.requires:
            if direction == "in" and short_service(svc) == key:
                continue
            in_by[card.port_side_for(svc, "in")].append(svc)

        base = card._slots_for_side(side_n, out_by, in_by)
        idx = max(0, min(int(new_index), len(base)))
        base.insert(idx, (direction, moved_svc))
        card.port_slot_order[side_n] = [
            ProcessCard.slot_key(d, svc) for d, svc in base
        ]
        for s in ("left", "right", "top", "bottom"):
            if s == side_n:
                continue
            rebuilt = card._slots_for_side(s, out_by, in_by)
            if rebuilt:
                card.port_slot_order[s] = [
                    ProcessCard.slot_key(d, svc) for d, svc in rebuilt
                ]
            else:
                card.port_slot_order.pop(s, None)

        new_prov = self._services_from_slot_orders(card, "out", list(card.provides))
        new_req = self._services_from_slot_orders(card, "in", list(card.requires))

        self._session.set_node_ui(
            card.process_name,
            port_sides=dict(card.port_sides),
            port_slot_order={
                s: list(keys) for s, keys in card.port_slot_order.items()
            },
        )
        # frame_ingest Outs are GfChannel slots (canvas only) — never push through
        # set_ports / deployments (that strips channel services).
        if card.is_frame_ingest():
            card.provides = list(new_prov)
            card.requires = list(new_req)
            card._height = card._compute_height()
            card._rebuild_ports()
            card.prepareGeometryChange()
            card.update()
        else:
            self._session.set_ports(
                card.process_name, new_prov, new_req, prune_flows=False
            )
            card.set_ports(new_prov, new_req)
        for e in list(card._edges):
            if hasattr(e, "update_path"):
                e.update_path()
        self._drag_undo_armed = False
        self._end_doc_edit()
        self.changed.emit()

    @staticmethod
    def _services_from_slot_orders(
        card: ProcessCard, direction: str, services: list[str]
    ) -> list[str]:
        """Order provides/requires to follow interleaved port_slot_order."""
        by_short = {short_service(s): s for s in services}
        seen: set[str] = set()
        result: list[str] = []
        for side in ("left", "right", "top", "bottom"):
            for raw in card.port_slot_order.get(side, []):
                parsed = ProcessCard.parse_slot_key(raw)
                if parsed is None or parsed[0] != direction:
                    continue
                sk = parsed[1]
                full = by_short.get(sk)
                if full is not None and sk not in seen:
                    result.append(full)
                    seen.add(sk)
        for s in services:
            sk = short_service(s)
            if sk not in seen:
                result.append(s)
                seen.add(sk)
        return result

    # --- context menus / edit ---

    def _on_view_context_menu(self, pos) -> None:  # type: ignore[no-untyped-def]
        scene_pos = self._view.mapToScene(pos)
        item = self._scene.itemAt(scene_pos, self._view.transform())
        cur: QGraphicsItem | None = item
        while cur is not None:
            if isinstance(cur, EdgeCurve):
                self.show_edge_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, ChannelEdge):
                self.show_channel_edge_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, MissingEdge):
                self.show_missing_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, ProcessCard):
                self.show_card_menu(cur, self._view.mapToGlobal(pos))
                return
            cur = cur.parentItem()

        menu = QMenu(self)
        act_add = menu.addAction(t("添加模块…"))
        act_cam = menu.addAction(t("添加 frame_ingest…"))
        act_ext = menu.addAction(t("添加外部 MCU…"))
        act_ext.setEnabled(self._show_external_mcu())
        if not self._show_external_mcu():
            act_ext.setToolTip(
                t(
                    "当前拓扑为仅 AP。请先改为「AP + MCU CP」；"
                    "对外控制信号可挂在 gateway 端口上。"
                )
            )
        act_import = menu.addAction(t("导入 hpp/h…"))
        chosen = menu.exec(self._view.mapToGlobal(pos))
        if chosen is act_add:
            self.add_node()
        elif chosen is act_cam:
            self.add_frame_ingest()
        elif chosen is act_ext:
            self.add_external_mcu_node()
        elif chosen is act_import:
            self.import_hpp()

    def show_edge_menu(self, edge: EdgeCurve, global_pos) -> None:  # type: ignore[no-untyped-def]
        edge.setSelected(True)
        menu = QMenu(self)
        act_edit = menu.addAction(t("编辑信号名…"))
        act_reset = menu.addAction(t("重置连线路径"))
        act_del = menu.addAction(t("删除信号线"))
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_edge(edge)
        elif chosen is act_reset:
            if self._session:
                self._session.set_flow_route(edge.flow, None)
            else:
                edge.flow.pop("route", None)
            edge.update_path()
            self.changed.emit()
        elif chosen is act_del:
            self._remove_edge(edge)

    def show_channel_edge_menu(self, edge: ChannelEdge, global_pos) -> None:  # type: ignore[no-untyped-def]
        edge.setSelected(True)
        menu = QMenu(self)
        act_del = menu.addAction(t("删除 GfChannel 边"))
        chosen = menu.exec(global_pos)
        if chosen is act_del:
            self._remove_channel_edge(edge)

    def show_missing_menu(self, miss: MissingEdge, global_pos) -> None:  # type: ignore[no-untyped-def]
        miss.setSelected(True)
        menu = QMenu(self)
        act_fix = menu.addAction(t("补上连线（写入 dataflow）"))
        act_ignore = menu.addAction(t("忽略此建议（不再显示）"))
        act_drop = menu.addAction(t("移除目标 In 端口（不再需要该输入）"))
        chosen = menu.exec(global_pos)
        if chosen is act_fix:
            self.fix_missing_edge(miss)
        elif chosen is act_ignore:
            self.ignore_missing_edge(miss)
        elif chosen is act_drop:
            self.drop_missing_require(miss)

    def fix_missing_edge(self, miss: MissingEdge) -> None:
        if not self._session:
            return
        ok = self._session.add_dataflow(
            miss.src.process_name,
            miss.service,
            miss.dst.process_name,
        )
        if not ok:
            QMessageBox.information(self, t("补线"), t("该 dataflow 已存在"))
            return
        self.rebuild()
        self.changed.emit()

    def ignore_missing_edge(self, miss: MissingEdge) -> None:
        """Suppress a suggested provider→consumer pair (require may already be met via another hop)."""
        if not self._session:
            return
        key = (
            f"{miss.src.process_name}|{short_service(miss.service)}|{miss.dst.process_name}"
        )
        ui = self._session.node_ui(miss.dst.process_name)
        ignored = list(ui.get("ignore_missing") or [])
        if key not in ignored:
            ignored.append(key)
        self._session.set_node_ui(miss.dst.process_name, ignore_missing=ignored)
        self.rebuild()
        self.changed.emit()

    def drop_missing_require(self, miss: MissingEdge) -> None:
        """Remove the In port that caused the unsatisfied/suggested missing edge."""
        if not self._session:
            return
        dst = miss.dst.process_name
        svc = short_service(miss.service)
        card = self._nodes.get(dst)
        if not card:
            return
        new_req = [r for r in card.requires if short_service(r) != svc]
        self._session.set_ports(dst, list(card.provides), new_req)
        self.rebuild()
        self.changed.emit()

    def _focus_edge(self, edge: EdgeCurve, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            edge.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(
                highlight=(e is edge),
                dimmed=(e is not edge),
                role="",
            )
        for e in self._channel_edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for m in self._missing:
            m.set_visual_state(highlight=False, dimmed=True)
        for card in self._nodes.values():
            hit = card is edge.src or card is edge.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        # 确保品红路径点出现（选中态 + 已入 scene）
        if _qt_alive(edge):
            edge.update_path()
        if edge in self._edges:
            idx = self._edges.index(edge)
            self._flow_list.blockSignals(True)
            self._flow_list.setCurrentRow(idx)
            self._flow_list.blockSignals(False)
        if center:
            self._view.centerOn(edge)

    def _focus_channel_edge(
        self, edge: ChannelEdge, *, select: bool = True, center: bool = True
    ) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            edge.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for e in self._channel_edges:
            e.set_visual_state(
                highlight=(e is edge),
                dimmed=(e is not edge),
                role="",
            )
        for m in self._missing:
            m.set_visual_state(highlight=False, dimmed=True)
        for card in self._nodes.values():
            hit = card is edge.src or card is edge.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        if edge in self._channel_edges:
            idx = len(self._edges) + self._channel_edges.index(edge)
            self._flow_list.blockSignals(True)
            self._flow_list.setCurrentRow(idx)
            self._flow_list.blockSignals(False)
        if center:
            self._view.centerOn(edge)

    def _focus_missing(self, miss: MissingEdge, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            miss.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(highlight=False, dimmed=True)
        for e in self._channel_edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for m in self._missing:
            m.set_visual_state(highlight=(m is miss), dimmed=(m is not miss))
        for card in self._nodes.values():
            hit = card is miss.src or card is miss.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        if miss in self._missing:
            for i in range(self._flow_list.count()):
                it = self._flow_list.item(i)
                if it is None:
                    continue
                data = it.data(Qt.ItemDataRole.UserRole)
                if data and data[0] == "missing" and data[1] == self._missing.index(miss):
                    self._flow_list.blockSignals(True)
                    self._flow_list.setCurrentRow(i)
                    self._flow_list.blockSignals(False)
                    break
        if center:
            self._view.centerOn(miss)

    def _focus_peer(self, peer: McuPeerLink, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            peer.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for e in self._channel_edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for m in self._missing:
            m.set_visual_state(highlight=False, dimmed=True)
        for p in self._peers:
            p.set_visual_state(highlight=(p is peer), dimmed=(p is not peer))
        for card in self._nodes.values():
            hit = card is peer.mcu or card is peer.gateway
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        if center:
            self._view.centerOn(peer)

    def show_peer_menu(self, peer: McuPeerLink, global_pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        act_focus_mcu = menu.addAction(t("Select MCU"))
        act_focus_gw = menu.addAction(t("Select gateway"))
        chosen = menu.exec(global_pos)
        if chosen is act_focus_mcu:
            self._scene.clearSelection()
            peer.mcu.setSelected(True)
        elif chosen is act_focus_gw:
            self._scene.clearSelection()
            peer.gateway.setSelected(True)

    @staticmethod
    def _fuzzy_match(query: str, *parts: str) -> bool:
        hay = " ".join(parts).lower()
        q = query.lower().strip()
        if not q:
            return True
        if q in hay:
            return True
        # subsequence fuzzy: characters of query appear in order
        i = 0
        for ch in hay:
            if i < len(q) and ch == q[i]:
                i += 1
        if i == len(q):
            return True
        return all(tok in hay for tok in q.split())

    def _on_search_text(self, text: str) -> None:
        self._search_hits.clear()
        q = text.strip()
        if not q:
            self._search_hits.setVisible(False)
            return
        hits: list[tuple[str, str, int]] = []  # label, kind, index
        for i, e in enumerate(self._edges):
            if self._fuzzy_match(
                q, short_service(e.service), e.src.process_name, e.dst.process_name, e.service
            ):
                hits.append(
                    (
                        f"{short_service(e.service)}:  {e.src.process_name}  →  {e.dst.process_name}",
                        "edge",
                        i,
                    )
                )
        for i, e in enumerate(self._channel_edges):
            if self._fuzzy_match(
                q, e.slot, e.src.process_name, e.dst.process_name
            ):
                hits.append(
                    (
                        f"[GfChannel] {e.slot}:  {e.src.process_name}  →  {e.dst.process_name}",
                        "channel",
                        i,
                    )
                )
        for i, m in enumerate(self._missing):
            if self._fuzzy_match(
                q, short_service(m.service), m.src.process_name, m.dst.process_name, m.service
            ):
                hits.append(
                    (
                        f"[缺失] {short_service(m.service)}:  {m.src.process_name}  →  {m.dst.process_name}",
                        "missing",
                        i,
                    )
                )
        if not hits:
            item = QListWidgetItem("（无匹配）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._search_hits.addItem(item)
        else:
            for label, kind, idx in hits[:50]:
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, (kind, idx))
                self._search_hits.addItem(item)
        self._search_hits.setVisible(True)

    def _on_search_hit_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, idx = data
        if kind == "edge" and 0 <= idx < len(self._edges):
            self._focus_edge(self._edges[idx])
        elif kind == "channel" and 0 <= idx < len(self._channel_edges):
            self._focus_channel_edge(self._channel_edges[idx])
        elif kind == "missing" and 0 <= idx < len(self._missing):
            self._focus_missing(self._missing[idx])
        elif kind == "peer" and 0 <= idx < len(self._peers):
            self._focus_peer(self._peers[idx])

    def edit_edge(self, edge: EdgeCurve) -> None:
        if not self._session:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("编辑信号"))
        form = QFormLayout(dlg)
        form.addRow(t("源"), QLabel(edge.src.process_name))
        form.addRow(t("目的"), QLabel(edge.dst.process_name))
        svc = QLineEdit(edge.service)
        form.addRow("service", svc)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_svc = canon_service(svc.text())
        if not new_svc:
            return
        old_short = short_service(edge.service)
        frm = edge.src.process_name
        to = edge.dst.process_name
        flows = self._session.dataflows()
        for f in flows:
            if (
                str(f.get("from")) == frm
                and str(f.get("to")) == to
                and short_service(str(f.get("service") or "")) == old_short
            ):
                f["service"] = new_svc
        self._session.set_dataflows(flows)
        new_prov = [
            new_svc if short_service(p) == old_short else p for p in edge.src.provides
        ]
        new_req = [
            new_svc if short_service(r) == old_short else r for r in edge.dst.requires
        ]
        self._session.upsert_deployment(
            frm,
            provides=[canon_service(x) for x in new_prov],
            requires=[canon_service(x) for x in edge.src.requires],
        )
        self._session.upsert_deployment(
            to,
            provides=[canon_service(x) for x in edge.dst.provides],
            requires=[canon_service(x) for x in new_req],
        )
        self.rebuild()
        self.changed.emit()

    def _remove_edge(self, edge: EdgeCurve) -> None:
        if not self._session:
            return
        self._push_undo()
        target = edge.flow
        flows = self._session.dataflows()
        new_flows = [f for f in flows if f is not target]
        if len(new_flows) == len(flows):
            new_flows = [f for f in flows if f != target]
        self._session.set_dataflows(new_flows)
        self.rebuild()
        self.changed.emit()

    def _remove_channel_edge(self, edge: ChannelEdge) -> None:
        if not self._session:
            return
        self._push_undo()
        self._session.remove_channel_flow_match(
            edge.src.process_name,
            edge.dst.process_name,
            slot=edge.slot,
        )
        self.rebuild()
        self.changed.emit()

    def _delete_selection(self) -> None:
        channels = [i for i in self._scene.selectedItems() if isinstance(i, ChannelEdge)]
        if channels:
            self._remove_channel_edge(channels[0])
            return
        edges = [i for i in self._scene.selectedItems() if isinstance(i, EdgeCurve)]
        if edges:
            self._remove_edge(edges[0])
            return
        missing = [i for i in self._scene.selectedItems() if isinstance(i, MissingEdge)]
        if missing:
            self.ignore_missing_edge(missing[0])
            return
        cards = [i for i in self._scene.selectedItems() if isinstance(i, ProcessCard)]
        if cards:
            self.delete_node(cards[0])
            return
        row = self._flow_list.currentRow()
        item = self._flow_list.item(row) if row >= 0 else None
        if item is not None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data[0] == "edge" and 0 <= data[1] < len(self._edges):
                self._remove_edge(self._edges[data[1]])
                return
            if data and data[0] == "channel" and 0 <= data[1] < len(self._channel_edges):
                self._remove_channel_edge(self._channel_edges[data[1]])
                return
            if data and data[0] == "missing" and 0 <= data[1] < len(self._missing):
                self.ignore_missing_edge(self._missing[data[1]])
                return
        if 0 <= row < len(self._edges):
            self._remove_edge(self._edges[row])

    def show_card_menu(self, card: ProcessCard, global_pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        if card.is_external():
            act_del = menu.addAction(t("Delete external MCU"))
            chosen = menu.exec(global_pos)
            if chosen is act_del:
                self.delete_node(card)
            return
        if card.is_frame_ingest():
            act_edit = menu.addAction(t("编辑 frame_ingest…"))
            act_del = menu.addAction(t("删除 frame_ingest"))
            chosen = menu.exec(global_pos)
            if chosen is act_edit:
                self.edit_frame_ingest(card)
            elif chosen is act_del:
                self.delete_node(card)
            return
        act_edit = menu.addAction(t("编辑端口…"))
        act_import = menu.addAction(t("从此模块导入 hpp…"))
        menu.addSeparator()
        act_del = menu.addAction(t("删除模块"))
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_ports(card)
        elif chosen is act_import:
            self.import_hpp(default_process=card.process_name)
        elif chosen is act_del:
            self.delete_node(card)

    def set_single_port_side(self, port: PortItem, side: str) -> None:
        """Move one Out/In port (e.g. EgoMotion only) to another card edge."""
        # Append to end of that side's unified Out+In ladder.
        card = port.card
        side_n = _norm_side(side, port.side)
        peers = self._ports_on_side_unified(card, side_n, exclude=port)
        self.apply_port_side_and_order(port, side_n, len(peers))

    def add_node(self) -> None:
        if not self._session:
            return
        dlg = AddNodeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, domain = dlg.values()
        if not name:
            return
        if name in self._nodes:
            QMessageBox.warning(self, t("添加模块"), t("已存在：{name}").format(name=name))
            return
        self._push_undo()
        self._session.upsert_deployment(name, compute_domain=domain, provides=[], requires=[])
        self.rebuild(fit_view=True)
        self.changed.emit()

    def add_frame_ingest(self) -> None:
        """Add optional host.frame_ingest canvas node (not a deployment)."""
        if not self._session:
            return
        name = ProjectSession.FRAME_INGEST_PROCESS
        if name in self._nodes or any(
            c.is_frame_ingest() for c in self._nodes.values() if _qt_alive(c)
        ):
            QMessageBox.information(
                self,
                t("frame_ingest"),
                t("已存在视频契约节点。请双击 {name} 编辑。").format(name=name),
            )
            self.edit_frame_ingest(self._nodes.get(name))
            return
        fi = dict(self._session.frame_ingest_cfg())
        slots = list(self._session.camera_slots())
        if not slots:
            slots = [{"id": "front", "w": 640, "h": 480}]
        if str(fi.get("active_source") or "none") == "none":
            fi = {**fi, "active_source": "isp"}
        dlg = FrameIngestDialog(
            fi,
            slots,
            parent=self,
            channel_policies=self._session.publish_policy_channels(),
            channel_names=self._session.channel_policy_names(),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._push_undo()
        fields, new_slots = dlg.result_config()
        self._apply_frame_ingest(fields, new_slots, seed_fcm=True)
        self._session.apply_channel_publish_policies(dlg.result_channel_policies())
        self.rebuild(fit_view=True)
        self.changed.emit()

    def edit_frame_ingest(self, card: ProcessCard | None = None) -> None:
        if not self._session:
            return
        fi = dict(self._session.frame_ingest_cfg())
        slots = list(self._session.camera_slots())
        dlg = FrameIngestDialog(
            fi,
            slots,
            parent=self,
            channel_policies=self._session.publish_policy_channels(),
            channel_names=self._session.channel_policy_names(),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._push_undo()
        fields, new_slots = dlg.result_config()
        self._apply_frame_ingest(fields, new_slots, seed_fcm=False)
        self._session.apply_channel_publish_policies(dlg.result_channel_policies())
        self.rebuild()
        self.changed.emit()

    def _apply_frame_ingest(
        self,
        fields: dict[str, Any],
        slots: list[dict[str, Any]],
        *,
        seed_fcm: bool,
    ) -> None:
        assert self._session is not None
        self._session.migrate_legacy_camera_channel_flows()
        old_ids = {str(s.get("id")) for s in self._session.camera_slots()}
        new_ids = {str(s.get("id")) for s in slots if str(s.get("id") or "").strip()}
        # Preserve SIL paths / camera_transport from prior req
        prev = self._session.frame_ingest_cfg()
        merged = dict(prev)
        merged.update(fields)
        if isinstance(prev.get("paths"), dict) and "paths" not in fields:
            merged["paths"] = prev["paths"]
        legacy_transport = prev.get("camera_transport")
        if legacy_transport and "camera_transport" not in fields:
            merged["camera_transport"] = legacy_transport
        for k, v in merged.items():
            if k == "camera_slots":
                continue
            self._session.update_frame_ingest(**{k: v})
        self._session.set_camera_slots(slots)
        # Drop channel_flows for removed lane ids
        for sid in old_ids - new_ids:
            slot = ProjectSession.gf_channel_slot_name(sid)
            for fl in list(self._session.channel_flows()):
                if str(fl.get("slot") or "") == slot:
                    self._session.remove_channel_flow_match(
                        str(fl.get("from") or ""),
                        str(fl.get("to") or ""),
                        slot=slot,
                    )
        name = ProjectSession.FRAME_INGEST_PROCESS
        ui = self._session.node_ui(name)
        x = float(ui["x"]) if "x" in ui else -80.0
        y = float(ui["y"]) if "y" in ui else -320.0
        # Preserve authored out_side / port_sides / slot order when editing slots.
        fields_ui: dict[str, Any] = {
            "kind": "frame_ingest",
            "label": str(ui.get("label") or "frame_ingest"),
            "x": x,
            "y": y,
        }
        if "out_side" not in ui:
            fields_ui["out_side"] = "right"
        if "in_side" not in ui:
            fields_ui["in_side"] = "left"
        self._session.set_node_ui(name, **fields_ui)
        self._layout_pos[name] = (x, y)
        if seed_fcm and not self._session.channel_flows():
            self._session.seed_default_channel_flows()

    def add_external_mcu_node(self) -> None:
        """Add external MCU boundary node (VehicleBus / Trajectory via gateway)."""
        if not self._session:
            return
        if not self._show_external_mcu():
            QMessageBox.information(
                self,
                t("外部 MCU"),
                t(
                    "当前拓扑为「仅 AP（无 MCU）」，不显示 MCU 节点。\n"
                    "请先在 SKU 将拓扑改为「AP + MCU CP」。\n"
                    "对外控制信号（如 VehicleBus / Trajectory）可直接挂在 gateway 等模块端口上。"
                ),
            )
            return
        name = "external.vehicle_mcu"
        if name in self._nodes:
            QMessageBox.information(self, t("外部节点"), t("已存在：{name}").format(name=name))
            return
        self._push_undo()
        self._session.upsert_deployment(
            name,
            compute_domain="external",
            provides=["services.semantic.VehicleBus"],
            requires=["services.semantic.Trajectory"],
        )
        self._session.set_node_ui(
            name,
            kind="external",
            label="MCU",
            out_side="right",
            in_side="left",
            x=-280.0,
            y=120.0,
        )
        # link to gateway if present
        gw = "adapter.vehicle_can_gateway"
        deps = {str(d.get("process")) for d in self._session.deployments()}
        if gw in deps:
            self._session.add_dataflow(name, "services.semantic.VehicleBus", gw)
            self._session.add_dataflow(gw, "services.semantic.Trajectory", name)
            # ensure gateway ports
            for d in self._session.deployments():
                if str(d.get("process")) != gw:
                    continue
                prov = [str(x) for x in (d.get("provides") or [])]
                req = [str(x) for x in (d.get("requires") or [])]
                if not any(short_service(x) == "Trajectory" for x in prov):
                    prov.append("services.semantic.Trajectory")
                if not any(short_service(x) == "VehicleBus" for x in req):
                    req.append("services.semantic.VehicleBus")
                if not any(short_service(x) == "Trajectory" for x in req):
                    req.append("services.semantic.Trajectory")
                self._session.set_ports(gw, prov, req)
                break
        self.rebuild(fit_view=True)
        self.changed.emit()
        QMessageBox.information(self, t("external MCU"), t("已添加 {name}").format(name=name))

    def flush_canvas(self) -> None:
        """Persist node positions / sides into wiring.canvas before save.

        Only write fields the card owns. ``set_node_ui`` skips None (never deletes).
        """
        if not self._session:
            return
        for name, card in self._nodes.items():
            if not _qt_alive(card):
                continue
            p = card.pos()
            fields: dict[str, Any] = {
                "x": round(p.x(), 1),
                "y": round(p.y(), 1),
                "out_side": card.out_side,
                "in_side": card.in_side,
            }
            if card.port_sides:
                fields["port_sides"] = dict(card.port_sides)
            if card.port_slot_order:
                fields["port_slot_order"] = {
                    s: list(keys) for s, keys in card.port_slot_order.items()
                }
            if card.kind and card.kind != "process":
                fields["kind"] = card.kind
            if card.label:
                fields["label"] = card.label
            self._session.set_node_ui(name, **fields)

    def delete_node(self, card: ProcessCard) -> None:
        if not self._session:
            return
        if card.is_frame_ingest():
            reply = QMessageBox.question(
                self,
                t("删除 frame_ingest"),
                t(
                    "删除视频契约节点？\n"
                    "将清空 camera_slots / channel_flows，并把 active_source 设为 none。"
                ),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._push_undo()
            self._session.remove_frame_ingest_node()
            self.rebuild()
            self.changed.emit()
            return
        reply = QMessageBox.question(
            self,
            t("删除模块"),
            t("删除 {name} 及其相关 dataflows？").format(name=card.process_name),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._push_undo()
        # Also drop GfChannel edges into this process
        for fl in list(self._session.channel_flows()):
            if str(fl.get("to")) == card.process_name or str(fl.get("from")) == card.process_name:
                self._session.remove_channel_flow_match(
                    str(fl.get("from") or ""),
                    str(fl.get("to") or ""),
                    slot=str(fl.get("slot") or ""),
                )
        self._session.remove_deployment(card.process_name)
        self.rebuild()
        self.changed.emit()

    def _port_candidates(self, process: str) -> list[str]:
        if not self._session:
            return []
        names: list[str] = []
        hpp = self._session.module_hpp_for_process(process)
        if hpp:
            try:
                names.extend(self._session.parse_hpp_candidates(hpp))
            except Exception:  # noqa: BLE001
                pass
        # also common services already in graph
        for card in self._nodes.values():
            for s in card.provides + card.requires:
                short = short_service(s)
                if short and short not in names:
                    names.append(short)
        return names

    def edit_ports(self, card: ProcessCard) -> None:
        if not self._session:
            return
        if card.is_external():
            QMessageBox.information(
                self,
                t("external MCU"),
                t("画布上无端口可编辑（边界节点仅连 gateway）。"),
            )
            return
        if card.is_frame_ingest():
            self.edit_frame_ingest(card)
            return
        soa_prov = [p for p in card.provides if not is_channel_svc(p)]
        soa_req = [r for r in card.requires if not is_channel_svc(r)]
        dlg = PortEditDialog(
            card.process_name,
            soa_prov,
            soa_req,
            self._port_candidates(card.process_name),
            self,
            out_policies=self._session.publish_policy_services(),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._push_undo()
        provides, requires = dlg.result_ports()
        self._session.set_ports(card.process_name, provides, requires)
        self._session.apply_out_publish_policies(dlg.result_out_policies())
        self._session.prune_orphan_publish_policies()
        self.rebuild()
        self.changed.emit()

    def import_hpp(self, default_process: str = "") -> None:
        if not self._session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("选择头文件"),
            str(self._session.paths.project_dir),
            "C/C++ Headers (*.hpp *.h);;All (*)",
        )
        if not path:
            return
        hpp_path = Path(path)
        try:
            candidates = self._session.parse_hpp_candidates(hpp_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("解析失败"), str(exc))
            return
        if not candidates:
            QMessageBox.information(self, t("导入"), t("未解析到 struct，请检查头文件格式"))
            return
        self._apply_import_candidates(
            candidates,
            default_process,
            source_path=hpp_path,
            kind="hpp",
            title=t("从头文件添加端口"),
            hint=t("勾选要加入的类型（作为 service 短名）："),
        )

    def import_fidl(self, default_process: str = "") -> None:
        if not self._session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("选择 FIDL"),
            str(self._session.paths.project_dir),
            "Franca IDL (*.fidl);;All (*)",
        )
        if not path:
            return
        fidl_path = Path(path)
        try:
            candidates = self._session.parse_fidl_candidates(fidl_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("解析失败"), str(exc))
            return
        if not candidates:
            QMessageBox.information(
                self,
                t("导入"),
                t("未解析到 interface/struct/method/broadcast，请检查 .fidl 格式"),
            )
            return
        self._apply_import_candidates(
            candidates,
            default_process,
            source_path=fidl_path,
            kind="fidl",
            title=t("从 FIDL 添加端口"),
            hint=t("勾选要加入的名称（struct / broadcast / method / interface）："),
        )

    def _apply_import_candidates(
        self,
        candidates: list[str],
        default_process: str,
        *,
        source_path: Path,
        kind: str,
        title: str,
        hint: str,
    ) -> None:
        assert self._session is not None
        procs = sorted(self._nodes.keys())
        if not procs:
            QMessageBox.information(self, t("导入"), t("请先添加至少一个模块"))
            return
        default = default_process if default_process in procs else procs[0]
        dlg = ImportPortsDialog(
            candidates, procs, default, self, title=title, hint=hint
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        process, names, direction = dlg.selected()
        if not names:
            return

        rel = self._session.relpath_from_repo(source_path)
        if kind == "fidl":
            self._session.upsert_module(process, fidl_rel=rel)
        else:
            self._session.upsert_module(process, rel)

        card = self._nodes.get(process)
        provides = list(card.provides) if card else []
        requires = list(card.requires) if card else []
        for n in names:
            svc = canon_service(n)
            if direction == "out":
                if short_service(svc) not in {short_service(x) for x in provides}:
                    provides.append(svc)
            else:
                if short_service(svc) not in {short_service(x) for x in requires}:
                    requires.append(svc)
        self._session.set_ports(process, provides, requires)
        self.rebuild()
        self.changed.emit()
        QMessageBox.information(
            self,
            t("导入完成"),
            t(
                "已关联 {rel}\n向 {process} 添加了 {n} 个{direction} 端口。\n"
                "可双击模块继续调整，再从 Out 拖到 In 连线。"
            ).format(rel=rel, process=process, n=len(names), direction=direction),
        )

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

    def _highlight_list_edge(self, row: int) -> None:
        if row < 0:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            self._scene.blockSignals(False)
            self._clear_visual_emphasis()
            return
        item = self._flow_list.item(row)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            # legacy fallback for solid edges only
            if row < len(self._edges):
                self._focus_edge(self._edges[row])
            return
        kind, idx = data
        if kind == "edge" and 0 <= idx < len(self._edges):
            self._focus_edge(self._edges[idx])
        elif kind == "channel" and 0 <= idx < len(self._channel_edges):
            self._focus_channel_edge(self._channel_edges[idx])
        elif kind == "missing" and 0 <= idx < len(self._missing):
            self._focus_missing(self._missing[idx])
        elif kind == "peer" and 0 <= idx < len(self._peers):
            self._focus_peer(self._peers[idx])

# ProcessCard / PortItem refer to WiringGraphView via from __future__ annotations
