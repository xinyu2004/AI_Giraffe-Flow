"""Zoomable graphics view for the wiring canvas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from gf_config.gui.wiring_graph_items import (
    EdgeCurve,
    MissingEdge,
    McuPeerLink,
    PortItem,
    ProcessCard,
)

if TYPE_CHECKING:
    from gf_config.gui.wiring_graph import WiringGraphView

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


