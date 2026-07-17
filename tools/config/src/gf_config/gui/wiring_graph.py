"""Signal-link graph: Simulink-style ports, drag-wire, context menus, hpp import."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import shiboken6
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt, Signal
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
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gf_codegen.compose.parse_hpp import is_fat_port_name
from gf_config.core import ProjectSession, canon_service, short_service
from gf_config.gui.lineage_view import LineageView


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
    "Perception_In_St": "#5dade2",
    "Perception_MESSAGE_Out_St": "#f5b041",
    "IPC_CanInfo_10ms_St": "#76d7c4",
    "IPC_CanInfo_20ms_St": "#76d7c4",
    "IPC_CanInfo_100ms_St": "#76d7c4",
    "IPC_ADC_Perception_Out_St": "#f1948a",
    "VehicleBus": "#c9a227",
}


def service_color(svc: str) -> QColor:
    return QColor(SERVICE_COLORS.get(short_service(svc), "#aab7b8"))


_PORT_SIDES = ("left", "right", "top", "bottom")
_SIDE_LABEL = {"left": "左", "right": "右", "top": "上", "bottom": "下"}


def is_external_node(*, kind: str = "", process: str = "") -> bool:
    return kind == "external" or process.startswith("external.")


def role_of(process: str, *, kind: str = "") -> str:
    if is_external_node(kind=kind, process=process):
        return "External · MCU/车身"
    if process.startswith("adapter."):
        return "Adapter"
    if process.startswith(("sensing.", "perception.", "planning.")):
        return "SOA App"
    if "mcu" in process:
        return "MCU / CP"
    return "Process"


def _norm_side(side: str | None, default: str) -> str:
    s = (side or default).strip().lower()
    return s if s in _PORT_SIDES else default


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
        self.setToolTip(f"{'Out' if direction == 'out' else 'In'}: {short_service(service)}")
        self._apply_brush()

    def _apply_brush(self) -> None:
        # 未连线=红；已连线 Out=绿 / In=橙
        selected = bool(self.card and (self.card.isSelected() or self.card._emphasis))
        linked = bool(self.card and self.card.is_port_linked(self.direction, self.service))
        if not linked:
            fill = QColor("#e74c3c") if selected else QColor("#c0392b")
            border = QColor("#ffffff") if selected else QColor("#f5b7b1")
            tip = "未连线"
        elif self.direction == "out":
            fill = QColor("#2ecc71") if selected else QColor("#58d68d")
            border = QColor("#ffffff") if selected else QColor("#abebc6")
            tip = "已连出"
        else:
            fill = QColor("#e67e22") if selected else QColor("#f39c12")
            border = QColor("#ffffff") if selected else QColor("#fdebd0")
            tip = "已连入"
        self.setBrush(QBrush(fill))
        self.setPen(QPen(border, 2.5 if selected else 1.5))
        self.setToolTip(
            f"{'Out' if self.direction == 'out' else 'In'}: "
            f"{short_service(self.service)}（{tip}）"
        )
        # In 用略扁椭圆区分形状
        s = self.SIZE
        if self.direction == "in":
            self.setRect(-s / 2, -s / 2 + 1, s, s - 2)
        else:
            self.setRect(-s / 2, -s / 2, s, s)

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
    # MCU/车身：相对原 EXT(150×78) → 宽×1.5、高×3
    EXT_WIDTH = 225
    EXT_HEIGHT = 234
    LINE = 16
    HEADER = 62  # title + role + domain

    def __init__(
        self,
        name: str,
        provides: list[str],
        requires: list[str],
        x: float,
        y: float,
        graph: WiringGraphView | None = None,
        *,
        out_side: str = "right",
        in_side: str = "left",
        kind: str = "process",
        label: str = "",
        compute_domain: str = "ap_linux",
    ) -> None:
        super().__init__()
        self.process_name = name
        self.provides = list(provides)
        self.requires = list(requires)
        self.graph = graph
        self.out_side = _norm_side(out_side, "right")
        self.in_side = _norm_side(in_side, "left")
        self.kind = kind or "process"
        self.label = label or ""
        self.compute_domain = compute_domain or "ap_linux"
        # 画布隐藏：仅与 MCU 边界相关的端口（yaml dataflow 仍保留）
        self._canvas_hide_out: set[str] = set()
        self._canvas_hide_in: set[str] = set()
        self._edges: list[Any] = []
        self._out_ports: list[PortItem] = []
        self._in_ports: list[PortItem] = []
        self._emphasis = False
        self._dimmed = False
        self._updating_links = False
        # 短服务名：已有 dataflow 的 Out / In
        self._linked_out: set[str] = set()
        self._linked_in: set[str] = set()
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._height = self._compute_height()
        self._rebuild_ports()

    def set_link_status(self, *, linked_out: set[str], linked_in: set[str]) -> None:
        """按 dataflow 标记端口是否已连；未连线文字/圆点为红。"""
        self._linked_out = {short_service(s) for s in linked_out}
        self._linked_in = {short_service(s) for s in linked_in}
        if _qt_alive(self):
            self.update()
            for p in self._out_ports + self._in_ports:
                if _qt_alive(p):
                    p._apply_brush()

    def is_port_linked(self, direction: str, service: str) -> bool:
        key = short_service(service)
        if direction == "out":
            return key in self._linked_out
        return key in self._linked_in

    def is_external(self) -> bool:
        return is_external_node(kind=self.kind, process=self.process_name)

    @property
    def card_width(self) -> float:
        return float(self.EXT_WIDTH if self.is_external() else self.WIDTH)

    def set_canvas_hide(
        self,
        *,
        out: set[str] | None = None,
        inn: set[str] | None = None,
    ) -> None:
        """Hide MCU-boundary ports on canvas (directional). yaml 不变。"""
        if out is not None:
            self._canvas_hide_out = {short_service(s) for s in out}
        if inn is not None:
            self._canvas_hide_in = {short_service(s) for s in inn}
        self._height = self._compute_height()
        self._rebuild_ports()
        self.prepareGeometryChange()
        self.update()

    def _visible_provides(self) -> list[str]:
        return [p for p in self.provides if short_service(p) not in self._canvas_hide_out]

    def _visible_requires(self) -> list[str]:
        return [r for r in self.requires if short_service(r) not in self._canvas_hide_in]

    def set_ports(self, provides: list[str], requires: list[str]) -> None:
        self.provides = list(provides)
        self.requires = list(requires)
        self._height = self._compute_height()
        self._rebuild_ports()
        self.prepareGeometryChange()
        self.update()
        for e in self._edges:
            e.update_path()

    def set_port_sides(self, *, out_side: str | None = None, in_side: str | None = None) -> None:
        if out_side is not None:
            self.out_side = _norm_side(out_side, self.out_side)
        if in_side is not None:
            self.in_side = _norm_side(in_side, self.in_side)
        self._rebuild_ports()
        self.prepareGeometryChange()
        self.update()
        for e in self._edges:
            e.update_path()

    def _compute_height(self) -> float:
        # MCU/车身：紧凑块放大（宽×1.5 / 高×3），仍不展示信号端口
        if self.is_external():
            return float(self.EXT_HEIGHT)
        n = (
            1
            + max(len(self._visible_provides()), 1)
            + 1
            + max(len(self._visible_requires()), 1)
        )
        return self.HEADER + n * self.LINE + 12

    def _place_on_side(self, side: str, index: int, count: int) -> QPointF:
        n = max(count, 1)
        t = (index + 1) / (n + 1)
        w = self.card_width
        if side == "right":
            return QPointF(w, self.HEADER + t * (self._height - self.HEADER))
        if side == "left":
            return QPointF(0, self.HEADER + t * (self._height - self.HEADER))
        if side == "top":
            return QPointF(t * w, 0)
        return QPointF(t * w, self._height)

    def _rebuild_ports(self) -> None:
        for p in self._out_ports + self._in_ports:
            if p.scene():
                p.scene().removeItem(p)
            else:
                p.setParentItem(None)
        self._out_ports.clear()
        self._in_ports.clear()

        # 外部 MCU：无端口（与 gateway 用边界连线，不在画布上挂信号）
        if self.is_external():
            return

        outs = self._visible_provides()
        ins = self._visible_requires()
        for i, svc in enumerate(outs):
            port = PortItem(self, "out", svc, i)
            port.setPos(self._place_on_side(self.out_side, i, len(outs)))
            self._out_ports.append(port)
        for i, svc in enumerate(ins):
            port = PortItem(self, "in", svc, i)
            port.setPos(self._place_on_side(self.in_side, i, len(ins)))
            self._in_ports.append(port)

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
        return self.scenePos() + QPointF(self.card_width, self._height / 2)

    def in_anchor(self, service: str) -> QPointF:
        port = self.in_port_for_service(service)
        if port:
            return port.scene_center()
        return self.scenePos() + QPointF(0, self._height / 2)

    def peer_anchor(self, toward: ProcessCard) -> QPointF:
        """MCU↔gateway 边界连线锚点（模块中心朝向对端一侧）。"""
        w = self.EXT_WIDTH if self.is_external() else self.WIDTH
        h = self._height
        sp = self.pos()  # itemChange 期间比 scenePos() 更安全
        c = sp + QPointF(w / 2, h / 2)
        ow = toward.EXT_WIDTH if toward.is_external() else toward.WIDTH
        other = toward.pos() + QPointF(ow / 2, toward._height / 2)
        if other.x() >= c.x():
            return sp + QPointF(w, h / 2)
        return sp + QPointF(0, h / 2)

    def set_visual_state(self, *, emphasis: bool = False, dimmed: bool = False) -> None:
        self._emphasis = emphasis
        self._dimmed = dimmed
        if _qt_alive(self):
            self.update()
            for p in self._out_ports + self._in_ports:
                if _qt_alive(p):
                    p._apply_brush()

    def boundingRect(self) -> QRectF:
        return QRectF(-8, -4, self.card_width + 16, self._height + 8)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:  # type: ignore[no-untyped-def]
        w = self.card_width
        r = QRectF(0, 0, w, self._height)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        external = self.is_external()

        if self._emphasis or self.isSelected():
            fill = QColor("#3d3a1e") if external else QColor("#1e6b4f")
            border = QColor("#f7dc6f")
            border_w = 3.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(247, 220, 111, 50)))
            painter.drawRoundedRect(r.adjusted(-5, -5, 5, 5), 12, 12)
        elif self._dimmed:
            fill = QColor("#1a1a14") if external else QColor("#0f221c")
            border = QColor("#5c5346")
            border_w = 1.5
        else:
            fill = QColor("#2a2618") if external else QColor("#15352c")
            border = QColor("#c9a227") if external else QColor("#7dcea0")
            border_w = 2

        painter.setBrush(QBrush(fill))
        pen = QPen(border, border_w)
        if external:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
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
        title = self.label or self.process_name
        painter.drawText(
            QRectF(8, y, w - 16, 20),
            Qt.AlignmentFlag.AlignLeft,
            title,
        )
        y += 20

        font_small = QFont()
        font_small.setPointSize(8)
        painter.setFont(font_small)
        painter.setPen(QColor("#5d6d63") if self._dimmed else QColor("#7fb39a"))
        painter.drawText(8, y + 12, role_of(self.process_name, kind=self.kind))
        y += 16
        # compute_domain：部署域（写进 wiring/SOR；卡片上可见）
        dom_c = QColor("#4a4030") if self._dimmed else QColor("#c9a227")
        painter.setPen(dom_c)
        painter.drawText(8, y + 12, f"部署:{self.compute_domain}")

        if external:
            y += 28
            painter.setPen(QColor("#8a7a40") if self._dimmed else QColor("#f0e6b0"))
            painter.drawText(8, y + 12, "↔ 仅连 gateway")
            y += 28
            painter.setPen(QColor("#6e6340") if self._dimmed else QColor("#d5c48a"))
            painter.drawText(8, y + 12, "VehicleBus / Trajectory")
            return

        y = self.HEADER
        out_hint = _SIDE_LABEL.get(self.out_side, self.out_side)
        in_hint = _SIDE_LABEL.get(self.in_side, self.in_side)
        outs = self._visible_provides()
        ins = self._visible_requires()
        # 已连线：Out 绿 / In 橙；未连线：红
        out_head = QColor("#145a32") if self._dimmed else QColor("#00e676")
        out_ok = QColor("#1e8449") if self._dimmed else QColor("#69f0ae")
        in_head = QColor("#6e2c00") if self._dimmed else QColor("#ff9100")
        in_ok = QColor("#935116") if self._dimmed else QColor("#ffb74d")
        unlinked = QColor("#7b241c") if self._dimmed else QColor("#e74c3c")
        painter.setPen(out_head)
        painter.drawText(8, y + 12, f"● Out →{out_hint}")
        y += self.LINE
        if outs:
            for p in outs:
                painter.setPen(out_ok if self.is_port_linked("out", p) else unlinked)
                painter.drawText(14, y + 12, short_service(p))
                y += self.LINE
        else:
            painter.setPen(QColor("#566573"))
            painter.drawText(14, y + 12, "(none)")
            y += self.LINE

        painter.setPen(in_head)
        painter.drawText(8, y + 12, f"■ In →{in_hint}")
        y += self.LINE
        if ins:
            for req in ins:
                painter.setPen(in_ok if self.is_port_linked("in", req) else unlinked)
                painter.drawText(14, y + 12, short_service(req))
                y += self.LINE
        else:
            painter.setPen(QColor("#566573"))
            painter.drawText(14, y + 12, "(none)")

    def itemChange(self, change, value):  # type: ignore[no-untyped-def]
        if not _qt_alive(self):
            return value
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # 拖动中禁止 setSceneRect / ensureVisible（否则飞快 + RecursionError）
            if not self._updating_links:
                self._updating_links = True
                try:
                    for e in self._edges:
                        if _qt_alive(e):
                            e.update_path()
                finally:
                    self._updating_links = False
            if self.graph is not None:
                self.graph.note_card_pos_live(self)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update()
            for p in self._out_ports + self._in_ports:
                if _qt_alive(p):
                    p._apply_brush()
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().mouseReleaseEvent(event)
        if self.graph is not None and event.button() == Qt.MouseButton.LeftButton:
            self.graph.finalize_card_drag(self)

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


class RouteHandle(QGraphicsEllipseItem):
    """Draggable midpoint to reshape an edge path (child of EdgeCurve)."""

    R = 9.0

    def __init__(self, edge: EdgeCurve) -> None:
        r = self.R
        # 挂在线上：点手柄不会取消线的选中（独立 scene 项会清选中→黄点立刻消失）
        super().__init__(-r, -r, 2 * r, 2 * r, edge)
        self.edge = edge
        self.setZValue(50)
        self.setBrush(QBrush(QColor("#ff2d95")))  # 品红，选中线上易见
        self.setPen(QPen(QColor("#ffffff"), 2.0))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("拖动调整连线路径（Ctrl+S 保存）")
        self._updating = False
        self.hide()

    def itemChange(self, change, value):  # type: ignore[no-untyped-def]
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and not self._updating
            and _qt_alive(self.edge)
        ):
            self.edge.on_handle_moved(self.scenePos())
        return super().itemChange(change, value)


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
        self._role = ""  # "" | "out" | "in" — 相对选中节点的进出
        self._handle: RouteHandle | None = None
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # PathItem 默认裁剪子项到线形；关掉才能看见路径点
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, False)
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

    def set_visual_state(
        self,
        *,
        highlight: bool = False,
        dimmed: bool = False,
        role: str = "",
    ) -> None:
        self._highlight = highlight
        self._dimmed = dimmed
        self._role = role
        if not _qt_alive(self):
            return
        self._apply_style()
        self.update_path()

    def _apply_style(self) -> None:
        selected = self.isSelected()
        if selected:
            # 选中线本身：亮黄 + 显示路径点
            color = QColor("#f7dc6f")
            width = 3.2
        elif self._highlight and self._role == "out":
            color = QColor("#2ecc71")
            width = 2.8
        elif self._highlight and self._role == "in":
            color = QColor("#e67e22")
            width = 2.8
        elif self._highlight:
            color = QColor("#f7dc6f")
            width = 2.5
        elif self._dimmed:
            color = QColor(self._base_color)
            color.setAlpha(55)
            width = 1.2
        else:
            color = self._base_color
            width = 2.0
        self.setPen(QPen(color, width))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        if selected:
            lc = QColor("#f7dc6f")
        elif self._highlight and self._role == "out":
            lc = QColor("#abebc6")
        elif self._highlight and self._role == "in":
            lc = QColor("#fad7a0")
        else:
            lc = self._base_color.lighter(130)
        if self._dimmed and not selected and not self._highlight:
            lc.setAlpha(80)
        self._label.setBrush(QBrush(lc))

    def shape(self) -> QPainterPath:
        """Widen hit area so thin lines are easy to select."""
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        return stroker.createStroke(self.path())

    @staticmethod
    def _leave_point(p: QPointF, side: str, dist: float, spread: float) -> QPointF:
        if side == "right":
            return QPointF(p.x() + dist, p.y() + spread)
        if side == "left":
            return QPointF(p.x() - dist, p.y() + spread)
        if side == "top":
            return QPointF(p.x() + spread, p.y() - dist)
        return QPointF(p.x() + spread, p.y() + dist)

    @staticmethod
    def _approach_point(p: QPointF, side: str, dist: float, spread: float) -> QPointF:
        if side == "left":
            return QPointF(p.x() - dist, p.y() + spread)
        if side == "right":
            return QPointF(p.x() + dist, p.y() + spread)
        if side == "top":
            return QPointF(p.x() + spread, p.y() - dist)
        return QPointF(p.x() + spread, p.y() + dist)

    def update_path(self) -> None:
        p0 = self.src.out_anchor(self.service)
        p3 = self.dst.in_anchor(self.service)
        if self.fan_count > 1:
            spread = (self.fan_index - (self.fan_count - 1) / 2.0) * 28.0
        else:
            spread = 0.0
        dist = max(48.0, 0.25 * math.hypot(p3.x() - p0.x(), p3.y() - p0.y()))
        p1 = self._leave_point(p0, self.src.out_side, dist, spread)
        p2 = self._approach_point(p3, self.dst.in_side, dist, spread)

        route = self.flow.get("route") if isinstance(self.flow.get("route"), dict) else {}
        mid_dx = float(route.get("mid_dx") or 0.0)
        mid_dy = float(route.get("mid_dy") or 0.0)
        p1 = QPointF(p1.x() + mid_dx, p1.y() + mid_dy)
        p2 = QPointF(p2.x() + mid_dx, p2.y() + mid_dy)

        path = QPainterPath(p0)
        path.cubicTo(p1, p2, p3)

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

        handle_pt = cubic_bezier_point(p0, p1, p2, p3, 0.5)
        show_handle = self.isSelected()  # 仅选中该线时显示路径点
        if show_handle:
            if self._handle is None:
                self._handle = RouteHandle(self)
            if self._handle is not None and _qt_alive(self._handle):
                self._handle._updating = True
                # 子项坐标相对 EdgeCurve（默认在 0,0）
                self._handle.setPos(self.mapFromScene(handle_pt))
                self._handle.show()
                self._handle.setZValue(50)
                self._handle._updating = False
        elif self._handle is not None and _qt_alive(self._handle):
            self._handle.hide()

    def on_handle_moved(self, scene_pos: QPointF) -> None:
        """User dragged route handle → persist offset relative to default mid."""
        p0 = self.src.out_anchor(self.service)
        p3 = self.dst.in_anchor(self.service)
        if self.fan_count > 1:
            spread = (self.fan_index - (self.fan_count - 1) / 2.0) * 28.0
        else:
            spread = 0.0
        dist = max(48.0, 0.25 * math.hypot(p3.x() - p0.x(), p3.y() - p0.y()))
        p1 = self._leave_point(p0, self.src.out_side, dist, spread)
        p2 = self._approach_point(p3, self.dst.in_side, dist, spread)
        default_mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
        self.flow["route"] = {
            "mid_dx": round(scene_pos.x() - default_mid.x(), 1),
            "mid_dy": round(scene_pos.y() - default_mid.y(), 1),
        }
        if self.graph is not None and self.graph._session is not None:
            self.graph._session.dirty_wiring = True
            self.graph.changed.emit()
        self.update_path()

    def remove_label(self) -> None:
        if self._handle is not None and _qt_alive(self._handle):
            sc = self._handle.scene()
            if sc is not None:
                sc.removeItem(self._handle)
            else:
                self._handle.setParentItem(None)
            self._handle = None
        if _qt_alive(self._label) and self._label.scene():
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


class McuPeerLink(QGraphicsPathItem):
    """MCU/车身 ↔ gateway 的特殊边界连线（画布不展示具体信号端口）。"""

    def __init__(
        self,
        mcu: ProcessCard,
        gateway: ProcessCard,
        services: list[str],
        graph: WiringGraphView | None = None,
    ) -> None:
        super().__init__()
        self.mcu = mcu
        self.gateway = gateway
        self.services = list(services)
        self.graph = graph
        self.src = mcu
        self.dst = gateway
        self._highlight = False
        self._dimmed = False
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        mcu._edges.append(self)
        gateway._edges.append(self)
        label = "MCU ↔ gateway"
        if services:
            shorts = sorted({short_service(s) for s in services})
            label = f"MCU ↔ gateway（{' / '.join(shorts[:3])}）"
        self._label = QGraphicsSimpleTextItem(label)
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
            width = 3.5
        elif self._dimmed:
            color = QColor("#c9a227")
            color.setAlpha(55)
            width = 1.8
        else:
            color = QColor("#c9a227")
            width = 2.8
        pen = QPen(color, width, Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        lc = QColor("#fff8dc") if (self._highlight or selected) else QColor("#f0e6b0")
        if self._dimmed and not selected:
            lc.setAlpha(80)
        self._label.setBrush(QBrush(lc))

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(16.0)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        return stroker.createStroke(self.path())

    def update_path(self) -> None:
        if not _qt_alive(self.mcu) or not _qt_alive(self.gateway):
            return
        # 拖动卡片时 peer_anchor 可能再入 itemChange；用几何缓存避免深递归
        p0 = self.mcu.peer_anchor(self.gateway)
        p3 = self.gateway.peer_anchor(self.mcu)
        mid = QPointF((p0.x() + p3.x()) / 2.0, (p0.y() + p3.y()) / 2.0)
        path = QPainterPath(p0)
        path.quadTo(mid + QPointF(0, -24), p3)
        # 双向示意箭头
        for tip, base in ((p3, mid), (p0, mid)):
            dx, dy = tip.x() - base.x(), tip.y() - base.y()
            length = math.hypot(dx, dy) or 1.0
            ux, uy = dx / length, dy / length
            append_chevron(path, tip, ux, uy, arrow_len=9.0, arrow_w=4.5)
        self.setPath(path)
        if self.scene() and self._label.scene() is None:
            self.scene().addItem(self._label)
        if _qt_alive(self._label):
            self._label.setPos(mid.x() - 40, mid.y() - 36)
            self._label.setZValue(2 if (self._highlight or self.isSelected()) else 1)

    def remove_label(self) -> None:
        if _qt_alive(self._label) and self._label.scene():
            self._label.scene().removeItem(self._label)

    def itemChange(self, change, value):  # type: ignore[no-untyped-def]
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._apply_style()
            self.update_path()
        return super().itemChange(change, value)

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.graph is not None:
            self.graph.show_peer_menu(self, event.screenPos())
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
        # 负坐标节点（MCU 拖到左侧）时，避免默认居中把左缘裁掉
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
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
        *,
        out_side: str = "right",
        in_side: str = "left",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"编辑端口 — {process}")
        self.resize(480, 480)

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
        side_row = QHBoxLayout()
        self._out_side = QComboBox()
        self._in_side = QComboBox()
        for s in _PORT_SIDES:
            self._out_side.addItem(f"Out 在{_SIDE_LABEL[s]}侧", s)
            self._in_side.addItem(f"In 在{_SIDE_LABEL[s]}侧", s)
        self._out_side.setCurrentIndex(
            max(0, _PORT_SIDES.index(_norm_side(out_side, "right")))
        )
        self._in_side.setCurrentIndex(
            max(0, _PORT_SIDES.index(_norm_side(in_side, "left")))
        )
        side_row.addWidget(self._out_side)
        side_row.addWidget(self._in_side)
        layout.addLayout(side_row)
        layout.addWidget(QLabel("Out (provides)"))
        layout.addWidget(self._provides)
        layout.addWidget(QLabel("In (requires)"))
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

    def result_ports(self) -> tuple[list[str], list[str], str, str]:
        provides = [self._provides.item(i).text() for i in range(self._provides.count())]
        requires = [self._requires.item(i).text() for i in range(self._requires.count())]
        out_side = str(self._out_side.currentData() or "right")
        in_side = str(self._in_side.currentData() or "left")
        return provides, requires, out_side, in_side


class ImportPortsDialog(QDialog):
    """Shared dialog: pick candidates from hpp or fidl → module ports."""

    def __init__(
        self,
        candidates: list[str],
        processes: list[str],
        default_process: str,
        parent: QWidget | None = None,
        *,
        title: str = "添加端口",
        hint: str = "勾选要加入的名称（作为 service 短名）：",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(460, 480)
        self._all = list(candidates)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(hint))

        self._fat_only = QCheckBox("仅粗端口 / 整包对接（推荐，隐藏 Item 碎片）")
        self._fat_only.setChecked(len(candidates) > 6)
        self._fat_only.toggled.connect(self._rebuild_checks)
        layout.addWidget(self._fat_only)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._checks_host = QWidget()
        self._checks_layout = QVBoxLayout(self._checks_host)
        self._scroll.setWidget(self._checks_host)
        layout.addWidget(self._scroll, stretch=1)
        self._checks: list[QCheckBox] = []
        self._rebuild_checks()

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

    def _rebuild_checks(self) -> None:
        while self._checks_layout.count():
            item = self._checks_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._checks.clear()
        names = self._all
        if self._fat_only.isChecked():
            fat = [n for n in self._all if is_fat_port_name(n)]
            if fat:
                names = fat
        for name in names:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._checks.append(cb)
            self._checks_layout.addWidget(cb)
        self._checks_layout.addStretch(1)

    def selected(self) -> tuple[str, list[str], str]:
        names = [cb.text() for cb in self._checks if cb.isChecked()]
        direction = "out" if self._dir_out.isChecked() else "in"
        return self._proc.currentText(), names, direction


# Back-compat alias
ImportHppDialog = ImportPortsDialog


class AddNodeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加模块")
        form = QFormLayout(self)
        self._name = QLineEdit("sensing.new_app")
        self._domain = QComboBox()
        self._domain.setEditable(False)
        # 普通 SOA/Adapter 模块；MCU 走单独入口，不在此选 external
        self._domain.addItem("ap_linux — 域控 Linux（默认，几乎总是这个）", "ap_linux")
        self._domain.addItem("host — 桌面联调 PC（开发机跑 sim）", "host")
        self._domain.setCurrentIndex(0)
        self._domain.setToolTip(
            "compute_domain：进程跑在哪个算力域。\n"
            "写入 wiring.yaml → Verify 合成进 gf.sor.json 的 deployments[]。\n"
            "异构 AP+MCU 拓扑时用于选 binding / 裁剪；ap_only 项目里多为元数据。\n"
            "卡片上会显示「部署:ap_linux」。"
        )
        hint = QLabel(
            "「部署域」= wiring 字段 compute_domain（不是 computer）。\n"
            "画布上体现为卡片第三行「部署:xxx」；进 SOR 后供异构部署/裁剪使用。\n"
            "当前多数项目选 ap_linux 即可。\n\n"
            "MCU/车身不是普通模块：请空白处右键 →「添加 MCU/车身」\n"
            "（金框特殊节点，无信号端口，只连 gateway）。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:11px;")
        form.addRow("进程名", self._name)
        form.addRow("部署域（compute_domain）", self._domain)
        form.addRow(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[str, str]:
        name = self._name.text().strip()
        data = self._domain.currentData()
        domain = str(data) if data else "ap_linux"
        return name, domain or "ap_linux"


class WiringGraphView(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: ProjectSession | None = None
        self._nodes: dict[str, ProcessCard] = {}
        self._edges: list[EdgeCurve] = []
        self._missing: list[MissingEdge] = []
        self._peers: list[McuPeerLink] = []
        self._wire_src: PortItem | None = None
        self._wire_line: QGraphicsLineItem | None = None
        # process_name -> (x, y); survives rebuild so edits don't reset layout
        self._layout_pos: dict[str, tuple[float, float]] = {}
        # 打开项目时 Tab 可能尚未显示，viewport=0 → fitInView 无效；显示后再 fit
        self._need_fit_on_show = False

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
            "●绿=Out已连 · ■橙=In已连 · 红=未连线（文字与端口圆点）\n"
            "MCU/车身=金框特殊节点，无端口，只与 gateway 一条边界虚线\n"
            "部署:xxx=compute_domain · Verify 结果见右侧「Lineage」页"
        )
        self._legend.setWordWrap(True)
        self._legend.setStyleSheet("color: #a9cfc0; font-size: 11px;")

        flows_page = QWidget()
        flows_l = QVBoxLayout(flows_page)
        flows_l.setContentsMargins(4, 4, 4, 4)
        flows_l.addWidget(self._legend)
        flows_l.addWidget(self._search)
        flows_l.addWidget(self._search_hits)
        flows_l.addWidget(QLabel("全部 dataflows（右键画布可删边）"))
        flows_l.addWidget(self._flow_list)

        self._lineage = LineageView()
        self._lineage.set_placeholder("尚无 lineage。菜单：文件 → Verify（Ctrl+R）")

        self._right_tabs = QTabWidget()
        self._right_tabs.addTab(flows_page, "连线")
        self._right_tabs.addTab(self._lineage, "Lineage")

        self._right_panel = QWidget()
        right = QVBoxLayout(self._right_panel)
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(self._right_tabs)
        self._right_panel.setMinimumWidth(300)
        self._right_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )

        self._btn_toggle_right = QToolButton()
        # 面板在右：展开时 ▶=点此收起；收起后 ◀=点此展开
        self._btn_toggle_right.setText("▶")
        self._btn_toggle_right.setToolTip("折叠 / 展开右侧面板（连线 + Lineage）")
        self._btn_toggle_right.setFixedWidth(22)
        self._btn_toggle_right.clicked.connect(self._toggle_right_panel)
        self._right_collapsed = False

        layout = QHBoxLayout(self)
        layout.addWidget(self._view, stretch=3)
        layout.addWidget(self._btn_toggle_right, stretch=0)
        layout.addWidget(self._right_panel, stretch=1)

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

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        if self._need_fit_on_show:
            QTimer.singleShot(0, self._fit_after_show)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        if self._need_fit_on_show and self._view.viewport().width() > 40:
            QTimer.singleShot(0, self._fit_after_show)

    def _fit_after_show(self) -> None:
        if not self._need_fit_on_show:
            return
        if self._view.viewport().width() < 40:
            return
        self._need_fit_on_show = False
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
        self.rebuild(fit_view=True)

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
            self._session.set_node_ui(
                card.process_name,
                x=round(p.x(), 1),
                y=round(p.y(), 1),
                out_side=card.out_side,
                in_side=card.in_side,
                kind=card.kind if card.kind != "process" else None,
                label=card.label or None,
            )
            self.changed.emit()
        self._refresh_scene_rect()

    def remember_card_pos(self, card: ProcessCard) -> None:
        """兼容旧调用：等价于松开时落盘。"""
        self.finalize_card_drag(card)

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
        if rect.isNull():
            return QRectF(0, 0, 400, 300)
        return rect

    def _refresh_scene_rect(self) -> None:
        if not self._nodes and not self._scene.items():
            self._scene.setSceneRect(QRectF())
            return
        # 大边距：负坐标 MCU 可滚进视口，不被裁切
        r = self._nodes_content_rect().adjusted(-400, -400, 400, 400)
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
        content = self._nodes_content_rect().adjusted(-120, -120, 120, 120)
        self._refresh_scene_rect()
        self._view.fitInView(content, Qt.AspectRatioMode.KeepAspectRatio)
        self._view.remember_default_transform()
        self._need_fit_on_show = False

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

        for p in self._peers:
            p.set_visual_state(highlight=(p in peer_hit), dimmed=(p not in peer_hit))

        for m in self._missing:
            hit = m.src is focus or m.dst is focus
            m.set_visual_state(highlight=hit, dimmed=not hit)

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
        act_ext = menu.addAction("添加 MCU/车身 节点…")
        act_import = menu.addAction("导入 hpp/h…")
        chosen = menu.exec(self._view.mapToGlobal(pos))
        if chosen is act_add:
            self.add_node()
        elif chosen is act_ext:
            self.add_external_mcu_node()
        elif chosen is act_import:
            self.import_hpp()

    def show_edge_menu(self, edge: EdgeCurve, global_pos) -> None:  # type: ignore[no-untyped-def]
        edge.setSelected(True)
        menu = QMenu(self)
        act_edit = menu.addAction("编辑信号名…")
        act_reset = menu.addAction("重置连线路径")
        act_del = menu.addAction("删除信号线")
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_edge(edge)
        elif chosen is act_reset:
            edge.flow.pop("route", None)
            if self._session:
                self._session.dirty_wiring = True
            edge.update_path()
            self.changed.emit()
        elif chosen is act_del:
            self._remove_edge(edge)

    def show_missing_menu(self, miss: MissingEdge, global_pos) -> None:  # type: ignore[no-untyped-def]
        miss.setSelected(True)
        menu = QMenu(self)
        act_fix = menu.addAction("补上连线（写入 dataflow）")
        act_ignore = menu.addAction("忽略此建议（不再显示）")
        act_drop = menu.addAction("移除目标 In 端口（不再需要该输入）")
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
            QMessageBox.information(self, "补线", "该 dataflow 已存在")
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

    def _focus_peer(self, peer: McuPeerLink, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            peer.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
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
        menu.addAction("MCU ↔ gateway 边界（yaml 仍保留 VehicleBus/Trajectory）").setEnabled(False)
        act_focus_mcu = menu.addAction("选中 MCU")
        act_focus_gw = menu.addAction("选中 gateway")
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
        elif kind == "peer" and 0 <= idx < len(self._peers):
            self._focus_peer(self._peers[idx])

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
            if data and data[0] == "missing" and 0 <= data[1] < len(self._missing):
                self.ignore_missing_edge(self._missing[data[1]])
                return
        if 0 <= row < len(self._edges):
            self._remove_edge(self._edges[row])

    def show_card_menu(self, card: ProcessCard, global_pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        if card.is_external():
            menu.addAction("MCU/车身：无信号端口，只连 gateway").setEnabled(False)
            act_del = menu.addAction("删除 MCU/车身")
            chosen = menu.exec(global_pos)
            if chosen is act_del:
                self.delete_node(card)
            return
        act_edit = menu.addAction("编辑端口 / 方位…")
        act_import = menu.addAction("从此模块导入 hpp…")
        side_menu = menu.addMenu("快捷：端口方位")
        act_in_bottom = side_menu.addAction("In 放到下边（适合 gateway/planning）")
        act_out_bottom = side_menu.addAction("Out 放到下边")
        act_default = side_menu.addAction("恢复默认（Out 右 / In 左）")
        menu.addSeparator()
        act_del = menu.addAction("删除模块")
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_ports(card)
        elif chosen is act_import:
            self.import_hpp(default_process=card.process_name)
        elif chosen is act_in_bottom:
            self._set_card_sides(card, in_side="bottom")
        elif chosen is act_out_bottom:
            self._set_card_sides(card, out_side="bottom")
        elif chosen is act_default:
            self._set_card_sides(card, out_side="right", in_side="left")
        elif chosen is act_del:
            self.delete_node(card)

    def _set_card_sides(
        self,
        card: ProcessCard,
        *,
        out_side: str | None = None,
        in_side: str | None = None,
    ) -> None:
        if not self._session:
            return
        if out_side is None:
            out_side = card.out_side
        if in_side is None:
            in_side = card.in_side
        self._session.set_node_ui(card.process_name, out_side=out_side, in_side=in_side)
        card.set_port_sides(out_side=out_side, in_side=in_side)
        self.changed.emit()

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
        self.rebuild(fit_view=True)
        self.changed.emit()

    def add_external_mcu_node(self) -> None:
        """Placeholder: MCU/车身 — 信号来源与控车去向。"""
        if not self._session:
            return
        name = "external.vehicle_mcu"
        if name in self._nodes:
            QMessageBox.information(self, "外部节点", f"已存在：{name}")
            return
        self._session.upsert_deployment(
            name,
            compute_domain="external",
            provides=["services.semantic.VehicleBus"],
            requires=["services.semantic.Trajectory"],
        )
        self._session.set_node_ui(
            name,
            kind="external",
            label="MCU / 车身",
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
        QMessageBox.information(
            self,
            "MCU / 车身",
            "已添加特殊边界节点：画布无信号端口，只与 gateway 一条金色虚线。\n"
            "yaml 仍保留 VehicleBus / Trajectory 供 Verify；Ctrl+S 保存布局。",
        )

    def flush_canvas(self) -> None:
        """Persist node positions / sides into wiring.canvas before save."""
        if not self._session:
            return
        for name, card in self._nodes.items():
            if not _qt_alive(card):
                continue
            p = card.pos()
            self._session.set_node_ui(
                name,
                x=round(p.x(), 1),
                y=round(p.y(), 1),
                out_side=card.out_side,
                in_side=card.in_side,
                kind=card.kind if card.kind != "process" else None,
                label=card.label or None,
            )

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
        if card.is_external():
            QMessageBox.information(
                self,
                "MCU / 车身",
                "这是特殊边界节点：画布上无信号端口，只与 gateway 一条边界连线。\n\n"
                "wiring.yaml 底层仍保留 VehicleBus / Trajectory dataflow，供 Verify 使用。",
            )
            return
        dlg = PortEditDialog(
            card.process_name,
            list(card.provides),
            list(card.requires),
            self._port_candidates(card.process_name),
            self,
            out_side=card.out_side,
            in_side=card.in_side,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        provides, requires, out_side, in_side = dlg.result_ports()
        self._session.set_ports(card.process_name, provides, requires)
        self._session.set_node_ui(
            card.process_name, out_side=out_side, in_side=in_side
        )
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
        self._apply_import_candidates(
            candidates,
            default_process,
            source_path=hpp_path,
            kind="hpp",
            title="从头文件添加端口",
            hint="勾选要加入的类型（作为 service 短名）：",
        )

    def import_fidl(self, default_process: str = "") -> None:
        if not self._session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 FIDL",
            str(self._session.paths.project_dir),
            "Franca IDL (*.fidl);;All (*)",
        )
        if not path:
            return
        fidl_path = Path(path)
        try:
            candidates = self._session.parse_fidl_candidates(fidl_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "解析失败", str(exc))
            return
        if not candidates:
            QMessageBox.information(
                self,
                "导入",
                "未解析到 interface/struct/method/broadcast，请检查 .fidl 格式",
            )
            return
        self._apply_import_candidates(
            candidates,
            default_process,
            source_path=fidl_path,
            kind="fidl",
            title="从 FIDL 添加端口",
            hint="勾选要加入的名称（struct / broadcast / method / interface）：",
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
            QMessageBox.information(self, "导入", "请先添加至少一个模块")
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
            "导入完成",
            f"已关联 {rel}\n向 {process} 添加了 {len(names)} 个{direction} 端口。\n"
            "可双击模块继续调整，再从 Out 拖到 In 连线。",
        )

    def rebuild(self, *, fit_view: bool = False, reset_layout: bool = False) -> None:
        self.cancel_wire()
        # Snapshot positions before C++ items are destroyed
        if not reset_layout:
            for name, card in list(self._nodes.items()):
                if _qt_alive(card):
                    p = card.pos()
                    self._layout_pos[name] = (p.x(), p.y())
        else:
            self._layout_pos.clear()

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
            for p in self._peers:
                if _qt_alive(p):
                    p.remove_label()
            self._nodes.clear()
            self._edges.clear()
            self._missing.clear()
            self._peers.clear()
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

        # auto-layout slots for nodes without a remembered position
        auto_slots: dict[str, tuple[float, float]] = {}
        ext_i = 0
        for depth, names in sorted(cols.items()):
            for i, name in enumerate(names):
                if is_external_node(process=name):
                    # MCU 默认在最左，避免挤进 AP 列被裁切
                    auto_slots[name] = (-280.0, 40.0 + ext_i * 120.0)
                    ext_i += 1
                else:
                    # AP 列整体右移，给左侧 MCU 留空
                    auto_slots[name] = (120.0 + depth * 280.0, 40.0 + i * 240.0)

        for name in ordered:
            d = dep_map.get(name) or {}
            provides = [str(x) for x in (d.get("provides") or [])]
            requires = [str(x) for x in (d.get("requires") or [])]
            ui = self._session.node_ui(name)
            if name in self._layout_pos:
                x, y = self._layout_pos[name]
            elif "x" in ui and "y" in ui:
                x, y = float(ui["x"]), float(ui["y"])
                self._layout_pos[name] = (x, y)
            else:
                x, y = auto_slots.get(name, (40.0, 40.0))
                if name not in auto_slots:
                    n = len(self._layout_pos)
                    x, y = 80.0 + (n % 4) * 40.0, 80.0 + (n // 4) * 40.0
                self._layout_pos[name] = (x, y)
            kind = str(ui.get("kind") or "")
            if is_external_node(kind=kind, process=name) and not kind:
                kind = "external"
            card = ProcessCard(
                name,
                provides,
                requires,
                x,
                y,
                graph=self,
                out_side=str(ui.get("out_side") or "right"),
                in_side=str(ui.get("in_side") or "left"),
                kind=kind or "process",
                label=str(ui.get("label") or ""),
                compute_domain=str(d.get("compute_domain") or "ap_linux"),
            )
            self._scene.addItem(card)
            self._nodes[name] = card

        # drop positions for deleted processes
        self._layout_pos = {k: v for k, v in self._layout_pos.items() if k in self._nodes}

        flows = self._session.dataflows()
        outbound_count: dict[str, int] = {}
        outbound_seen: dict[str, int] = {}
        peer_svcs: dict[tuple[str, str], list[str]] = {}
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
            # MCU/车身相关流：画布合并为一条边界线；yaml 仍保留具体 service
            if src_n.is_external() or dst_n.is_external():
                a, b = (src, dst) if src_n.is_external() else (dst, src)
                key = (a, b)
                peer_svcs.setdefault(key, []).append(svc)
                continue
            idx = outbound_seen.get(src, 0)
            outbound_seen[src] = idx + 1
            edge = EdgeCurve(src_n, dst_n, svc, fl, idx, outbound_count.get(src, 1), graph=self)
            self._scene.addItem(edge)
            edge.update_path()  # 入景后再挂路径控制点
            self._edges.append(edge)
            item = QListWidgetItem(f"{short_service(svc)}:  {src}  →  {dst}")
            item.setData(Qt.ItemDataRole.UserRole, ("edge", len(self._edges) - 1))
            self._flow_list.addItem(item)

        # gateway 上仅面向 MCU 的端口：画布隐藏（保留 planning→Trajectory In 等）
        hide_out: dict[str, set[str]] = {}
        hide_in: dict[str, set[str]] = {}
        for fl in flows:
            src = str(fl.get("from") or "")
            dst = str(fl.get("to") or "")
            svc = short_service(str(fl.get("service") or ""))
            src_n = self._nodes.get(src)
            dst_n = self._nodes.get(dst)
            if not src_n or not dst_n or not svc:
                continue
            if src_n.is_external() and not dst_n.is_external():
                hide_in.setdefault(dst, set()).add(svc)
            elif dst_n.is_external() and not src_n.is_external():
                hide_out.setdefault(src, set()).add(svc)
        for name, card in self._nodes.items():
            if card.is_external():
                continue
            card.set_canvas_hide(out=hide_out.get(name, set()), inn=hide_in.get(name, set()))
        # 隐藏端口后 gateway 高度变化，刷新已有边锚点
        for e in self._edges:
            if _qt_alive(e):
                e.update_path()

        # 有 dataflow 的端口=已连（绿/橙）；否则红
        linked_out: dict[str, set[str]] = {n: set() for n in self._nodes}
        linked_in: dict[str, set[str]] = {n: set() for n in self._nodes}
        for fl in flows:
            src = str(fl.get("from") or "")
            dst = str(fl.get("to") or "")
            svc = short_service(str(fl.get("service") or ""))
            if not svc:
                continue
            if src in linked_out:
                linked_out[src].add(svc)
            if dst in linked_in:
                linked_in[dst].add(svc)
        for name, card in self._nodes.items():
            card.set_link_status(
                linked_out=linked_out.get(name, set()),
                linked_in=linked_in.get(name, set()),
            )

        for (mcu_name, gw_name), svcs in peer_svcs.items():
            mcu_n = self._nodes.get(mcu_name)
            gw_n = self._nodes.get(gw_name)
            if not mcu_n or not gw_n:
                continue
            peer = McuPeerLink(mcu_n, gw_n, svcs, graph=self)
            self._scene.addItem(peer)
            peer.update_path()
            self._peers.append(peer)
            pitem = QListWidgetItem(
                f"[MCU边界] {mcu_name}  ↔  {gw_name}"
            )
            pitem.setData(
                Qt.ItemDataRole.UserRole, ("peer", len(self._peers) - 1)
            )
            self._flow_list.addItem(pitem)

        provided_by: dict[str, list[str]] = {}
        for name, card in self._nodes.items():
            for p in card.provides:
                provided_by.setdefault(short_service(p), []).append(name)

        # 仅当某 In 端口「完全没有」入边时才提示缺失；
        # MCU/车身不参与缺失虚线（边界由 peer link 表达）。
        for cons_name, card in self._nodes.items():
            if card.is_external():
                continue
            ignored = set()
            if self._session:
                ignored = {
                    str(x)
                    for x in (self._session.node_ui(cons_name).get("ignore_missing") or [])
                }
            for req in card.requires:
                svc_s = short_service(req)
                satisfied = any(
                    str(f.get("to")) == cons_name
                    and short_service(str(f.get("service") or "")) == svc_s
                    for f in flows
                )
                if satisfied:
                    continue
                providers = provided_by.get(svc_s) or []
                if not providers:
                    # 无提供方：仍在列表提示，不画到虚构节点
                    mitem = QListWidgetItem(f"[缺失] {svc_s}:  (无 Provide)  →  {cons_name}")
                    mitem.setData(Qt.ItemDataRole.UserRole, ("missing_orphan", svc_s))
                    self._flow_list.addItem(mitem)
                    continue
                for prov in providers:
                    key = f"{prov}|{svc_s}|{cons_name}"
                    if key in ignored:
                        continue
                    src_n = self._nodes.get(prov)
                    if not src_n or src_n.is_external():
                        continue
                    miss = MissingEdge(src_n, card, req, graph=self)
                    self._scene.addItem(miss)
                    self._missing.append(miss)
                    mitem = QListWidgetItem(f"[缺失] {svc_s}:  {prov}  →  {cons_name}")
                    mitem.setData(
                        Qt.ItemDataRole.UserRole, ("missing", len(self._missing) - 1)
                    )
                    self._flow_list.addItem(mitem)

        if self._search.text().strip():
            self._on_search_text(self._search.text())
        self._refresh_scene_rect()
        if fit_view:
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
        elif kind == "peer" and 0 <= idx < len(self._peers):
            self._focus_peer(self._peers[idx])

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
