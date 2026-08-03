"""Signal-link graph: Simulink-style ports, drag-wire, context menus, hpp import."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

import shiboken6
from PySide6.QtCore import QEvent, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
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
    QApplication,
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
from gf_config.gui.cursors import (
    port_move_cursor,
    wire_link_cursor,
)
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
_SIDE_LABEL = {"left": "left", "right": "right", "top": "top", "bottom": "bottom"}


def is_external_node(*, kind: str = "", process: str = "") -> bool:
    return kind == "external" or process.startswith("external.")


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
    """Out (green) / In (orange). Bare drag = wire; Ctrl+drag = side + order."""

    SIZE = 16.0
    HIT = 22.0  # larger pick target than the painted disc

    def __init__(
        self,
        card: ProcessCard,
        direction: str,
        service: str,
        index: int,
        *,
        side: str = "right",
    ) -> None:
        s = self.SIZE
        super().__init__(-s / 2, -s / 2, s, s)
        self.card = card
        self.direction = direction  # "in" | "out"
        self.service = service
        self.index = index
        self.side = _norm_side(side, "right" if direction == "out" else "left")
        self.setParentItem(card)
        self.setZValue(20)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )
        self.setCursor(wire_link_cursor())
        self._home_pos = QPointF(0, 0)
        self._origin_side = self.side
        self._origin_index = index
        self._pending_side: str | None = None
        self._pending_index: int | None = None
        self._apply_brush()

    def _hover_cursor_for(self) -> QCursor:
        g = self.card.graph if self.card is not None else None
        # During wire drag, override cursor owns the look; keep hand here.
        if g is not None and g._wire_src is not None:
            return wire_link_cursor()
        mods = QApplication.queryKeyboardModifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            return port_move_cursor()
        return wire_link_cursor()

    def hoverEnterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.setCursor(self._hover_cursor_for())
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.setCursor(self._hover_cursor_for())
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.setCursor(wire_link_cursor())
        super().hoverLeaveEvent(event)

    def shape(self) -> QPainterPath:
        """Fat hit target so ports are easy to grab."""
        h = self.HIT
        path = QPainterPath()
        path.addEllipse(QRectF(-h / 2, -h / 2, h, h))
        return path

    def _apply_brush(self) -> None:
        # 颜色 = 方向（Out 绿 / In 橙）；未连用虚线描边提示
        selected = bool(self.card and (self.card.isSelected() or self.card._emphasis))
        linked = bool(self.card and self.card.is_port_linked(self.direction, self.service))
        if self.direction == "out":
            fill = QColor("#2ecc71") if selected else QColor("#58d68d")
            tip_dir = "Out"
        else:
            fill = QColor("#e67e22") if selected else QColor("#f39c12")
            tip_dir = "In"
        if linked:
            border = QColor("#ffffff") if selected else QColor("#f8f9f9")
            tip = "linked"
            pen = QPen(border, 2.5 if selected else 1.5)
        else:
            border = QColor("#922b21")
            tip = "unlinked"
            pen = QPen(border, 2.0 if selected else 1.6)
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setBrush(QBrush(fill))
        self.setPen(pen)
        side_l = _SIDE_LABEL.get(self.side, self.side)
        # 裸拖连线（Out↔In）；Ctrl+拖 = 改边 / 同边调序（减交叉）
        self.setToolTip(
            f"{tip_dir}: {short_service(self.service)} ({tip} · {side_l})\n"
            "拖拽连线 · Ctrl+拖：改边或同边调序 · 右键选边"
        )
        s = self.SIZE
        if self.direction == "in":
            self.setRect(-s / 2, -s / 2 + 1, s, s - 2)
        else:
            self.setRect(-s / 2, -s / 2, s, s)

    def scene_center(self) -> QPointF:
        return self.sceneBoundingRect().center()

    def nearest_card_side(self, scene_pos: QPointF) -> str:
        """Pick left/right/top/bottom from cursor vs card rect in scene coords."""
        r = self.card.sceneBoundingRect()
        cx = (r.left() + r.right()) / 2.0
        cy = (r.top() + r.bottom()) / 2.0
        dx = scene_pos.x() - cx
        dy = scene_pos.y() - cy
        dist_l = abs(scene_pos.x() - r.left())
        dist_r = abs(scene_pos.x() - r.right())
        dist_t = abs(scene_pos.y() - r.top())
        dist_b = abs(scene_pos.y() - r.bottom())
        if not r.contains(scene_pos):
            if abs(dx) >= abs(dy):
                return "right" if dx >= 0 else "left"
            return "bottom" if dy >= 0 else "top"
        return min(
            (dist_l, "left"),
            (dist_r, "right"),
            (dist_t, "top"),
            (dist_b, "bottom"),
            key=lambda t: t[0],
        )[1]

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton and self.card.graph is not None:
            self._home_pos = QPointF(self.pos())
            self._origin_side = self.side
            self._pending_side = None
            self._pending_index = None
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            # 裸拖（Out/In）→ 拉线；Ctrl+拖拽 → 改端口边 / 同边调序
            if ctrl:
                self.card.graph.begin_port_relocate(self)
            else:
                self.card.graph.begin_wire(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        g = self.card.graph
        if g is not None:
            if g._wire_src is not None:
                g.update_wire_preview(event.scenePos())
                event.accept()
                return
            if g._reloc_port is not None:
                g.update_port_relocate(event.scenePos())
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        g = self.card.graph
        if g is not None and event.button() == Qt.MouseButton.LeftButton:
            if g._reloc_port is not None:
                g.finish_port_relocate()
                event.accept()
                return
            if g._wire_src is not None:
                g.finish_wire(event.scenePos())
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.card.graph is None:
            return
        menu = QMenu()
        menu.addAction(f"{short_service(self.service)} — move to:").setEnabled(False)
        for s in _PORT_SIDES:
            act = menu.addAction(f"  {_SIDE_LABEL[s]}")
            act.setData(s)
            if s == self.side:
                act.setCheckable(True)
                act.setChecked(True)
        chosen = menu.exec(event.screenPos())
        if chosen is not None and chosen.data():
            self.card.graph.set_single_port_side(self, str(chosen.data()))
        event.accept()


class ProcessCard(QGraphicsItem):
    WIDTH = 200
    # External MCU card: compact (no port list / tutorial lines)
    EXT_WIDTH = 180
    EXT_HEIGHT = 56
    LINE = 16
    HEADER = 28  # title only

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
        port_sides: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.process_name = name
        self.provides = list(provides)
        self.requires = list(requires)
        self.graph = graph
        self.out_side = _norm_side(out_side, "right")
        self.in_side = _norm_side(in_side, "left")
        # Keys: "out:Trajectory" / "in:Trajectory"（同名透传端口互不影响）
        # 兼容旧键 "Trajectory"（无方向前缀，两侧共用，读时仍生效）
        self.port_sides: dict[str, str] = {}
        for k, v in (port_sides or {}).items():
            if not str(v).strip():
                continue
            key = str(k).strip()
            if ":" in key:
                d, _, svc_name = key.partition(":")
                d = d.strip().lower()
                svc_name = short_service(svc_name)
                if d in ("in", "out") and svc_name:
                    self.port_sides[f"{d}:{svc_name}"] = _norm_side(
                        v, self.out_side if d == "out" else self.in_side
                    )
            else:
                self.port_sides[short_service(key)] = _norm_side(v, self.out_side)
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

    @staticmethod
    def port_side_key(direction: str, service: str) -> str:
        d = "out" if direction == "out" else "in"
        return f"{d}:{short_service(service)}"

    def port_side_for(self, service: str, direction: str) -> str:
        key = short_service(service)
        dir_key = self.port_side_key(direction, service)
        if dir_key in self.port_sides:
            return _norm_side(
                self.port_sides[dir_key],
                self.out_side if direction == "out" else self.in_side,
            )
        # 旧版无方向前缀：两侧曾共用一个键
        if key in self.port_sides:
            return _norm_side(
                self.port_sides[key],
                self.out_side if direction == "out" else self.in_side,
            )
        return self.out_side if direction == "out" else self.in_side

    def set_port_sides(self, *, out_side: str | None = None, in_side: str | None = None) -> None:
        if out_side is not None:
            self.out_side = _norm_side(out_side, self.out_side)
        if in_side is not None:
            self.in_side = _norm_side(in_side, self.in_side)
        self._rebuild_ports()
        self.prepareGeometryChange()
        self.update()
        for e in list(self._edges):
            if hasattr(e, "update_path"):
                e.update_path()

    def _compute_height(self) -> float:
        # External MCU: compact block, no signal ports on canvas
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

        from collections import defaultdict

        outs = self._visible_provides()
        ins = self._visible_requires()
        out_by_side: dict[str, list[str]] = defaultdict(list)
        in_by_side: dict[str, list[str]] = defaultdict(list)
        for svc in outs:
            out_by_side[self.port_side_for(svc, "out")].append(svc)
        for svc in ins:
            in_by_side[self.port_side_for(svc, "in")].append(svc)

        for side, svcs in out_by_side.items():
            for i, svc in enumerate(svcs):
                port = PortItem(self, "out", svc, i, side=side)
                port.setPos(self._place_on_side(side, i, len(svcs)))
                self._out_ports.append(port)
        for side, svcs in in_by_side.items():
            for i, svc in enumerate(svcs):
                port = PortItem(self, "in", svc, i, side=side)
                port.setPos(self._place_on_side(side, i, len(svcs)))
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
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )

        if external:
            return

        font_small = QFont()
        font_small.setPointSize(8)
        painter.setFont(font_small)
        y = self.HEADER
        outs = self._visible_provides()
        ins = self._visible_requires()
        # Color = direction; unlinked ports get a trailing !
        # 列表顺序：In 在上、Out 在下（与常见「输入→处理→输出」阅读方向一致）
        out_head = QColor("#145a32") if self._dimmed else QColor("#00e676")
        out_ok = QColor("#1e8449") if self._dimmed else QColor("#69f0ae")
        in_head = QColor("#6e2c00") if self._dimmed else QColor("#ff9100")
        in_ok = QColor("#935116") if self._dimmed else QColor("#ffb74d")
        painter.setPen(in_head)
        painter.drawText(8, y + 12, "In")
        y += self.LINE
        for svc in ins:
            linked = self.is_port_linked("in", svc)
            painter.setPen(in_ok)
            mark = "" if linked else " !"
            painter.drawText(16, y + 12, f"{short_service(svc)}{mark}")
            y += self.LINE
        painter.setPen(out_head)
        painter.drawText(8, y + 12, "Out")
        y += self.LINE
        for svc in outs:
            linked = self.is_port_linked("out", svc)
            painter.setPen(out_ok)
            mark = "" if linked else " !"
            painter.drawText(16, y + 12, f"{short_service(svc)}{mark}")
            y += self.LINE

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

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.graph is not None
            and self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        ):
            self.graph.begin_card_drag(self)
        super().mousePressEvent(event)

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
        self.setToolTip("Drag to adjust route (Ctrl+S to save)")
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
        src_port = self.src.out_port_for_service(self.service)
        dst_port = self.dst.in_port_for_service(self.service)
        src_side = (
            src_port.side
            if src_port is not None
            else self.src.port_side_for(self.service, "out")
        )
        dst_side = (
            dst_port.side
            if dst_port is not None
            else self.dst.port_side_for(self.service, "in")
        )
        p1 = self._leave_point(p0, src_side, dist, spread)
        p2 = self._approach_point(p3, dst_side, dist, spread)

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
        src_port = self.src.out_port_for_service(self.service)
        dst_port = self.dst.in_port_for_service(self.service)
        src_side = (
            src_port.side
            if src_port is not None
            else self.src.port_side_for(self.service, "out")
        )
        dst_side = (
            dst_port.side
            if dst_port is not None
            else self.dst.port_side_for(self.service, "in")
        )
        p1 = self._leave_point(p0, src_side, dist, spread)
        p2 = self._approach_point(p3, dst_side, dist, spread)
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
    """External MCU ↔ gateway boundary link (services stay in yaml)."""

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
        label = "gateway"
        if services:
            shorts = sorted({short_service(s) for s in services})
            label = " / ".join(shorts[:3])
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
        # fit 后上下左右居中（勿 AlignTop，否则会偏上）
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # AsNeeded：内容已 fit 时不占滚动条；放大后仍可拖动画布
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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


class PortEditDialog(QDialog):
    """Double-click block: add/remove In/Out ports (Simulink-like). Side layout = drag ports on canvas."""

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
        self.resize(480, 480)
        self._active: QListWidget | None = None

        self._provides = QListWidget()
        self._requires = QListWidget()
        for p in provides:
            self._provides.addItem(canon_service(p))
        for r in requires:
            self._requires.addItem(canon_service(r))
        # In / Out 互斥选中：同一时刻只有一个列表有 current item
        self._provides.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._requires.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._provides.itemSelectionChanged.connect(
            lambda: self._on_list_selected(self._provides)
        )
        self._requires.itemSelectionChanged.connect(
            lambda: self._on_list_selected(self._requires)
        )
        self._provides.itemClicked.connect(lambda *_: self._set_active(self._provides))
        self._requires.itemClicked.connect(lambda *_: self._set_active(self._requires))

        self._svc = QComboBox()
        self._svc.setEditable(True)
        for c in candidates:
            self._svc.addItem(canon_service(c) if not c.startswith("services.") else c)
        if not candidates:
            self._svc.addItem("services.semantic.")

        layout = QVBoxLayout(self)
        # In 在上、Out 在下（与画布卡片一致）
        layout.addWidget(QLabel("In (requires)"))
        layout.addWidget(self._requires)
        layout.addWidget(QLabel("Out (provides)"))
        layout.addWidget(self._provides)

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
        row.addWidget(btn_in)
        row.addWidget(btn_out)
        row.addWidget(btn_del)
        row.addWidget(btn_swap)
        layout.addLayout(row)

        hint = QLabel(
            "提示：In / Out 只能选中一侧；也可从候选下拉选 hpp 类型名；"
            "手输短名会规范为 services.semantic.*。"
            "\n透传模块（如 gateway）In/Out 可同名（如 Trajectory）；"
            "改边/调序互不影响。若画布上易混淆，可起不同短名，但连线类型需一致。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:11px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_active(self, lst: QListWidget) -> None:
        self._active = lst

    def _on_list_selected(self, lst: QListWidget) -> None:
        """Selecting in one list clears the other — only one side active."""
        if not lst.selectedItems():
            return
        other = self._requires if lst is self._provides else self._provides
        other.blockSignals(True)
        other.clearSelection()
        other.setCurrentRow(-1)
        other.blockSignals(False)
        self._active = lst
        lst.setFocus(Qt.FocusReason.MouseFocusReason)

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
        lst.setCurrentRow(lst.count() - 1)
        self._on_list_selected(lst)

    def _active_list(self) -> QListWidget | None:
        if self._active is not None and self._active.currentRow() >= 0:
            return self._active
        if self._requires.currentRow() >= 0:
            return self._requires
        if self._provides.currentRow() >= 0:
            return self._provides
        return None

    def _delete_selected(self) -> None:
        lst = self._active_list()
        if lst is None:
            return
        row = lst.currentRow()
        if row >= 0:
            lst.takeItem(row)

    def _swap_direction(self) -> None:
        lst = self._active_list()
        if lst is None:
            return
        row = lst.currentRow()
        if row < 0:
            return
        item = lst.takeItem(row)
        if item is None:
            return
        dst = self._requires if lst is self._provides else self._provides
        dst.addItem(item.text())
        dst.setCurrentRow(dst.count() - 1)
        self._on_list_selected(dst)

    def result_ports(self) -> tuple[list[str], list[str]]:
        provides = [self._provides.item(i).text() for i in range(self._provides.count())]
        requires = [self._requires.item(i).text() for i in range(self._requires.count())]
        return provides, requires


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
        self._dir_in.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._dir_out)
        bg.addButton(self._dir_in)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_in)
        dir_row.addWidget(self._dir_out)
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
        self._domain.addItem("ap_linux — AP Linux (default)", "ap_linux")
        self._domain.addItem("host — desktop / sim PC", "host")
        self._domain.setCurrentIndex(0)
        self._domain.setToolTip(
            "compute_domain: where the process runs.\n"
            "Written to wiring.yaml → Verify → gf.sor.json deployments[]."
        )
        hint = QLabel(
            "compute_domain is a wiring field (into SOR).\n"
            "For an external MCU node: blank canvas → right-click → Add external MCU."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:11px;")
        form.addRow("进程名", self._name)
        form.addRow("compute_domain", self._domain)
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
        self._wire_forbid_mark: QGraphicsSimpleTextItem | None = None
        self._reloc_port: PortItem | None = None
        self._reloc_card_was_movable = True
        # 是否持有 QApplication override cursor（压过 PortItem 自带光标）
        self._app_cursor_pushed = False
        # process_name -> (x, y); survives rebuild so edits don't reset layout
        self._layout_pos: dict[str, tuple[float, float]] = {}
        # 打开项目时 Tab 可能尚未显示，viewport=0 → fitInView 无效；显示后再 fit
        self._need_fit_on_show = False
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._undo_suppress = False
        self._drag_undo_armed = False
        self._undo_limit = 40

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
            "Out=绿 · In=橙 · ! =未连\n"
            "拖拽连线 · Ctrl+拖改边/同边调序 · Ctrl+Z/Y 撤销"
        )
        self._legend.setWordWrap(True)
        self._legend.setStyleSheet("color: #a9cfc0; font-size: 11px;")

        flows_page = QWidget()
        flows_l = QVBoxLayout(flows_page)
        flows_l.setContentsMargins(4, 4, 4, 4)
        flows_l.addWidget(self._legend)
        flows_l.addWidget(self._search)
        flows_l.addWidget(self._search_hits)
        flows_l.addWidget(QLabel("dataflows"))
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
        self._right_panel.setMinimumWidth(280)
        self._right_panel.setMaximumWidth(420)
        self._right_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )

        self._btn_toggle_right = QToolButton()
        # 面板在右：展开时 ▶=收起；收起后 ◀=展开。默认收起，画布优先。
        self._btn_toggle_right.setText("◀")
        self._btn_toggle_right.setToolTip("折叠 / 展开右侧面板（连线 + Lineage）")
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
        self.flush_canvas()
        self._undo_stack.append(copy.deepcopy(self._session.wiring))
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def begin_card_drag(self, card: ProcessCard) -> None:
        """Arm one undo snapshot per drag gesture."""
        if self._drag_undo_armed:
            return
        self._push_undo()
        self._drag_undo_armed = True

    def undo(self) -> None:
        if not self._undo_stack or self._session is None:
            return
        self.flush_canvas()
        self._redo_stack.append(copy.deepcopy(self._session.wiring))
        snap = self._undo_stack.pop()
        self._apply_wiring_snapshot(snap)
        self.changed.emit()

    def redo(self) -> None:
        if not self._redo_stack or self._session is None:
            return
        self.flush_canvas()
        self._undo_stack.append(copy.deepcopy(self._session.wiring))
        snap = self._redo_stack.pop()
        self._apply_wiring_snapshot(snap)
        self.changed.emit()

    def _apply_wiring_snapshot(self, snap: dict[str, Any]) -> None:
        assert self._session is not None
        self._undo_suppress = True
        try:
            self._session.wiring = snap
            self._session.dirty_wiring = True
            # Load positions from snapshot; rebuild must NOT overwrite from live cards
            # (those still hold post-drag coords until scene.clear).
            self._layout_pos.clear()
            nodes = (snap.get("canvas") or {}).get("nodes") or {}
            if isinstance(nodes, dict):
                for name, ui in nodes.items():
                    if isinstance(ui, dict) and "x" in ui and "y" in ui:
                        self._layout_pos[str(name)] = (float(ui["x"]), float(ui["y"]))
            self.rebuild(fit_view=False, keep_layout_pos=True)
        finally:
            self._undo_suppress = False
            self._drag_undo_armed = False

    def clear_undo_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._drag_undo_armed = False

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
        self.clear_undo_history()
        self._last_topo: str | None = None
        self.rebuild(fit_view=True)

    def _topology(self) -> str:
        if not self._session:
            return "ap_only"
        req = getattr(self._session, "req", None) or {}
        topo = str(req.get("topology") or self._session.wiring.get("topology") or "ap_only")
        return topo.strip() or "ap_only"

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
            self._session.set_node_ui(
                card.process_name,
                x=round(p.x(), 1),
                y=round(p.y(), 1),
                out_side=card.out_side,
                in_side=card.in_side,
                port_sides=dict(card.port_sides) if card.port_sides else None,
                kind=card.kind if card.kind != "process" else None,
                label=card.label or None,
            )
            self.changed.emit()
        self._refresh_scene_rect()
        self._drag_undo_armed = False
        # Drop ScrollHandDrag "closed hand" residual after item drag.
        self._view.viewport().unsetCursor()

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
        """Illegal drop: red ✕ near tip (keep hand cursor — no ForbiddenCursor)."""
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
            ok = (
                target is not src
                and target.direction != src.direction
                and target.card is not src.card
            )
        # Legal → green; illegal → red dash + ✕; searching → yellow dash. Cursor stays hand.
        if ok is True:
            pen = QPen(QColor("#2ecc71"), 2.5, Qt.PenStyle.SolidLine)
        elif ok is False:
            pen = QPen(QColor("#c0392b"), 2.8, Qt.PenStyle.DashLine)
        else:
            pen = QPen(QColor("#f7dc6f"), 2.0, Qt.PenStyle.DashLine)
        self._wire_line.setPen(pen)
        self._set_wire_forbid_mark(scene_pos if ok is False else None)

    def finish_wire(self, scene_pos: QPointF) -> None:
        src = self._wire_src
        # hit-test before cancel clears the preview line
        target = self._port_at(scene_pos)
        self.cancel_wire()
        if src is None or not self._session:
            return
        if target is None or target.direction == src.direction:
            return  # need Out↔In pair (either drag direction)
        if target.card is src.card:
            QMessageBox.information(self, "连线", "不能连到同一模块")
            return

        out_port = src if src.direction == "out" else target
        in_port = target if src.direction == "out" else src

        self._push_undo()
        out_svc = canon_service(out_port.service)
        in_svc = (in_port.service or "").strip()
        # Simulink-like: connection carries the Out signal; In port name follows Out.
        if not in_svc:
            new_req = list(in_port.card.requires) + [out_svc]
            self._session.set_ports(
                in_port.card.process_name, list(in_port.card.provides), new_req
            )
        elif short_service(in_svc) != short_service(out_svc):
            new_req = [
                out_svc if short_service(r) == short_service(in_svc) else r
                for r in in_port.card.requires
            ]
            self._session.set_ports(
                in_port.card.process_name, list(in_port.card.provides), new_req
            )

        ok = self._session.add_dataflow(
            out_port.card.process_name,
            out_svc,
            in_port.card.process_name,
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
        peers = self._ports_on_side_ordered(
            port.card, port.direction, port.side, exclude=None
        )
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

    def _ports_on_side_ordered(
        self,
        card: ProcessCard,
        direction: str,
        side: str,
        *,
        exclude: PortItem | None = None,
    ) -> list[PortItem]:
        """Same-side peers in provides/requires order (matches apply / rebuild)."""
        ex_key = short_service(exclude.service) if exclude is not None else ""
        port_map = {
            short_service(p.service): p
            for p in (card._out_ports if direction == "out" else card._in_ports)
        }
        out: list[PortItem] = []
        for svc in self._services_list(card, direction):
            key = short_service(svc)
            if ex_key and key == ex_key:
                continue
            if card.port_side_for(svc, direction) != side:
                continue
            p = port_map.get(key)
            if p is not None:
                out.append(p)
        return out

    def _insert_index_on_side(
        self, port: PortItem, side: str, scene_pos: QPointF
    ) -> int:
        """Insert index among same-side peers (provides order, not Y-sort)."""
        card = port.card
        local = card.mapFromScene(scene_pos)
        peers = self._ports_on_side_ordered(
            card, port.direction, side, exclude=port
        )
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
        direction = moving.direction
        groups: dict[str, list[PortItem]] = defaultdict(list)
        for svc in self._services_list(card, direction):
            key = short_service(svc)
            if key == short_service(moving.service):
                continue
            side = card.port_side_for(svc, direction)
            port_map = {
                short_service(p.service): p
                for p in (
                    card._out_ports if direction == "out" else card._in_ports
                )
            }
            p = port_map.get(key)
            if p is not None:
                groups[side].append(p)
        dest = list(groups.get(new_side, []))
        new_index = max(0, min(int(new_index), len(dest)))
        dest.insert(new_index, moving)
        groups[new_side] = dest
        for side, plist in groups.items():
            n = len(plist)
            for i, p in enumerate(plist):
                p.side = side
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
            self.refresh_port_hover_cursor()

    def apply_port_side_and_order(
        self,
        port: PortItem,
        new_side: str,
        new_index: int,
        *,
        card: ProcessCard | None = None,
    ) -> None:
        """Persist port edge + order in provides/requires (reduces crossings)."""
        if not self._session:
            return
        card = card if card is not None else port.card
        if not _qt_alive(card):
            return
        # Capture identity before any rebuild destroys PortItem
        direction = port.direction
        moved_svc = port.service
        key = short_service(moved_svc)
        side_n = _norm_side(new_side, "right" if direction == "out" else "left")
        dir_key = ProcessCard.port_side_key(direction, moved_svc)
        card.port_sides[dir_key] = side_n
        # 去掉旧版无方向键，避免同名 In/Out 再被绑在一起
        card.port_sides.pop(key, None)
        self._session.set_node_ui(
            card.process_name, port_sides=dict(card.port_sides)
        )

        def side_of(svc: str) -> str:
            return card.port_side_for(svc, direction)

        if direction == "out":
            new_prov = self._reorder_services_on_side(
                list(card.provides), moved_svc, side_n, new_index, side_of
            )
            new_req = list(card.requires)
            # 仅调序/改边，不剪 dataflow（避免误删 + 加速）
            self._session.set_ports(
                card.process_name, new_prov, new_req, prune_flows=False
            )
            card.set_ports(new_prov, new_req)
        else:
            new_prov = list(card.provides)
            new_req = self._reorder_services_on_side(
                list(card.requires), moved_svc, side_n, new_index, side_of
            )
            self._session.set_ports(
                card.process_name, new_prov, new_req, prune_flows=False
            )
            card.set_ports(new_prov, new_req)
        for e in list(card._edges):
            if hasattr(e, "update_path"):
                e.update_path()
        self._drag_undo_armed = False
        self.changed.emit()

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
        act_ext = menu.addAction("Add external MCU…")
        act_ext.setEnabled(self._show_external_mcu())
        if not self._show_external_mcu():
            act_ext.setToolTip(
                "当前拓扑为仅 AP。请先改为「AP + MCU CP」；"
                "对外控制信号可挂在 gateway 端口上。"
            )
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
        act_focus_mcu = menu.addAction("Select MCU")
        act_focus_gw = menu.addAction("Select gateway")
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
        self._push_undo()
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
            act_del = menu.addAction("Delete external MCU")
            chosen = menu.exec(global_pos)
            if chosen is act_del:
                self.delete_node(card)
            return
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

    def set_single_port_side(self, port: PortItem, side: str) -> None:
        """Move one Out/In port (e.g. EgoMotion only) to another card edge."""
        # Append to end of that side (context-menu path).
        card = port.card
        peers = [
            p
            for p in (
                card._out_ports if port.direction == "out" else card._in_ports
            )
            if p is not port
            and card.port_side_for(p.service, port.direction) == _norm_side(side, port.side)
        ]
        self.apply_port_side_and_order(port, side, len(peers))

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
        self._push_undo()
        self._session.upsert_deployment(name, compute_domain=domain, provides=[], requires=[])
        self.rebuild(fit_view=True)
        self.changed.emit()

    def add_external_mcu_node(self) -> None:
        """Add external MCU boundary node (VehicleBus / Trajectory via gateway)."""
        if not self._session:
            return
        if not self._show_external_mcu():
            QMessageBox.information(
                self,
                "外部 MCU",
                "当前拓扑为「仅 AP（无 MCU）」，不显示 MCU 节点。\n"
                "请先在 SKU 将拓扑改为「AP + MCU CP」。\n"
                "对外控制信号（如 VehicleBus / Trajectory）可直接挂在 gateway 等模块端口上。",
            )
            return
        name = "external.vehicle_mcu"
        if name in self._nodes:
            QMessageBox.information(self, "外部节点", f"已存在：{name}")
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
        QMessageBox.information(self, "external MCU", f"Added {name}")

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
                port_sides=dict(card.port_sides) if card.port_sides else None,
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
        self._push_undo()
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
                "external MCU",
                "No editable ports on canvas (boundary link to gateway only).",
            )
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
        self._push_undo()
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

    def rebuild(
        self,
        *,
        fit_view: bool = False,
        reset_layout: bool = False,
        keep_layout_pos: bool = False,
    ) -> None:
        self.cancel_wire()
        # Snapshot positions before C++ items are destroyed — unless caller
        # already filled _layout_pos (undo/redo) or asked to drop layout.
        if reset_layout:
            self._layout_pos.clear()
        elif not keep_layout_pos:
            for name, card in list(self._nodes.items()):
                if _qt_alive(card):
                    p = card.pos()
                    self._layout_pos[name] = (p.x(), p.y())

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
        show_mcu = self._show_external_mcu()
        ap_x0 = 120.0 if show_mcu else 40.0
        auto_slots: dict[str, tuple[float, float]] = {}
        ext_i = 0
        for depth, names in sorted(cols.items()):
            for i, name in enumerate(names):
                if is_external_node(process=name):
                    # MCU 默认在最左，避免挤进 AP 列被裁切
                    auto_slots[name] = (-280.0, 40.0 + ext_i * 120.0)
                    ext_i += 1
                else:
                    # 有 MCU 时 AP 列右移留空；仅 AP 拓扑则贴左
                    auto_slots[name] = (ap_x0 + depth * 280.0, 40.0 + i * 240.0)

        for name in ordered:
            d = dep_map.get(name) or {}
            provides = [str(x) for x in (d.get("provides") or [])]
            requires = [str(x) for x in (d.get("requires") or [])]
            ui = self._session.node_ui(name)
            kind = str(ui.get("kind") or "")
            if is_external_node(kind=kind, process=name) and not kind:
                kind = "external"
            # ap_only：不画 MCU 卡片；YAML/dataflow 仍保留，gateway 对外端口可见
            if is_external_node(kind=kind, process=name) and not show_mcu:
                continue
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
            raw_ps = ui.get("port_sides") if isinstance(ui.get("port_sides"), dict) else {}
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
                port_sides={str(k): str(v) for k, v in raw_ps.items()},
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
            # External-MCU flows: one boundary link on canvas; yaml keeps services
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
            pitem = QListWidgetItem(f"[boundary] {mcu_name} ↔ {gw_name}")
            pitem.setData(
                Qt.ItemDataRole.UserRole, ("peer", len(self._peers) - 1)
            )
            self._flow_list.addItem(pitem)

        provided_by: dict[str, list[str]] = {}
        for name, card in self._nodes.items():
            for p in card.provides:
                provided_by.setdefault(short_service(p), []).append(name)

        # 仅当某 In 端口「完全没有」入边时才提示缺失；
        # External MCU has no missing-edge dashes (peer link covers the boundary).
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
        self._last_topo = self._topology()

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
