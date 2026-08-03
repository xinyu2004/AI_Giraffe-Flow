"""gf-config canvas cursors — frozen UX (do not reinvent).

| Scene              | Cursor                                      |
|--------------------|---------------------------------------------|
| Wire / hover port  | System PointingHand                         |
| Ctrl+drag port     | Custom black 4-way; hotspot at cross center |
| Illegal wire drop  | Keep hand; wiring_graph shows red line + ✕  |
                     | (ForbiddenCursor becomes a white dot on     |
                     |  some compositors — do not use it.)         |
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap, QPolygonF

_move: QCursor | None = None
_SIZE = 28  # slightly larger than system SizeAll; hotspot stays centered


def wire_link_cursor() -> QCursor:
    """Wire link / port hover: system pointing hand."""
    return QCursor(Qt.CursorShape.PointingHandCursor)


def port_move_cursor() -> QCursor:
    """Ctrl relocate/reorder: black 4-way; hotspot = cross center (like SizeAll)."""
    global _move
    if _move is not None:
        return _move
    # Fixed logical pixels (no DPR): hotspot stays stable on HiDPI.
    s = _SIZE
    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _paint_four_way(p, s / 2.0, arm=7.0, tip_len=4.5, tip_w=3.2)
    p.end()
    hot = s // 2
    _move = QCursor(pm, hot, hot)
    return _move


def _paint_four_way(
    p: QPainter,
    c: float,
    *,
    arm: float,
    tip_len: float,
    tip_w: float,
) -> None:
    """White halo then black core so the cross stays visible on light/dark chrome."""

    def stroke(color: QColor, width: float) -> None:
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(color)
        p.drawLine(QPointF(c, c - arm), QPointF(c, c + arm))
        p.drawLine(QPointF(c - arm, c), QPointF(c + arm, c))
        for tx, ty, ux, uy in (
            (c, c - arm, 0.0, -1.0),
            (c, c + arm, 0.0, 1.0),
            (c - arm, c, -1.0, 0.0),
            (c + arm, c, 1.0, 0.0),
        ):
            tip = QPointF(tx + ux * tip_len * 0.35, ty + uy * tip_len * 0.35)
            base = QPointF(tx - ux * tip_len * 0.15, ty - uy * tip_len * 0.15)
            px_, py_ = -uy, ux
            p.drawPolygon(
                QPolygonF(
                    [
                        tip,
                        QPointF(base.x() + px_ * tip_w, base.y() + py_ * tip_w),
                        QPointF(base.x() - px_ * tip_w, base.y() - py_ * tip_w),
                    ]
                )
            )

    stroke(QColor("#ffffff"), 3.2)
    stroke(QColor("#111111"), 1.8)
