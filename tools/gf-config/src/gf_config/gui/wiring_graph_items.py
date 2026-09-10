"""Graphics items and helpers for the wiring canvas.

Owned here: ProcessCard, PortItem, EdgeCurve / ChannelEdge / MissingEdge, colors.
View / session / relocate persistence: ``wiring_graph.WiringGraphView``.
"""

from __future__ import annotations

import math
from typing import Any

import shiboken6
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
    QListWidget,
    QMenu,
)

from gf_config.core import (
    ProjectSession,
    normalize_channel_slot,
    short_service,
)
from gf_config.gui.cursors import (
    port_move_cursor,
    wire_link_cursor,
)
from gf_config.i18n import t


def _qt_alive(obj: Any) -> bool:
    """True if the wrapped C++ QObject/QGraphicsItem still exists."""
    try:
        return obj is not None and shiboken6.isValid(obj)
    except Exception:  # noqa: BLE001
        return False


# Distinct hues for “line color = source process” (dark canvas).
_PROCESS_PALETTE = (
    "#5dade2",
    "#58d68d",
    "#f5b041",
    "#af7ac5",
    "#76d7c4",
    "#f1948a",
    "#f7dc6f",
    "#85c1e9",
    "#e59866",
    "#a9cce3",
    "#d5a6e6",
    "#7dcea0",
)


def process_color(process: str) -> QColor:
    """Stable theme color per process (edge color follows Out card)."""
    name = (process or "").strip() or "?"
    h = 0
    for ch in name:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return QColor(_PROCESS_PALETTE[h % len(_PROCESS_PALETTE)])




_PORT_SIDES = ("left", "right", "top", "bottom")
_SIDE_LABEL = {"left": "left", "right": "right", "top": "top", "bottom": "bottom"}


def is_external_node(*, kind: str = "", process: str = "") -> bool:
    return kind == "external" or process.startswith("external.")


def is_frame_ingest_node(*, kind: str = "", process: str = "") -> bool:
    return ProjectSession.is_frame_ingest_process(kind=kind, process=process)


def is_camera_source(*, kind: str = "", process: str = "") -> bool:
    """Compat alias for frame_ingest / legacy camera.* canvas nodes."""
    return is_frame_ingest_node(kind=kind, process=process)


def port_label(svc: str) -> str:
    """Display name: keep full gf.channel.* slot; SOA uses short service."""
    ch = normalize_channel_slot(svc or "")
    if ch:
        return ch
    return short_service(svc)


def port_link_key(svc: str) -> str:
    ch = normalize_channel_slot(svc or "")
    if ch:
        return ch
    return short_service(svc)


def _norm_side(side: str | None, default: str) -> str:
    s = (side or default).strip().lower()
    return s if s in _PORT_SIDES else default


def _qpoint(x: float, y: float) -> QPointF:
    return QPointF(x, y)


class DeselectableListWidget(QListWidget):
    """Click empty area → clear current row (no sticky last selection)."""

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.itemAt(event.position().toPoint()) is None:
            self.clearSelection()
            self.setCurrentRow(-1)
            event.accept()
            return
        super().mousePressEvent(event)


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


def append_chevron(path: QPainterPath, apex: QPointF, ux: float, uy: float, *, arrow_len: float = 10.0, arrow_w: float = 5.0) -> None:
    """Open chevron arrow at apex, oriented by unit direction (ux, uy)."""
    px, py = -uy, ux
    base = QPointF(apex.x() - ux * arrow_len, apex.y() - uy * arrow_len)
    path.moveTo(apex)
    path.lineTo(QPointF(base.x() + px * arrow_w, base.y() + py * arrow_w))
    path.moveTo(apex)
    path.lineTo(QPointF(base.x() - px * arrow_w, base.y() - py * arrow_w))


class PortItem(QGraphicsEllipseItem):
    """Out (green) / In (orange). Bare drag = wire; Ctrl+drag = side + order (Out/In may interleave)."""

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
        # Out above In so same-side stack (legacy layouts) still shows green tip.
        self.setZValue(21 if direction == "out" else 20)
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
            tip = t("linked")
            pen = QPen(border, 2.5 if selected else 1.5)
        else:
            border = QColor("#922b21")
            tip = t("unlinked")
            pen = QPen(border, 2.0 if selected else 1.6)
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setBrush(QBrush(fill))
        self.setPen(pen)
        side_l = _SIDE_LABEL.get(self.side, self.side)
        # 裸拖连线（Out↔In）；Ctrl+拖 = 改边 / 同边调序（减交叉）
        self.setToolTip(
            f"{tip_dir}: {port_label(self.service)} ({tip} · {side_l})\n"
            + t("拖拽连线 · Ctrl+拖：改边或同边调序 · 右键选边")
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
            # 裸拖（Out/In）→ 拉线；Ctrl+拖拽 → 改边 / 同边调序（Out↔In 可交错）
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
        port_slot_order: dict[str, list[str]] | None = None,
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
        # Same-side Out/In interleave: side -> ["out:Foo", "in:Bar", ...]
        self.port_slot_order: dict[str, list[str]] = {}
        for side, keys in (port_slot_order or {}).items():
            side_n = str(side).strip().lower()
            if side_n not in ("left", "right", "top", "bottom"):
                continue
            cleaned: list[str] = []
            for raw in keys or []:
                sk = ProcessCard.normalize_slot_key(str(raw))
                if sk:
                    cleaned.append(sk)
            if cleaned:
                self.port_slot_order[side_n] = cleaned
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
        # 已有 dataflow / channel_flow 的 Out / In（SOA 用短名；GfChannel 用全槽名）
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
        """按 dataflow / channel_flow 标记端口是否已连；未连线文字/圆点为红。"""
        self._linked_out = {port_link_key(s) for s in linked_out}
        self._linked_in = {port_link_key(s) for s in linked_in}
        if _qt_alive(self):
            self.update()
            for p in self._out_ports + self._in_ports:
                if _qt_alive(p):
                    p._apply_brush()

    def is_port_linked(self, direction: str, service: str) -> bool:
        key = port_link_key(service)
        if direction == "out":
            return key in self._linked_out
        return key in self._linked_in

    def is_external(self) -> bool:
        return is_external_node(kind=self.kind, process=self.process_name)

    def is_camera(self) -> bool:
        return self.is_frame_ingest()

    def is_frame_ingest(self) -> bool:
        return is_frame_ingest_node(kind=self.kind, process=self.process_name)

    @property
    def card_width(self) -> float:
        if self.is_external():
            return float(self.EXT_WIDTH)
        if self.is_frame_ingest():
            return 220.0
        return float(self.WIDTH)

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
    def slot_key(direction: str, service: str) -> str:
        d = "out" if direction == "out" else "in"
        return f"{d}:{short_service(service)}"

    @staticmethod
    def normalize_slot_key(raw: str) -> str | None:
        key = str(raw).strip()
        if ":" not in key:
            return None
        d, _, svc = key.partition(":")
        d = d.strip().lower()
        svc = short_service(svc)
        if d not in ("in", "out") or not svc:
            return None
        return f"{d}:{svc}"

    @staticmethod
    def parse_slot_key(raw: str) -> tuple[str, str] | None:
        sk = ProcessCard.normalize_slot_key(raw)
        if sk is None:
            return None
        d, _, svc = sk.partition(":")
        return d, svc

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
        # CameraSource / frame_ingest: title + Out only (GfChannel slot)
        if self.is_frame_ingest():
            n = 1 + max(len(self._visible_provides()), 1)
            return self.HEADER + n * self.LINE + 12
        n = (
            1
            + max(len(self._visible_requires()), 1)
            + 1
            + max(len(self._visible_provides()), 1)
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

        # Out+In on the same side share one slot ladder; order may interleave
        # (Ctrl+drag). Default remains outs then ins when no saved order.
        sides = set(out_by_side) | set(in_by_side)
        for side in sides:
            slots = self._slots_for_side(side, out_by_side, in_by_side)
            # Keep saved order in sync with live ports (drop stale / append new).
            self.port_slot_order[side] = [
                self.slot_key(d, svc) for d, svc in slots
            ]
            n = len(slots)
            for i, (direction, svc) in enumerate(slots):
                port = PortItem(self, direction, svc, i, side=side)
                port.setPos(self._place_on_side(side, i, n))
                if direction == "out":
                    self._out_ports.append(port)
                else:
                    self._in_ports.append(port)

    def _slots_for_side(
        self,
        side: str,
        out_by_side: dict[str, list[str]],
        in_by_side: dict[str, list[str]],
    ) -> list[tuple[str, str]]:
        outs = list(out_by_side.get(side, []))
        ins = list(in_by_side.get(side, []))
        avail: dict[tuple[str, str], str] = {}
        for svc in outs:
            avail[("out", short_service(svc))] = svc
        for svc in ins:
            avail[("in", short_service(svc))] = svc
        slots: list[tuple[str, str]] = []
        for raw in self.port_slot_order.get(side, []):
            parsed = self.parse_slot_key(raw)
            if parsed is None:
                continue
            d, sk = parsed
            full = avail.pop((d, sk), None)
            if full is not None:
                slots.append((d, full))
        for svc in outs:
            key = ("out", short_service(svc))
            if key in avail:
                slots.append(("out", avail.pop(key)))
        for svc in ins:
            key = ("in", short_service(svc))
            if key in avail:
                slots.append(("in", avail.pop(key)))
        return slots

    def out_port_for_service(self, service: str) -> PortItem | None:
        key = port_link_key(service)
        for p in self._out_ports:
            if port_link_key(p.service) == key:
                return p
        return self._out_ports[0] if self._out_ports else None

    def in_port_for_service(self, service: str) -> PortItem | None:
        key = port_link_key(service)
        for p in self._in_ports:
            if port_link_key(p.service) == key:
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
        camera = self.is_frame_ingest()

        if self._emphasis or self.isSelected():
            if external:
                fill = QColor("#3d3a1e")
            elif camera:
                fill = QColor("#1a3a4a")
            else:
                fill = QColor("#1e6b4f")
            border = QColor("#f7dc6f")
            border_w = 3.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(247, 220, 111, 50)))
            painter.drawRoundedRect(r.adjusted(-5, -5, 5, 5), 12, 12)
        elif self._dimmed:
            if external:
                fill = QColor("#1a1a14")
            elif camera:
                fill = QColor("#0f1c24")
            else:
                fill = QColor("#0f221c")
            border = QColor("#5c5346")
            border_w = 1.5
        else:
            if external:
                fill = QColor("#2a2618")
                border = QColor("#c9a227")
            elif camera:
                fill = QColor("#152832")
                border = process_color(self.process_name)
            else:
                fill = QColor("#15352c")
                border = process_color(self.process_name)
            border_w = 2

        painter.setBrush(QBrush(fill))
        pen = QPen(border, border_w)
        if external:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif camera:
            pen.setStyle(Qt.PenStyle.DashDotLine)
        painter.setPen(pen)
        painter.drawRoundedRect(r, 10, 10)

        title_c = QColor("#fff8dc") if (self._emphasis or self.isSelected()) else QColor("#eafaf1")
        if camera and not (self._emphasis or self.isSelected()):
            title_c = QColor("#d6eaf8")
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
        outs_head = QColor("#145a32") if self._dimmed else QColor("#00e676")
        out_ok = QColor("#1e8449") if self._dimmed else QColor("#69f0ae")
        if camera:
            outs_head = QColor("#1a5276") if self._dimmed else QColor("#5dade2")
            out_ok = QColor("#2874a6") if self._dimmed else QColor("#85c1e9")
            painter.setPen(outs_head)
            painter.drawText(8, y + 12, "Out · GfChannel")
            y += self.LINE
            for svc in outs:
                linked = self.is_port_linked("out", svc)
                painter.setPen(out_ok)
                mark = "" if linked else " !"
                painter.drawText(16, y + 12, f"{port_label(svc)}{mark}")
                y += self.LINE
            return

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
            painter.drawText(16, y + 12, f"{port_label(svc)}{mark}")
            y += self.LINE
        painter.setPen(out_head)
        painter.drawText(8, y + 12, "Out")
        y += self.LINE
        for svc in outs:
            linked = self.is_port_linked("out", svc)
            painter.setPen(out_ok)
            mark = "" if linked else " !"
            painter.drawText(16, y + 12, f"{port_label(svc)}{mark}")
            y += self.LINE

    def itemChange(self, change, value):  # type: ignore[no-untyped-def]
        if not _qt_alive(self):
            return value
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # 拖动中禁止 setSceneRect / ensureVisible（否则飞快 + RecursionError）
            if not self._updating_links:
                self._updating_links = True
                try:
                    touched: list[Any] = []
                    for e in self._edges:
                        if _qt_alive(e):
                            e.update_path()
                            touched.append(e)
                    # Fan spread is by dest Y among (src, service) siblings —
                    # moving this card as a sink must refresh peers too.
                    for e in touched:
                        if not isinstance(e, EdgeCurve) or e.dst is not self:
                            continue
                        for sib in e.src._edges:
                            if (
                                isinstance(sib, EdgeCurve)
                                and _qt_alive(sib)
                                and sib.src is e.src
                                and sib.service == e.service
                                and sib not in touched
                            ):
                                sib.update_path()
                                touched.append(sib)
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
            if self.is_frame_ingest():
                self.graph.edit_frame_ingest(self)
            else:
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
        self.setToolTip(t("拖拽调整路径（Ctrl+S 保存）"))
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
        self._base_color = process_color(src.process_name)
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

    def _fan_spread(self) -> float:
        """Leave/approach offset: sort siblings by destination Y (live positions)."""
        siblings = [
            e
            for e in self.src._edges
            if isinstance(e, EdgeCurve)
            and e.src is self.src
            and e.service == self.service
        ]
        if len(siblings) <= 1:
            return 0.0
        siblings.sort(
            key=lambda e: (
                float(e.dst.in_anchor(e.service).y()),
                float(e.dst.in_anchor(e.service).x()),
                e.dst.process_name,
            )
        )
        try:
            idx = siblings.index(self)
        except ValueError:
            idx = int(self.fan_index)
            n = max(1, int(self.fan_count))
        else:
            n = len(siblings)
        return (idx - (n - 1) / 2.0) * 28.0

    def update_path(self) -> None:
        p0 = self.src.out_anchor(self.service)
        p3 = self.dst.in_anchor(self.service)
        spread = self._fan_spread()
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
        apex = cubic_bezier_point(p0, p1, p2, p3, 0.68)
        tang = cubic_bezier_tangent(p0, p1, p2, p3, 0.68)
        length = math.hypot(tang.x(), tang.y()) or 1.0
        ux, uy = tang.x() / length, tang.y() / length
        append_chevron(path, apex, ux, uy)
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
        spread = self._fan_spread()
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
            self.graph._session.set_flow_route(self.flow, self.flow["route"])
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
        apex = q_point(0.68)
        tang = q_tang(0.68)
        length = math.hypot(tang.x(), tang.y()) or 1.0
        ux, uy = tang.x() / length, tang.y() / length
        append_chevron(path, apex, ux, uy)
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
        for apex, base in ((p3, mid), (p0, mid)):
            dx, dy = apex.x() - base.x(), apex.y() - base.y()
            length = math.hypot(dx, dy) or 1.0
            ux, uy = dx / length, dy / length
            append_chevron(path, apex, ux, uy, arrow_len=9.0, arrow_w=4.5)
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


class ChannelEdge(QGraphicsPathItem):
    """GfChannel camera edge (camera → consumer); not an iceoryx dataflow."""

    def __init__(
        self,
        src: ProcessCard,
        dst: ProcessCard,
        slot: str,
        flow: dict[str, Any],
        graph: WiringGraphView | None = None,
    ) -> None:
        super().__init__()
        self.src = src
        self.dst = dst
        self.slot = (slot or "").strip() or "gf.channel.front"
        self.flow = flow
        self.service = self.slot  # PortItem/anchor helpers reuse service name
        self.graph = graph
        self._base_color = QColor("#5dade2")
        self._highlight = False
        self._dimmed = False
        self._role = ""
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, False)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        src._edges.append(self)
        dst._edges.append(self)
        self._label = QGraphicsSimpleTextItem(self.slot)
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
            color = QColor("#f7dc6f")
            width = 3.2
        elif self._highlight and self._role == "out":
            color = QColor("#5dade2")
            width = 2.8
        elif self._highlight and self._role == "in":
            color = QColor("#48c9b0")
            width = 2.8
        elif self._highlight:
            color = QColor("#5dade2")
            width = 2.5
        elif self._dimmed:
            color = QColor(self._base_color)
            color.setAlpha(55)
            width = 1.2
        else:
            color = self._base_color
            width = 2.2
        pen = QPen(color, width, Qt.PenStyle.DashDotLine)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        lc = QColor("#d6eaf8") if not selected else QColor("#f7dc6f")
        if self._dimmed and not selected and not self._highlight:
            lc.setAlpha(80)
        self._label.setBrush(QBrush(lc))

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        return stroker.createStroke(self.path())

    def update_path(self) -> None:
        if not _qt_alive(self.src) or not _qt_alive(self.dst):
            return
        p0 = self.src.out_anchor(self.slot)
        p3 = self.dst.in_anchor(self.slot)
        dist = max(48.0, 0.25 * math.hypot(p3.x() - p0.x(), p3.y() - p0.y()))
        src_port = self.src.out_port_for_service(self.slot)
        dst_port = self.dst.in_port_for_service(self.slot)
        src_side = (
            src_port.side
            if src_port is not None
            else self.src.port_side_for(self.slot, "out")
        )
        dst_side = (
            dst_port.side
            if dst_port is not None
            else self.dst.port_side_for(self.slot, "in")
        )
        p1 = EdgeCurve._leave_point(p0, src_side, dist, 0.0)
        p2 = EdgeCurve._approach_point(p3, dst_side, dist, 0.0)
        path = QPainterPath(p0)
        path.cubicTo(p1, p2, p3)
        apex = cubic_bezier_point(p0, p1, p2, p3, 0.68)
        tang = cubic_bezier_tangent(p0, p1, p2, p3, 0.68)
        length = math.hypot(tang.x(), tang.y()) or 1.0
        append_chevron(path, apex, tang.x() / length, tang.y() / length)
        self.setPath(path)
        label_pt = cubic_bezier_point(p0, p1, p2, p3, 0.42)
        if self.scene() and self._label.scene() is None:
            self.scene().addItem(self._label)
        self._label.setText(self.slot)
        self._label.setPos(label_pt.x() - 28, label_pt.y() - 18)
        self._label.setZValue(2 if (self._highlight or self.isSelected()) else 1)
        self.setZValue(1 if self.isSelected() else (0 if self._highlight else -1))

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
            self.graph.show_channel_edge_menu(self, event.screenPos())
            event.accept()
            return
        super().contextMenuEvent(event)


