"""Signal-link graph: Simulink-style ports, drag-wire, context menus, hpp import."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import shiboken6
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QShortcut,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
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
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gf_config.core import ProjectSession, canon_service, short_service


def _qt_alive(obj: Any) -> bool:
    """True if the wrapped C++ QObject/QGraphicsItem still exists."""
    try:
        return obj is not None and shiboken6.isValid(obj)
    except Exception:  # noqa: BLE001
        return False

SERVICE_COLORS: dict[str, str] = {
    "EgoMotion": "#5dade2",
    "UssZones": "#58d68d",
    "FrontObjectList": "#f5b041",
    "Trajectory": "#af7ac5",
    "VehicleModeStatus": "#76d7c4",
    "SurroundWorld": "#85c1e9",
    "ParkingWorld": "#f1948a",
    "DrivingObjectList": "#f7dc6f",
    "ActuatorCommand": "#e59866",
    "EgoMotionExtended": "#aed6f1",
}


def service_color(svc: str) -> QColor:
    return QColor(SERVICE_COLORS.get(short_service(svc), "#aab7b8"))


def role_of(process: str) -> str:
    if process.startswith("adapter."):
        return "Adapter"
    if process.startswith(("sensing.", "perception.", "planning.")):
        return "SOA App"
    if "mcu" in process:
        return "MCU / CP"
    return "Process"


def _qpoint(x: float, y: float) -> QPointF:
    return QPointF(x, y)


def cubic_bezier_point(p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF, t: float) -> QPointF:
    u = 1.0 - t
    return _qpoint(
        u**3 * p0.x() + 3 * u**2 * t * p1.x() + 3 * u * t**2 * p2.x() + t**3 * p3.x(),
        u**3 * p0.y() + 3 * u**2 * t * p1.y() + 3 * u * t**2 * p2.y() + t**3 * p3.y(),
    )


def cubic_bezier_tangent(p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF, t: float) -> QPointF:
    u = 1.0 - t
    return _qpoint(
        3 * u**2 * (p1.x() - p0.x()) + 6 * u * t * (p2.x() - p1.x()) + 3 * t**2 * (p3.x() - p2.x()),
        3 * u**2 * (p1.y() - p0.y()) + 6 * u * t * (p2.y() - p1.y()) + 3 * t**2 * (p3.y() - p2.y()),
    )


def append_chevron(path: QPainterPath, tip: QPointF, ux: float, uy: float, *, arrow_len: float = 10.0, arrow_w: float = 5.0) -> None:
    """Open chevron arrow at tip, oriented by unit direction (ux, uy)."""
    px, py = -uy, ux
    base = QPointF(tip.x() - ux * arrow_len, tip.y() - uy * arrow_len)
    path.moveTo(tip)
    path.lineTo(QPointF(base.x() + px * arrow_w, base.y() + py * arrow_w))
    path.moveTo(tip)
    path.lineTo(QPointF(base.x() - px * arrow_w, base.y() - py * arrow_w))


class PortItem(QGraphicsEllipseItem):
    """Inport (left) / Outport (right) — drag from Out to In like Simulink."""

    SIZE = 11.0

    def __init__(
        self,
        card: ProcessCard,
        direction: str,
        service: str,
        index: int,
    ) -> None:
        s = self.SIZE
        super().__init__(-s / 2, -s / 2, s, s)
        self.card = card
        self.direction = direction  # "in" | "out"
        self.service = service
        self.index = index
        self.setParentItem(card)
        self.setZValue(5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        self.setCursor(
            Qt.CursorShape.CrossCursor
            if direction == "out"
            else Qt.CursorShape.PointingHandCursor
        )
        self._apply_brush()

    def _apply_brush(self) -> None:
        if self.direction == "out":
            fill = QColor("#58d68d")
            border = QColor("#d5f5e3")
        else:
            fill = QColor("#f5b041")
            border = QColor("#fdebd0")
        self.setBrush(QBrush(fill))
        self.setPen(QPen(border, 1.5))

    def scene_center(self) -> QPointF:
        return self.sceneBoundingRect().center()

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.direction == "out"
            and self.card.graph is not None
        ):
            self.card.graph.begin_wire(self)
            event.accept()
            return
        super().mousePressEvent(event)


class ProcessCard(QGraphicsItem):
    WIDTH = 200
    LINE = 16
    HEADER = 44

    def __init__(
        self,
        name: str,
        provides: list[str],
        requires: list[str],
        x: float,
        y: float,
        graph: WiringGraphView | None = None,
    ) -> None:
        super().__init__()
        self.process_name = name
        self.provides = list(provides)
        self.requires = list(requires)
        self.graph = graph
        self._edges: list[EdgeCurve | MissingEdge] = []
        self._out_ports: list[PortItem] = []
        self._in_ports: list[PortItem] = []
        self._emphasis = False
        self._dimmed = False
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._height = self._compute_height()
        self._rebuild_ports()

    def set_ports(self, provides: list[str], requires: list[str]) -> None:
        self.provides = list(provides)
        self.requires = list(requires)
        self._height = self._compute_height()
        self._rebuild_ports()
        self.prepareGeometryChange()
        self.update()
        for e in self._edges:
            e.update_path()

    def _compute_height(self) -> float:
        n = 1 + max(len(self.provides), 1) + 1 + max(len(self.requires), 1)
        return self.HEADER + n * self.LINE + 12

    def _rebuild_ports(self) -> None:
        for p in self._out_ports + self._in_ports:
            if p.scene():
                p.scene().removeItem(p)
            else:
                p.setParentItem(None)
        self._out_ports.clear()
        self._in_ports.clear()

        y = self.HEADER
        y += self.LINE  # "Out / provides" label row
        if self.provides:
            for i, svc in enumerate(self.provides):
                port = PortItem(self, "out", svc, i)
                port.setPos(self.WIDTH, y + self.LINE / 2)
                self._out_ports.append(port)
                y += self.LINE
        else:
            y += self.LINE

        y += self.LINE  # "In / requires" label
        if self.requires:
            for i, svc in enumerate(self.requires):
                port = PortItem(self, "in", svc, i)
                port.setPos(0, y + self.LINE / 2)
                self._in_ports.append(port)
                y += self.LINE

    def out_port_for_service(self, service: str) -> PortItem | None:
        key = short_service(service)
        for p in self._out_ports:
            if short_service(p.service) == key:
                return p
        return self._out_ports[0] if self._out_ports else None

    def in_port_for_service(self, service: str) -> PortItem | None:
        key = short_service(service)
        for p in self._in_ports:
            if short_service(p.service) == key:
                return p
        return self._in_ports[0] if self._in_ports else None

    def out_anchor(self, service: str) -> QPointF:
        port = self.out_port_for_service(service)
        if port:
            return port.scene_center()
        return self.scenePos() + QPointF(self.WIDTH, self._height / 2)

    def in_anchor(self, service: str) -> QPointF:
        port = self.in_port_for_service(service)
        if port:
            return port.scene_center()
        return self.scenePos() + QPointF(0, self._height / 2)

    def set_visual_state(self, *, emphasis: bool = False, dimmed: bool = False) -> None:
        self._emphasis = emphasis
        self._dimmed = dimmed
        if _qt_alive(self):
            self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-8, -4, self.WIDTH + 16, self._height + 8)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:  # type: ignore[no-untyped-def]
        r = QRectF(0, 0, self.WIDTH, self._height)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._emphasis or self.isSelected():
            fill = QColor("#1e6b4f")
            border = QColor("#f7dc6f")
            border_w = 3.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(247, 220, 111, 50)))
            painter.drawRoundedRect(r.adjusted(-5, -5, 5, 5), 12, 12)
        elif self._dimmed:
            fill = QColor("#0f221c")
            border = QColor("#2c4a3e")
            border_w = 1.5
        else:
            fill = QColor("#15352c")
            border = QColor("#7dcea0")
            border_w = 2

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, border_w))
        painter.drawRoundedRect(r, 10, 10)

        title_c = QColor("#fff8dc") if (self._emphasis or self.isSelected()) else QColor("#eafaf1")
        if self._dimmed:
            title_c = QColor("#5d6d63")

        y = 8
        font_title = QFont()
        font_title.setPointSize(10)
        font_title.setBold(True)
        painter.setFont(font_title)
        painter.setPen(title_c)
        painter.drawText(
            QRectF(8, y, self.WIDTH - 16, 20),
            Qt.AlignmentFlag.AlignLeft,
            self.process_name,
        )
        y += 20

        font_small = QFont()
        font_small.setPointSize(8)
        painter.setFont(font_small)
        painter.setPen(QColor("#5d6d63") if self._dimmed else QColor("#7fb39a"))
        painter.drawText(8, y + 12, role_of(self.process_name))
        y = self.HEADER

        painter.setPen(QColor("#3d5c4a") if self._dimmed else QColor("#58d68d"))
        painter.drawText(8, y + 12, "Out (provides)")
        y += self.LINE
        painter.setPen(QColor("#3d5c4a") if self._dimmed else QColor("#d5f5e3"))
        if self.provides:
            for p in self.provides:
                painter.drawText(14, y + 12, short_service(p))
                y += self.LINE
        else:
            painter.setPen(QColor("#566573"))
            painter.drawText(14, y + 12, "(none)")
            y += self.LINE

        painter.setPen(QColor("#5c4a2c") if self._dimmed else QColor("#f5b041"))
        painter.drawText(8, y + 12, "In (requires)")
        y += self.LINE
        painter.setPen(QColor("#5c4a2c") if self._dimmed else QColor("#fdebd0"))
        if self.requires:
            for req in self.requires:
                painter.drawText(14, y + 12, short_service(req))
                y += self.LINE
        else:
            painter.setPen(QColor("#566573"))
            painter.drawText(14, y + 12, "(none)")

    def itemChange(self, change, value):  # type: ignore[no-untyped-def]
        if not _qt_alive(self):
            return value
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for e in self._edges:
                if _qt_alive(e):
                    e.update_path()
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.graph is not None:
            self.graph.edit_ports(self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.graph is not None:
            self.graph.show_card_menu(self, event.screenPos())
            event.accept()
            return
        super().contextMenuEvent(event)


class EdgeCurve(QGraphicsPathItem):
    def __init__(
        self,
        src: ProcessCard,
        dst: ProcessCard,
        service: str,
        flow: dict[str, Any],
        fan_index: int,
        fan_count: int,
        graph: WiringGraphView | None = None,
    ) -> None:
        super().__init__()
        self.src = src
        self.dst = dst
        self.service = service
        self.flow = flow
        self.fan_index = fan_index
        self.fan_count = fan_count
        self.graph = graph
        self._base_color = service_color(service)
        self._highlight = False
        self._dimmed = False
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        src._edges.append(self)
        dst._edges.append(self)

        self._label = QGraphicsSimpleTextItem(short_service(service))
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self._label.setFont(font)
        self._apply_style()
        self.update_path()

    def set_visual_state(self, *, highlight: bool = False, dimmed: bool = False) -> None:
        self._highlight = highlight
        self._dimmed = dimmed
        if not _qt_alive(self):
            return
        self._apply_style()
        self.update_path()

    def _apply_style(self) -> None:
        selected = self.isSelected()
        if self._highlight or selected:
            color = QColor("#f7dc6f")
            width = 3.0 if selected else 2.5
        elif self._dimmed:
            color = QColor(self._base_color)
            color.setAlpha(55)
            width = 1.2
        else:
            color = self._base_color
            width = 2.0
        self.setPen(QPen(color, width))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        lc = QColor("#fff8dc") if (self._highlight or selected) else self._base_color.lighter(130)
        if self._dimmed and not selected:
            lc.setAlpha(80)
        self._label.setBrush(QBrush(lc))

    def shape(self) -> QPainterPath:
        """Widen hit area so thin lines are easy to select."""
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        return stroker.createStroke(self.path())

    def update_path(self) -> None:
        p0 = self.src.out_anchor(self.service)
        p3 = self.dst.in_anchor(self.service)
        mid_span = max(40.0, abs(p3.x() - p0.x()) * 0.35)
        if self.fan_count > 1:
            spread = (self.fan_index - (self.fan_count - 1) / 2.0) * 28.0
        else:
            spread = 0.0
        p1 = QPointF(p0.x() + mid_span, p0.y() + spread)
        p2 = QPointF(p3.x() - mid_span, p3.y() + spread)

        path = QPainterPath(p0)
        path.cubicTo(p1, p2, p3)

        # label near mid; arrow further toward destination so they don't overlap
        label_pt = cubic_bezier_point(p0, p1, p2, p3, 0.42)
        tip = cubic_bezier_point(p0, p1, p2, p3, 0.68)
        tang = cubic_bezier_tangent(p0, p1, p2, p3, 0.68)
        length = math.hypot(tang.x(), tang.y()) or 1.0
        ux, uy = tang.x() / length, tang.y() / length
        append_chevron(path, tip, ux, uy)
        self.setPath(path)

        if self.scene() and self._label.scene() is None:
            self.scene().addItem(self._label)
        self._label.setText(short_service(self.service))
        self._label.setPos(label_pt.x() - 20, label_pt.y() - 18)
        self._label.setZValue(2 if (self._highlight or self.isSelected()) else 1)
        self.setZValue(1 if self.isSelected() else (0 if self._highlight else -1))

    def remove_label(self) -> None:
        if self._label.scene():
            self._label.scene().removeItem(self._label)

    def itemChange(self, change, value):  # type: ignore[no-untyped-def]
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._apply_style()
            self.update_path()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.graph is not None:
            self.graph.edit_edge(self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.graph is not None:
            self.graph.show_edge_menu(self, event.screenPos())
            event.accept()
            return
        super().contextMenuEvent(event)


class MissingEdge(QGraphicsPathItem):
    def __init__(
        self,
        src: ProcessCard,
        dst: ProcessCard,
        service: str,
        graph: WiringGraphView | None = None,
    ) -> None:
        super().__init__()
        self.src = src
        self.dst = dst
        self.service = service
        self.graph = graph
        self._dimmed = False
        self._highlight = False
        self.setZValue(-2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        src._edges.append(self)
        dst._edges.append(self)
        self._label = QGraphicsSimpleTextItem(f"? {short_service(service)}")
        self._label.setBrush(QBrush(QColor("#f5b7b1")))
        self._apply_style()
        self.update_path()

    def _apply_style(self) -> None:
        selected = self.isSelected()
        if self._highlight or selected:
            color = QColor("#f7dc6f")
            width = 3.0 if selected else 2.5
        elif self._dimmed:
            color = QColor("#e74c3c")
            color.setAlpha(50)
            width = 1.5
        else:
            color = QColor("#e74c3c")
            width = 2.0
        self.setPen(QPen(color, width, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        lc = QColor("#fff8dc") if (self._highlight or selected) else QColor("#f5b7b1")
        if self._dimmed and not selected:
            lc.setAlpha(80)
        self._label.setBrush(QBrush(lc))

    def set_visual_state(self, *, highlight: bool = False, dimmed: bool = False) -> None:
        self._highlight = highlight
        self._dimmed = dimmed
        if not _qt_alive(self):
            return
        self._apply_style()
        self.update_path()

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        return stroker.createStroke(self.path())

    def update_path(self) -> None:
        p0 = self.src.out_anchor(self.service)
        p3 = self.dst.in_anchor(self.service)
        ctrl = QPointF((p0.x() + p3.x()) / 2, (p0.y() + p3.y()) / 2 - 40)
        path = QPainterPath(p0)
        path.quadTo(ctrl, p3)

        def q_point(t: float) -> QPointF:
            u = 1.0 - t
            return QPointF(
                u * u * p0.x() + 2 * u * t * ctrl.x() + t * t * p3.x(),
                u * u * p0.y() + 2 * u * t * ctrl.y() + t * t * p3.y(),
            )

        def q_tang(t: float) -> QPointF:
            u = 1.0 - t
            return QPointF(
                2 * u * (ctrl.x() - p0.x()) + 2 * t * (p3.x() - ctrl.x()),
                2 * u * (ctrl.y() - p0.y()) + 2 * t * (p3.y() - ctrl.y()),
            )

        label_pt = q_point(0.42)
        tip = q_point(0.68)
        tang = q_tang(0.68)
        length = math.hypot(tang.x(), tang.y()) or 1.0
        ux, uy = tang.x() / length, tang.y() / length
        append_chevron(path, tip, ux, uy)
        self.setPath(path)
        if self.scene() and self._label.scene() is None:
            self.scene().addItem(self._label)
        self._label.setPos(label_pt.x() - 10, label_pt.y() - 16)
        self._label.setZValue(2 if (self._highlight or self.isSelected()) else 1)
        self.setZValue(1 if self.isSelected() else -2)

    def remove_label(self) -> None:
        if self._label.scene():
            self._label.scene().removeItem(self._label)

    def itemChange(self, change, value):  # type: ignore[no-untyped-def]
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._apply_style()
            self.update_path()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.graph is not None:
            self.graph.fix_missing_edge(self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.graph is not None:
            self.graph.show_missing_menu(self, event.screenPos())
            event.accept()
            return
        super().contextMenuEvent(event)


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
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._graph._on_view_context_menu)

    def remember_default_transform(self) -> None:
        self._default_transform = QTransform(self.transform())

    def reset_to_default_zoom(self) -> None:
        self.setTransform(QTransform(self._default_transform))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                return
            factor = 1.15 if delta > 0 else 1 / 1.15
            scale = self.transform().m11() * factor
            if 0.25 <= scale <= 4.0:
                self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._graph._wire_src is not None:
            self._graph.update_wire_preview(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._graph._wire_src is None and event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            cur: QGraphicsItem | None = item
            interactive = False
            while cur is not None:
                if isinstance(cur, (EdgeCurve, MissingEdge, PortItem, ProcessCard)):
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
        if self._graph._wire_src is not None and event.button() == Qt.MouseButton.LeftButton:
            self._graph.finish_wire(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self._graph._wire_src is None:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)


class PortEditDialog(QDialog):
    """Double-click block: add/remove In/Out ports (Simulink-like)."""

    def __init__(
        self,
        process: str,
        provides: list[str],
        requires: list[str],
        candidates: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"编辑端口 — {process}")
        self.resize(480, 420)

        self._provides = QListWidget()
        self._requires = QListWidget()
        for p in provides:
            self._provides.addItem(canon_service(p))
        for r in requires:
            self._requires.addItem(canon_service(r))

        self._svc = QComboBox()
        self._svc.setEditable(True)
        for c in candidates:
            self._svc.addItem(canon_service(c) if not c.startswith("services.") else c)
        if not candidates:
            self._svc.addItem("services.semantic.")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Out (provides) — 右侧端口"))
        layout.addWidget(self._provides)
        layout.addWidget(QLabel("In (requires) — 左侧端口"))
        layout.addWidget(self._requires)

        row = QHBoxLayout()
        row.addWidget(QLabel("service"))
        row.addWidget(self._svc, stretch=1)
        btn_out = QPushButton("＋ Out")
        btn_in = QPushButton("＋ In")
        btn_del = QPushButton("删除选中")
        btn_swap = QPushButton("切换方向")
        btn_out.clicked.connect(lambda: self._add("out"))
        btn_in.clicked.connect(lambda: self._add("in"))
        btn_del.clicked.connect(self._delete_selected)
        btn_swap.clicked.connect(self._swap_direction)
        row.addWidget(btn_out)
        row.addWidget(btn_in)
        row.addWidget(btn_del)
        row.addWidget(btn_swap)
        layout.addLayout(row)

        hint = QLabel("提示：也可从候选下拉选 hpp 解析出的类型名；手输短名会规范为 services.semantic.*")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:11px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add(self, direction: str) -> None:
        text = self._svc.currentText().strip()
        if not text:
            return
        svc = canon_service(text)
        lst = self._provides if direction == "out" else self._requires
        existing = {lst.item(i).text() for i in range(lst.count())}
        if svc in existing or short_service(svc) in {short_service(x) for x in existing}:
            return
        lst.addItem(svc)

    def _active_list(self) -> QListWidget | None:
        if self._provides.hasFocus() or self._provides.currentItem():
            if self._provides.currentRow() >= 0:
                return self._provides
        if self._requires.currentRow() >= 0:
            return self._requires
        if self._provides.currentRow() >= 0:
            return self._provides
        return None

    def _delete_selected(self) -> None:
        for lst in (self._provides, self._requires):
            row = lst.currentRow()
            if row >= 0 and lst.hasFocus():
                lst.takeItem(row)
                return
        for lst in (self._provides, self._requires):
            row = lst.currentRow()
            if row >= 0:
                lst.takeItem(row)
                return

    def _swap_direction(self) -> None:
        for src, dst in ((self._provides, self._requires), (self._requires, self._provides)):
            row = src.currentRow()
            if row >= 0:
                item = src.takeItem(row)
                if item:
                    dst.addItem(item.text())
                return

    def result_ports(self) -> tuple[list[str], list[str]]:
        provides = [self._provides.item(i).text() for i in range(self._provides.count())]
        requires = [self._requires.item(i).text() for i in range(self._requires.count())]
        return provides, requires


class ImportHppDialog(QDialog):
    def __init__(
        self,
        candidates: list[str],
        processes: list[str],
        default_process: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("从头文件添加端口")
        self.resize(420, 380)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("勾选要加入的类型（作为 service 短名）："))
        self._checks: list[QCheckBox] = []
        for name in candidates:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._checks.append(cb)
            layout.addWidget(cb)

        form = QFormLayout()
        self._proc = QComboBox()
        self._proc.addItems(processes)
        if default_process in processes:
            self._proc.setCurrentText(default_process)
        form.addRow("目标模块", self._proc)

        self._dir_out = QRadioButton("Out (provides)")
        self._dir_in = QRadioButton("In (requires)")
        self._dir_out.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._dir_out)
        bg.addButton(self._dir_in)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_out)
        dir_row.addWidget(self._dir_in)
        form.addRow("方向", dir_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self) -> tuple[str, list[str], str]:
        names = [cb.text() for cb in self._checks if cb.isChecked()]
        direction = "out" if self._dir_out.isChecked() else "in"
        return self._proc.currentText(), names, direction


class AddNodeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加模块")
        form = QFormLayout(self)
        self._name = QLineEdit("sensing.new_app")
        self._domain = QLineEdit("ap_linux")
        form.addRow("process", self._name)
        form.addRow("compute_domain", self._domain)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[str, str]:
        return self._name.text().strip(), self._domain.text().strip() or "ap_linux"


class WiringGraphView(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._nodes: dict[str, ProcessCard] = {}
        self._edges: list[EdgeCurve] = []
        self._missing: list[MissingEdge] = []
        self._wire_src: PortItem | None = None
        self._wire_line: QGraphicsLineItem | None = None

        self._scene = QGraphicsScene(self)
        self._view = ZoomGraphicsView(self._scene, self)
        self._scene.selectionChanged.connect(self._on_selection_changed)

        self._flow_list = QListWidget()
        self._flow_list.setMinimumWidth(340)
        self._flow_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索信号（模糊匹配名 / 进程）…")
        self._search.textChanged.connect(self._on_search_text)
        self._search_hits = QListWidget()
        self._search_hits.setMaximumHeight(140)
        self._search_hits.itemClicked.connect(self._on_search_hit_clicked)
        self._search_hits.setVisible(False)

        self._legend = QLabel(
            "类 Simulink：右键空白加模块 · 双击模块改端口 · 从右 Out 拖到左 In 连线\n"
            "单击信号线（含缺失虚线）可选中 · 搜索框可模糊定位\n"
            "连线以 Out 为准 · 箭头在线中段偏后 · Ctrl+滚轮 / Ctrl+H"
        )
        self._legend.setWordWrap(True)
        self._legend.setStyleSheet("color: #a9cfc0; font-size: 11px;")

        btn_row = QHBoxLayout()
        self._btn_remove = QPushButton("删除选中边")
        self._btn_remove.clicked.connect(self._remove_selected_flow)
        self._btn_import = QPushButton("导入 hpp/h…")
        self._btn_import.clicked.connect(self.import_hpp)
        self._btn_reload = QPushButton("重载图")
        self._btn_reload.clicked.connect(self.rebuild)
        self._btn_fit = QPushButton("适应窗口")
        self._btn_fit.clicked.connect(self._fit_and_remember)
        self._btn_reset = QPushButton("默认大小 (Ctrl+H)")
        self._btn_reset.clicked.connect(self.reset_zoom)
        for b in (
            self._btn_remove,
            self._btn_import,
            self._btn_reload,
            self._btn_fit,
            self._btn_reset,
        ):
            btn_row.addWidget(b)

        right = QVBoxLayout()
        right.addWidget(self._legend)
        right.addWidget(self._search)
        right.addWidget(self._search_hits)
        right.addWidget(QLabel("全部 dataflows"))
        right.addWidget(self._flow_list)
        right.addLayout(btn_row)

        layout = QHBoxLayout(self)
        layout.addWidget(self._view, stretch=3)
        layout.addLayout(right, stretch=1)

        self._flow_list.currentRowChanged.connect(self._highlight_list_edge)

        sc = QShortcut(QKeySequence("Ctrl+H"), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.reset_zoom)
        sc_del = QShortcut(QKeySequence.StandardKey.Delete, self)
        sc_del.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_del.activated.connect(self._delete_selection)
        sc_back = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        sc_back.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_back.activated.connect(self._delete_selection)

    def reset_zoom(self) -> None:
        self._view.reset_to_default_zoom()

    def set_session(self, session: ProjectSession | None) -> None:
        self._session = session
        self.rebuild()

    def _fit_and_remember(self) -> None:
        if not self._scene.items():
            return
        self._view.fitInView(
            self._scene.itemsBoundingRect().adjusted(-30, -30, 30, 30),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self._view.remember_default_transform()

    def _clear_visual_emphasis(self) -> None:
        for card in list(self._nodes.values()):
            if _qt_alive(card):
                card.set_visual_state(emphasis=False, dimmed=False)
        for e in list(self._edges):
            if _qt_alive(e):
                e.set_visual_state(highlight=False, dimmed=False)
        for m in list(self._missing):
            if _qt_alive(m):
                m.set_visual_state(highlight=False, dimmed=False)

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
        selected_cards = [
            i for i in self._scene.selectedItems() if isinstance(i, ProcessCard) and _qt_alive(i)
        ]

        if selected_missing and not selected_cards and not selected_edges:
            miss = selected_missing[0]
            self._focus_missing(miss, select=False, center=False)
            return

        if selected_edges and not selected_cards:
            edge = selected_edges[0]
            self._focus_edge(edge, select=False, center=False)
            return

        if not selected_cards:
            self._clear_visual_emphasis()
            return

        focus = selected_cards[0]
        connected: set[EdgeCurve] = set()
        neighbors: set[ProcessCard] = {focus}
        for e in self._edges:
            if e.src is focus or e.dst is focus:
                connected.add(e)
                neighbors.add(e.src)
                neighbors.add(e.dst)
        for m in self._missing:
            if m.src is focus or m.dst is focus:
                neighbors.add(m.src)
                neighbors.add(m.dst)

        for card in self._nodes.values():
            if card is focus:
                card.set_visual_state(emphasis=True, dimmed=False)
            elif card in neighbors:
                card.set_visual_state(emphasis=False, dimmed=False)
            else:
                card.set_visual_state(emphasis=False, dimmed=True)

        for e in self._edges:
            e.set_visual_state(highlight=(e in connected), dimmed=(e not in connected))

        for m in self._missing:
            hit = m.src is focus or m.dst is focus
            m.set_visual_state(highlight=hit, dimmed=not hit)

        if connected:
            first = next(e for e in self._edges if e in connected)
            idx = self._edges.index(first)
            self._flow_list.blockSignals(True)
            self._flow_list.setCurrentRow(idx)
            self._flow_list.blockSignals(False)

    # --- wiring drag ---

    def begin_wire(self, src_port: PortItem) -> None:
        self.cancel_wire()
        self._wire_src = src_port
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        line = QGraphicsLineItem()
        line.setPen(QPen(QColor("#f7dc6f"), 1.5, Qt.PenStyle.DashLine))
        line.setZValue(20)
        c = src_port.scene_center()
        line.setLine(c.x(), c.y(), c.x(), c.y())
        self._scene.addItem(line)
        self._wire_line = line

    def update_wire_preview(self, scene_pos: QPointF) -> None:
        if self._wire_src is None or self._wire_line is None:
            return
        c = self._wire_src.scene_center()
        self._wire_line.setLine(c.x(), c.y(), scene_pos.x(), scene_pos.y())

    def finish_wire(self, scene_pos: QPointF) -> None:
        src = self._wire_src
        self.cancel_wire()
        if src is None or not self._session:
            return
        item = self._scene.itemAt(scene_pos, self._view.transform())
        # walk up to PortItem
        target: PortItem | None = None
        cur: QGraphicsItem | None = item
        while cur is not None:
            if isinstance(cur, PortItem):
                target = cur
                break
            cur = cur.parentItem()
        if target is None or target.direction != "in":
            return
        if target.card is src.card:
            QMessageBox.information(self, "连线", "不能连到同一模块")
            return

        src_svc = canon_service(src.service)
        dst_svc = (target.service or "").strip()
        # Simulink-like: connection carries the source signal; In port name follows Out.
        if not dst_svc:
            new_req = list(target.card.requires) + [src_svc]
            self._session.set_ports(
                target.card.process_name, list(target.card.provides), new_req
            )
        elif short_service(dst_svc) != short_service(src_svc):
            new_req = [
                src_svc if short_service(r) == short_service(dst_svc) else r
                for r in target.card.requires
            ]
            self._session.set_ports(
                target.card.process_name, list(target.card.provides), new_req
            )

        ok = self._session.add_dataflow(
            src.card.process_name,
            src_svc,
            target.card.process_name,
        )
        if not ok:
            QMessageBox.information(self, "连线", "该 dataflow 已存在")
            return
        self.rebuild()
        self.changed.emit()

    def cancel_wire(self) -> None:
        self._wire_src = None
        if self._wire_line is not None:
            if self._wire_line.scene():
                self._scene.removeItem(self._wire_line)
            self._wire_line = None
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    # --- context menus / edit ---

    def _on_view_context_menu(self, pos) -> None:  # type: ignore[no-untyped-def]
        scene_pos = self._view.mapToScene(pos)
        item = self._scene.itemAt(scene_pos, self._view.transform())
        cur: QGraphicsItem | None = item
        while cur is not None:
            if isinstance(cur, EdgeCurve):
                self.show_edge_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, MissingEdge):
                self.show_missing_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, ProcessCard):
                self.show_card_menu(cur, self._view.mapToGlobal(pos))
                return
            cur = cur.parentItem()

        menu = QMenu(self)
        act_add = menu.addAction("添加模块…")
        act_import = menu.addAction("导入 hpp/h…")
        chosen = menu.exec(self._view.mapToGlobal(pos))
        if chosen is act_add:
            self.add_node()
        elif chosen is act_import:
            self.import_hpp()

    def show_edge_menu(self, edge: EdgeCurve, global_pos) -> None:  # type: ignore[no-untyped-def]
        edge.setSelected(True)
        menu = QMenu(self)
        act_edit = menu.addAction("编辑信号名…")
        act_del = menu.addAction("删除信号线")
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_edge(edge)
        elif chosen is act_del:
            self._remove_edge(edge)

    def show_missing_menu(self, miss: MissingEdge, global_pos) -> None:  # type: ignore[no-untyped-def]
        miss.setSelected(True)
        menu = QMenu(self)
        act_fix = menu.addAction("补上连线（写入 dataflow）")
        chosen = menu.exec(global_pos)
        if chosen is act_fix:
            self.fix_missing_edge(miss)

    def fix_missing_edge(self, miss: MissingEdge) -> None:
        if not self._session:
            return
        ok = self._session.add_dataflow(
            miss.src.process_name,
            miss.service,
            miss.dst.process_name,
        )
        if not ok:
            QMessageBox.information(self, "补线", "该 dataflow 已存在")
            return
        self.rebuild()
        self.changed.emit()

    def _focus_edge(self, edge: EdgeCurve, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            edge.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(highlight=(e is edge), dimmed=(e is not edge))
        for m in self._missing:
            m.set_visual_state(highlight=False, dimmed=True)
        for card in self._nodes.values():
            hit = card is edge.src or card is edge.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        if edge in self._edges:
            idx = self._edges.index(edge)
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
        for m in self._missing:
            m.set_visual_state(highlight=(m is miss), dimmed=(m is not miss))
        for card in self._nodes.values():
            hit = card is miss.src or card is miss.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        if miss in self._missing:
            row = len(self._edges) + self._missing.index(miss)
            self._flow_list.blockSignals(True)
            self._flow_list.setCurrentRow(row)
            self._flow_list.blockSignals(False)
        if center:
            self._view.centerOn(miss)

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
        elif kind == "missing" and 0 <= idx < len(self._missing):
            self._focus_missing(self._missing[idx])

    def edit_edge(self, edge: EdgeCurve) -> None:
        if not self._session:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("编辑信号")
        form = QFormLayout(dlg)
        form.addRow("from", QLabel(edge.src.process_name))
        form.addRow("to", QLabel(edge.dst.process_name))
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
        target = edge.flow
        flows = self._session.dataflows()
        new_flows = [f for f in flows if f is not target]
        if len(new_flows) == len(flows):
            new_flows = [f for f in flows if f != target]
        self._session.set_dataflows(new_flows)
        self.rebuild()
        self.changed.emit()

    def _delete_selection(self) -> None:
        edges = [i for i in self._scene.selectedItems() if isinstance(i, EdgeCurve)]
        if edges:
            self._remove_edge(edges[0])
            return
        cards = [i for i in self._scene.selectedItems() if isinstance(i, ProcessCard)]
        if cards:
            self.delete_node(cards[0])
            return
        row = self._flow_list.currentRow()
        if 0 <= row < len(self._edges):
            self._remove_edge(self._edges[row])

    def show_card_menu(self, card: ProcessCard, global_pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        act_edit = menu.addAction("编辑端口…")
        act_import = menu.addAction("从此模块导入 hpp…")
        menu.addSeparator()
        act_del = menu.addAction("删除模块")
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_ports(card)
        elif chosen is act_import:
            self.import_hpp(default_process=card.process_name)
        elif chosen is act_del:
            self.delete_node(card)

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
            QMessageBox.warning(self, "添加模块", f"已存在：{name}")
            return
        self._session.upsert_deployment(name, compute_domain=domain, provides=[], requires=[])
        self.rebuild()
        self.changed.emit()

    def delete_node(self, card: ProcessCard) -> None:
        if not self._session:
            return
        reply = QMessageBox.question(
            self,
            "删除模块",
            f"删除 {card.process_name} 及其相关 dataflows？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
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
        dlg = PortEditDialog(
            card.process_name,
            list(card.provides),
            list(card.requires),
            self._port_candidates(card.process_name),
            self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        provides, requires = dlg.result_ports()
        self._session.set_ports(card.process_name, provides, requires)
        self.rebuild()
        self.changed.emit()

    def import_hpp(self, default_process: str = "") -> None:
        if not self._session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择头文件",
            str(self._session.paths.project_dir),
            "C/C++ Headers (*.hpp *.h);;All (*)",
        )
        if not path:
            return
        hpp_path = Path(path)
        try:
            candidates = self._session.parse_hpp_candidates(hpp_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "解析失败", str(exc))
            return
        if not candidates:
            QMessageBox.information(self, "导入", "未解析到 struct，请检查头文件格式")
            return

        procs = sorted(self._nodes.keys())
        if not procs:
            QMessageBox.information(self, "导入", "请先添加至少一个模块")
            return
        default = default_process if default_process in procs else procs[0]
        dlg = ImportHppDialog(candidates, procs, default, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        process, names, direction = dlg.selected()
        if not names:
            return

        rel = self._session.relpath_from_repo(hpp_path)
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
            "导入完成",
            f"已关联 {rel}\n向 {process} 添加了 {len(names)} 个{direction} 端口。\n"
            "可双击模块继续调整，再从 Out 拖到 In 连线。",
        )

    def rebuild(self) -> None:
        self.cancel_wire()
        # Block selectionChanged while tearing down — scene.clear() deletes C++ items
        # while Python still briefly holds ProcessCard/EdgeCurve wrappers.
        self._scene.blockSignals(True)
        self._flow_list.blockSignals(True)
        try:
            for e in self._edges:
                if _qt_alive(e):
                    e.remove_label()
            for m in self._missing:
                if _qt_alive(m):
                    m.remove_label()
            self._nodes.clear()
            self._edges.clear()
            self._missing.clear()
            self._scene.clear()
            self._flow_list.clear()
        finally:
            self._scene.blockSignals(False)
            self._flow_list.blockSignals(False)

        if not self._session:
            return

        dep_map: dict[str, dict[str, Any]] = {}
        for d in self._session.deployments():
            p = d.get("process")
            if p:
                dep_map[str(p)] = d

        ordered = list(dep_map.keys())
        for fl in self._session.dataflows():
            for key in ("from", "to"):
                p = fl.get(key)
                if p and str(p) not in dep_map:
                    dep_map[str(p)] = {"process": p, "provides": [], "requires": []}
                    ordered.append(str(p))

        depths = self._compute_depths(ordered, self._session.dataflows())
        cols: dict[int, list[str]] = {}
        for name in ordered:
            cols.setdefault(depths.get(name, 0), []).append(name)

        for depth, names in sorted(cols.items()):
            for i, name in enumerate(names):
                d = dep_map.get(name) or {}
                provides = [str(x) for x in (d.get("provides") or [])]
                requires = [str(x) for x in (d.get("requires") or [])]
                x = 40 + depth * 280
                y = 40 + i * 240
                card = ProcessCard(name, provides, requires, x, y, graph=self)
                self._scene.addItem(card)
                self._nodes[name] = card

        flows = self._session.dataflows()
        outbound_count: dict[str, int] = {}
        outbound_seen: dict[str, int] = {}
        for fl in flows:
            src = str(fl.get("from") or "")
            outbound_count[src] = outbound_count.get(src, 0) + 1
        for fl in flows:
            src = str(fl.get("from") or "")
            dst = str(fl.get("to") or "")
            svc = str(fl.get("service") or "")
            src_n = self._nodes.get(src)
            dst_n = self._nodes.get(dst)
            if not src_n or not dst_n:
                continue
            idx = outbound_seen.get(src, 0)
            outbound_seen[src] = idx + 1
            edge = EdgeCurve(src_n, dst_n, svc, fl, idx, outbound_count.get(src, 1), graph=self)
            self._scene.addItem(edge)
            self._edges.append(edge)
            item = QListWidgetItem(f"{short_service(svc)}:  {src}  →  {dst}")
            item.setData(Qt.ItemDataRole.UserRole, ("edge", len(self._edges) - 1))
            self._flow_list.addItem(item)

        provided_by: dict[str, list[str]] = {}
        for name, card in self._nodes.items():
            for p in card.provides:
                provided_by.setdefault(short_service(p), []).append(name)

        for cons_name, card in self._nodes.items():
            for req in card.requires:
                svc_s = short_service(req)
                providers = provided_by.get(svc_s) or []
                for prov in providers:
                    has = any(
                        str(f.get("from")) == prov
                        and str(f.get("to")) == cons_name
                        and short_service(str(f.get("service") or "")) == svc_s
                        for f in flows
                    )
                    if has:
                        continue
                    src_n = self._nodes.get(prov)
                    if not src_n:
                        continue
                    miss = MissingEdge(src_n, card, req, graph=self)
                    self._scene.addItem(miss)
                    self._missing.append(miss)
                    mitem = QListWidgetItem(f"[缺失] {svc_s}:  {prov}  →  {cons_name}")
                    mitem.setData(Qt.ItemDataRole.UserRole, ("missing", len(self._missing) - 1))
                    self._flow_list.addItem(mitem)

        if self._search.text().strip():
            self._on_search_text(self._search.text())
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-60, -60, 60, 60))
        self._fit_and_remember()

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
        elif kind == "missing" and 0 <= idx < len(self._missing):
            self._focus_missing(self._missing[idx])

    def _remove_selected_flow(self) -> None:
        edges = [i for i in self._scene.selectedItems() if isinstance(i, EdgeCurve)]
        if edges:
            self._remove_edge(edges[0])
            return
        if not self._session:
            return
        row = self._flow_list.currentRow()
        if row < 0 or row >= len(self._edges):
            QMessageBox.information(
                self,
                "删除边",
                "请单击选中一条信号线，或在右侧列表选中后删除",
            )
            return
        self._remove_edge(self._edges[row])


# ProcessCard / PortItem refer to WiringGraphView via from __future__ annotations
