"""Animated DAG view: topology + highlight current playhead event only."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.architect import dag_from_sor
from gf_gmt.gui.session_model import SessionEvent, SessionModel


class AnimDagView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hint = QLabel(
            "动画 DAG：只点亮当前 playhead 一条事件。"
            "单跳=橙边；fan-out（同服务多订阅）=蓝边 + 「FAN」标签，"
            "发布端深橙、订阅端浅蓝——同一次发布的多条边会一起亮。"
        )
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color:#555;")
        self._activity = QLabel("当前：—")
        self._activity.setWordWrap(True)
        self._activity.setStyleSheet("color:#333; font-weight:600;")
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHints(self._view.renderHints())
        lay = QVBoxLayout(self)
        lay.addWidget(self._hint)
        lay.addWidget(self._activity)
        lay.addWidget(self._view)

        self._node_items: dict[str, QGraphicsEllipseItem] = {}
        # (from, to, service_short, line, label)
        self._edge_items: list[
            tuple[str, str, str, QGraphicsLineItem, QGraphicsSimpleTextItem | None]
        ] = []
        self._model: SessionModel | None = None

    def set_topology(self, sor: dict[str, Any] | None) -> None:
        self._scene.clear()
        self._node_items.clear()
        self._edge_items.clear()
        self._activity.setText("当前：—")
        if not sor:
            self._scene.addText("打开项目 SOR 后显示拓扑")
            return
        dag = dag_from_sor(sor)
        nodes = [
            str(n.get("process"))
            for n in (dag.get("nodes") or [])
            if isinstance(n, dict) and n.get("process")
        ]
        for e in dag.get("edges") or []:
            if not isinstance(e, dict):
                continue
            for key in ("from", "to"):
                p = e.get(key)
                if p and str(p) not in nodes:
                    nodes.append(str(p))
        if not nodes:
            self._scene.addText("SOR 无 deployments/dataflows")
            return

        cols = max(2, int(len(nodes) ** 0.5 + 0.9))
        spacing_x, spacing_y = 180.0, 120.0
        font = QFont()
        font.setPointSize(9)
        for i, name in enumerate(nodes):
            col, row = i % cols, i // cols
            x, y = col * spacing_x, row * spacing_y
            ellipse = QGraphicsEllipseItem(-40, -20, 80, 40)
            ellipse.setBrush(QBrush(QColor("#e8f4ea")))
            ellipse.setPen(QPen(QColor("#2e7d32"), 2))
            ellipse.setPos(x, y)
            self._scene.addItem(ellipse)
            label = QGraphicsSimpleTextItem(name)
            label.setFont(font)
            br = label.boundingRect()
            label.setPos(x - br.width() / 2, y - br.height() / 2)
            self._scene.addItem(label)
            self._node_items[name] = ellipse

        # group edges by (from,to) for slight visual offset when stacked
        pair_counts: dict[tuple[str, str], int] = {}
        pair_seen: dict[tuple[str, str], int] = {}
        raw_edges: list[tuple[str, str, str]] = []
        for e in dag.get("edges") or []:
            if not isinstance(e, dict):
                continue
            frm, to = str(e.get("from") or ""), str(e.get("to") or "")
            if frm not in self._node_items or to not in self._node_items:
                continue
            svc = str(e.get("service") or "")
            short = svc.rsplit(".", 1)[-1] if svc else ""
            raw_edges.append((frm, to, short))
            pair_counts[(frm, to)] = pair_counts.get((frm, to), 0) + 1

        # precompute which services are fan-out (same short → ≥2 edges)
        short_counts: dict[str, int] = {}
        for _frm, _to, short in raw_edges:
            if short:
                short_counts[short] = short_counts.get(short, 0) + 1

        label_font = QFont()
        label_font.setPointSize(8)
        for frm, to, short in raw_edges:
            a = self._node_items[frm].pos()
            b = self._node_items[to].pos()
            idx = pair_seen.get((frm, to), 0)
            pair_seen[(frm, to)] = idx + 1
            total = pair_counts[(frm, to)]
            a2, b2 = _offset_endpoints(a, b, idx, total)
            line = QGraphicsLineItem(a2.x(), a2.y(), b2.x(), b2.y())
            line.setPen(QPen(QColor("#90a4ae"), 2))
            line.setZValue(-1)
            self._scene.addItem(line)
            text_item: QGraphicsSimpleTextItem | None = None
            if short:
                mid = QPointF((a2.x() + b2.x()) / 2, (a2.y() + b2.y()) / 2)
                is_fan = short_counts.get(short, 0) > 1
                caption = f"FAN·{short}" if is_fan else short
                text_item = QGraphicsSimpleTextItem(caption)
                text_item.setFont(label_font)
                text_item.setBrush(
                    QBrush(QColor("#0277bd" if is_fan else "#546e7a"))
                )
                br = text_item.boundingRect()
                text_item.setPos(mid.x() - br.width() / 2, mid.y() - br.height() - 2)
                self._scene.addItem(text_item)
            self._edge_items.append((frm, to, short, line, text_item))

        self._view.fitInView(
            self._scene.itemsBoundingRect().adjusted(-40, -40, 40, 40),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def set_model(self, model: SessionModel | None) -> None:
        self._model = model

    def set_playhead(self, t_ns: int, *, event: SessionEvent | None = None) -> None:
        """Light only the current event (not a trailing window of many)."""
        current = event
        if current is None and self._model:
            for e in reversed(self._model.events):
                if e.t_ns <= t_ns:
                    current = e
                    break
        self._apply_current(current)

    def set_playhead_index(self, index: int) -> None:
        if self._model is None or not self._model.events:
            self._apply_current(None)
            return
        index = max(0, min(index, len(self._model.events) - 1))
        self._apply_current(self._model.events[index])

    def _apply_current(self, current: SessionEvent | None) -> None:
        active_edges: set[tuple[str, str, str]] = set()
        publishers: set[str] = set()
        subscribers: set[str] = set()
        is_fan = False

        if current is not None and current.service_short:
            matches = [
                (frm, to, short)
                for frm, to, short, _line, _lab in self._edge_items
                if short == current.service_short
            ]
            if matches:
                active_edges.update(matches)
                is_fan = len(matches) > 1
                froms = {m[0] for m in matches}
                tos = {m[1] for m in matches}
                publishers.update(froms)
                subscribers.update(tos - froms)
            elif current.from_proc and current.to_proc:
                active_edges.add(
                    (current.from_proc, current.to_proc, current.service_short)
                )
                publishers.add(current.from_proc)
                subscribers.add(current.to_proc)

        if current is not None:
            topic = current.topic or current.service_short or "?"
            if is_fan and active_edges:
                # stable order by destination name
                dests = sorted({to for _f, to, _s in active_edges})
                srcs = sorted(publishers) or sorted({f for f, _t, _s in active_edges})
                src = " / ".join(srcs)
                dest_list = " | ".join(dests)
                self._activity.setText(
                    f"当前：#{current.index} t={current.t_ns}  "
                    f"【fan-out×{len(active_edges)}】{topic}  "
                    f"{src} → [{dest_list}]"
                )
            elif current.from_proc and current.to_proc:
                self._activity.setText(
                    f"当前：#{current.index} t={current.t_ns}  "
                    f"{topic}  {current.from_proc}→{current.to_proc}"
                )
            else:
                self._activity.setText(
                    f"当前：#{current.index} t={current.t_ns}  {topic}"
                )
        else:
            self._activity.setText("当前：—")

        idle_edge = QPen(QColor("#90a4ae"), 2)
        hot_single = QPen(QColor("#e65100"), 4)
        hot_fan = QPen(QColor("#0277bd"), 4)
        idle_label = QColor("#546e7a")
        fan_label_idle = QColor("#0277bd")
        hot_label = QColor("#bf360c")
        hot_fan_label = QColor("#01579b")

        for frm, to, short, line, lab in self._edge_items:
            key = (frm, to, short)
            if key in active_edges:
                line.setPen(hot_fan if is_fan else hot_single)
                if lab is not None:
                    lab.setBrush(QBrush(hot_fan_label if is_fan else hot_label))
                    font = lab.font()
                    font.setBold(True)
                    lab.setFont(font)
            else:
                line.setPen(idle_edge)
                if lab is not None:
                    # restore FAN tint if this service is multi-edge in topology
                    fan_topo = sum(
                        1 for _a, _b, s, _l, _t in self._edge_items if s == short
                    ) > 1
                    lab.setBrush(
                        QBrush(fan_label_idle if fan_topo else idle_label)
                    )
                    font = lab.font()
                    font.setBold(False)
                    lab.setFont(font)

        idle_brush = QBrush(QColor("#e8f4ea"))
        idle_pen = QPen(QColor("#2e7d32"), 2)
        pub_brush = QBrush(QColor("#ffcc80"))  # publisher
        pub_pen = QPen(QColor("#e65100"), 3)
        sub_brush = QBrush(QColor("#b3e5fc"))  # fan-out / subscriber
        sub_pen = QPen(QColor("#0277bd"), 3)
        single_brush = QBrush(QColor("#ffe0b2"))
        single_pen = QPen(QColor("#e65100"), 3)

        active_nodes = publishers | subscribers
        for name, ellipse in self._node_items.items():
            if name not in active_nodes:
                ellipse.setBrush(idle_brush)
                ellipse.setPen(idle_pen)
            elif is_fan and name in publishers:
                ellipse.setBrush(pub_brush)
                ellipse.setPen(pub_pen)
            elif is_fan and name in subscribers:
                ellipse.setBrush(sub_brush)
                ellipse.setPen(sub_pen)
            else:
                ellipse.setBrush(single_brush)
                ellipse.setPen(single_pen)

    def flash_event(self, ev: SessionEvent | None) -> None:
        self._apply_current(ev)


def _offset_endpoints(
    a: QPointF, b: QPointF, index: int, total: int
) -> tuple[QPointF, QPointF]:
    """Nudge parallel edges apart so stacked fan-outs are readable."""
    if total <= 1:
        return a, b
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy) or 1.0
    # perpendicular unit
    px, py = -dy / length, dx / length
    # spread ±6px around center
    mid = (total - 1) / 2.0
    offset = (index - mid) * 10.0
    ox, oy = px * offset, py * offset
    return QPointF(a.x() + ox, a.y() + oy), QPointF(b.x() + ox, b.y() + oy)
