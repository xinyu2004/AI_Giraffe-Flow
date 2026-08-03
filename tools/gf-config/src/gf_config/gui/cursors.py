"""gf-config cursors — 系统小手 + 配套黑色四向（Ctrl）。

热点与系统 SizeAll 一样在正中，只换图形、不挪落点。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)

_move: QCursor | None = None
# 略大于系统小手，仍保持热点居中
_SIZE = 28


def wire_link_cursor() -> QCursor:
    """连线：系统黑色小手。"""
    return QCursor(Qt.CursorShape.PointingHandCursor)


def port_move_cursor() -> QCursor:
    """Ctrl 调序：黑色四向；热点在十字中心（与系统 SizeAll 同落点）。"""
    global _move
    if _move is not None:
        return _move
    # 不用 devicePixelRatio：HiDPI 下热点容易偏；固定逻辑像素更稳
    s = _SIZE
    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx = cy = s / 2.0  # 热点 = 十字中心
    arm = 7.0
    ah = 3.2
    al = 4.5

    def draw_cross(color: QColor, width: float) -> None:
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(color)
        p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
        p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        for tx, ty, ux, uy in (
            (cx, cy - arm, 0, -1),
            (cx, cy + arm, 0, 1),
            (cx - arm, cy, -1, 0),
            (cx + arm, cy, 1, 0),
        ):
            tip = QPointF(tx + ux * al * 0.35, ty + uy * al * 0.35)
            base = QPointF(tx - ux * al * 0.15, ty - uy * al * 0.15)
            px_, py_ = -uy, ux
            p.drawPolygon(
                QPolygonF(
                    [
                        tip,
                        QPointF(base.x() + px_ * ah, base.y() + py_ * ah),
                        QPointF(base.x() - px_ * ah, base.y() - py_ * ah),
                    ]
                )
            )

    draw_cross(QColor("#ffffff"), 3.2)
    draw_cross(QColor("#111111"), 1.8)
    p.end()
    hot = s // 2
    _move = QCursor(pm, hot, hot)
    return _move


def wire_forbidden_cursor() -> QCursor:
    """非法连线不换光标（画布红线 + ✕）。"""
    return wire_link_cursor()


def clear_cursor_cache() -> None:
    global _move
    _move = None
