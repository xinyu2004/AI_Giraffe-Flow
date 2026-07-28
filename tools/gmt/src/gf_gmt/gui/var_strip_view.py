"""GMT 变量轨：用户添加变量；每变量一行；滚轮缩放时间窗。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.gui.session_model import SessionModel
from gf_gmt.i18n import t
from gf_gmt.measure_tag import TagRecord, load_tags, tags_path_for_session


_COLORS = (
    QColor("#1565c0"),
    QColor("#c62828"),
    QColor("#2e7d32"),
    QColor("#6a1b9a"),
    QColor("#ef6c00"),
    QColor("#00838f"),
)

_DEFAULT_ROW_H = 64
_MARGIN_L = 72  # y-axis ticks
_LABEL_W = 150  # series name
_VALUE_W = 88  # playhead value readout
_MARGIN_R = 8
_AXIS_H = 26


def _scalar_fields(data: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, val in data.items():
        name = str(key).strip()
        if not name or name in {"timestamp_ns"}:
            continue
        if isinstance(val, bool):
            out[name] = float(int(val))
        elif isinstance(val, int) and not isinstance(val, bool):
            out[name] = float(val)
        elif isinstance(val, float):
            out[name] = float(val)
    return out


def topic_series_key(topic: str, service_short: str = "") -> str:
    """Disambiguate topics that share a leaf name.

    /gf/Trajectory           → Trajectory
    /gf/planning/Trajectory  → planning.Trajectory
    """
    t = (topic or "").strip().strip("/")
    parts = [p for p in t.split("/") if p]
    if parts and parts[0] == "gf":
        parts = parts[1:]
    if len(parts) >= 2:
        return ".".join(parts)
    if len(parts) == 1:
        return parts[0]
    s = (service_short or "").strip()
    return s or "x"


def _ev_topic_key(ev: Any) -> str:
    return topic_series_key(
        str(getattr(ev, "topic", "") or ""),
        str(getattr(ev, "service_short", "") or ""),
    )


def split_series_key(key: str) -> tuple[str, str]:
    """Split 'planning.Trajectory.seq' → ('planning.Trajectory', 'seq')."""
    if "." not in key:
        return key, ""
    topic_key, field = key.rsplit(".", 1)
    return topic_key, field


def discover_available_keys(model: SessionModel | None) -> list[str]:
    """All <topic_key>.<field> keys present in session, sorted."""
    if model is None or model.empty:
        return []
    keys: set[str] = set()
    for ev in model.events:
        tkey = _ev_topic_key(ev) or "x"
        for field in _scalar_fields(ev.data):
            keys.add(f"{tkey}.{field}")
    return sorted(keys)


def series_points(model: SessionModel, key: str) -> list[tuple[int, float]]:
    topic_key, field = split_series_key(key)
    if not field:
        return []
    pts: list[tuple[int, float]] = []
    for ev in model.events:
        if _ev_topic_key(ev) != topic_key:
            continue
        scalars = _scalar_fields(ev.data)
        if field not in scalars:
            continue
        pts.append((int(ev.t_ns), float(scalars[field])))
    pts.sort(key=lambda p: p[0])
    return pts


def value_at_or_before(pts: list[tuple[int, float]], t_ns: int) -> float | None:
    """Last sample at or before t_ns (hold semantics)."""
    if not pts:
        return None
    best: float | None = None
    for t, y in pts:
        if t <= t_ns:
            best = y
        else:
            break
    return best


def _fmt_val(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v - round(v)) < 1e-9 and abs(v) < 1e12:
        return str(int(round(v)))
    return f"{v:.4g}"


def _y_range(ys: list[float]) -> tuple[float, float]:
    """Auto-scale tightly to data with small pad — never a fake 0…100."""
    ymin, ymax = min(ys), max(ys)
    if ymax <= ymin:
        pad = max(1.0, abs(ymin) * 0.05) if ymin != 0 else 1.0
        return ymin - pad, ymax + pad
    span = ymax - ymin
    pad = span * 0.08
    return ymin - pad, ymax + pad


class _MultiStripCanvas(QWidget):
    """Stacked per-variable rows + shared time axis; wheel zooms time window."""

    seek_ns_requested = Signal(object)
    selection_changed = Signal(str)  # key

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.setMouseTracking(True)
        self._model: SessionModel | None = None
        self._keys: list[str] = []
        self._play_idx = 0
        self._tags: list[TagRecord] = []
        self._view_t0: int | None = None
        self._view_t1: int | None = None
        self._row_heights: dict[str, int] = {}
        self._default_row_h = _DEFAULT_ROW_H
        self._selected_key: str | None = None
        self._resize_key: str | None = None
        self._resize_start_y = 0
        self._resize_start_h = 0

    def row_height(self, key: str) -> int:
        return self._row_heights.get(key, self._default_row_h)

    def nudge_all_row_heights(self, delta: int) -> None:
        """整体调高/调矮：所有已添加轨 + 之后新建轨的默认高度。"""
        if not hasattr(self, "_default_row_h"):
            self._default_row_h = _DEFAULT_ROW_H
        self._default_row_h = max(36, min(220, self._default_row_h + int(delta)))
        if self._keys:
            for k in self._keys:
                cur = self._row_heights.get(k, self._default_row_h)
                self._row_heights[k] = max(36, min(220, cur + int(delta)))
        self._relayout()

    def set_selected_key(self, key: str | None) -> None:
        if key and key not in self._keys:
            return
        if key == self._selected_key:
            return
        self._selected_key = key
        self.update()

    def selected_key(self) -> str | None:
        return self._selected_key

    def _total_rows_h(self) -> int:
        if not self._keys:
            return _DEFAULT_ROW_H
        return sum(self.row_height(k) for k in self._keys)

    def _relayout(self) -> None:
        self.setMinimumHeight(_AXIS_H + self._total_rows_h() + 8)
        self.update()

    def _row_at_y(self, y: float) -> tuple[int, str, int, int] | None:
        """Return (index, key, top, height) for row under y, or None."""
        top = 0
        for i, key in enumerate(self._keys):
            h = self.row_height(key)
            if top <= y < top + h:
                return i, key, top, h
            top += h
        return None

    def set_state(
        self,
        model: SessionModel | None,
        keys: list[str],
        play_idx: int,
        tags: list[TagRecord],
        *,
        keep_view: bool = True,
        fit_key: str | None = None,
    ) -> None:
        old_model = self._model
        self._model = model
        self._keys = list(keys)
        for k in self._keys:
            self._row_heights.setdefault(k, self._default_row_h)
        # drop heights for removed keys
        self._row_heights = {
            k: self._row_heights[k] for k in self._keys if k in self._row_heights
        }
        if self._selected_key not in self._keys:
            self._selected_key = self._keys[-1] if self._keys else None
        self._play_idx = play_idx
        self._tags = tags
        if (
            not keep_view
            or model is None
            or model.empty
            or old_model is None
            or old_model is not model
            or self._view_t0 is None
        ):
            self._reset_view()
        else:
            self._clamp_view()
        if fit_key:
            self.fit_series(fit_key)
            self._selected_key = fit_key
        self._relayout()

    def _full_span(self) -> tuple[int, int]:
        if self._model is None or self._model.empty:
            return 0, 1
        return int(self._model.t_min), max(
            int(self._model.t_min) + 1, int(self._model.t_max)
        )

    def _reset_view(self) -> None:
        t0, t1 = self._full_span()
        self._view_t0, self._view_t1 = t0, t1

    def fit_series(self, key: str) -> None:
        if self._model is None or self._model.empty:
            return
        pts = series_points(self._model, key)
        if not pts:
            return
        self._apply_span(pts[0][0], pts[-1][0])

    def fit_compatible_keys(self, keys: list[str] | None = None) -> None:
        if self._model is None or self._model.empty:
            return
        use = list(keys if keys is not None else self._keys)
        spans: list[tuple[str, int, int, int]] = []
        for key in use:
            pts = series_points(self._model, key)
            if not pts:
                continue
            spans.append((key, int(pts[0][0]), int(pts[-1][0]), len(pts)))
        if not spans:
            self._reset_view()
            return
        spans.sort(key=lambda x: -x[3])
        _k, r0, r1, _n = spans[0]
        ref_mid = (r0 + r1) / 2.0
        ref_span = max(1.0, float(r1 - r0))
        t0, t1 = r0, r1
        for _k, a, b, _n in spans:
            mid = (a + b) / 2.0
            if abs(mid - ref_mid) <= max(ref_span, float(b - a)) * 50:
                t0 = min(t0, a)
                t1 = max(t1, b)
        self._apply_span(t0, t1)

    def _apply_span(self, s0: int, s1: int) -> None:
        full0, full1 = self._full_span()
        if s1 <= s0:
            pad = 50_000_000
            s0, s1 = s0 - pad, s0 + pad
        else:
            pad = max(1, int((s1 - s0) * 0.05))
            s0, s1 = s0 - pad, s1 + pad
        self._view_t0 = max(full0, int(s0))
        self._view_t1 = min(full1, int(s1))
        if self._view_t1 <= self._view_t0:
            self._view_t1 = self._view_t0 + 1_000_000
        self._clamp_view()

    def _clamp_view(self) -> None:
        if self._model is None or self._model.empty:
            return
        full0, full1 = self._full_span()
        full_span = max(1, full1 - full0)
        if self._view_t0 is None or self._view_t1 is None:
            self._reset_view()
            return
        min_span = 1_000_000
        span = max(min_span, int(self._view_t1) - int(self._view_t0))
        span = min(span, full_span)
        mid = (int(self._view_t0) + int(self._view_t1)) // 2
        t0 = mid - span // 2
        t1 = t0 + span
        if t0 < full0:
            t0 = full0
            t1 = t0 + span
        if t1 > full1:
            t1 = full1
            t0 = max(full0, t1 - span)
        self._view_t0, self._view_t1 = int(t0), int(t1)

    def _view_span(self) -> tuple[int, int, int]:
        if self._view_t0 is None or self._view_t1 is None:
            self._reset_view()
        assert self._view_t0 is not None and self._view_t1 is not None
        span = max(1, int(self._view_t1) - int(self._view_t0))
        return int(self._view_t0), int(self._view_t1), span

    def _plot_left(self) -> int:
        return _LABEL_W + _MARGIN_L

    def _plot_right_margin(self) -> int:
        return _VALUE_W + _MARGIN_R

    def _x_of_f(self, t_ns: int, plot_w: int) -> float:
        t0, _, span = self._view_span()
        left = self._plot_left()
        return float(left) + (float(t_ns) - float(t0)) / float(span) * float(plot_w)

    def _t_of(self, x: float, plot_w: int) -> int:
        t0, _, span = self._view_span()
        left = self._plot_left()
        frac = max(0.0, min(1.0, (x - left) / max(1.0, float(plot_w))))
        return int(t0 + span * frac)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._model is None or self._model.empty:
            return
        full0, full1 = self._full_span()
        full_span = max(1, full1 - full0)
        _t0, _t1, span = self._view_span()
        plot_w = max(1, self.width() - self._plot_left() - self._plot_right_margin())
        anchor_t = self._t_of(event.position().x(), plot_w)
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return
        factor = 0.8 if delta > 0 else 1.25
        new_span = int(span * factor)
        new_span = max(1_000_000, min(full_span, new_span))
        left = self._plot_left()
        frac = max(0.0, min(1.0, (event.position().x() - left) / plot_w))
        new_t0 = int(anchor_t - frac * new_span)
        new_t1 = new_t0 + new_span
        if new_t0 < full0:
            new_t0 = full0
            new_t1 = new_t0 + new_span
        if new_t1 > full1:
            new_t1 = full1
            new_t0 = max(full0, new_t1 - new_span)
        self._view_t0, self._view_t1 = new_t0, new_t1
        self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self._keys:
            return
        y = float(event.position().y())
        x = float(event.position().x())
        hit = self._row_at_y(y)
        if hit is None:
            return
        _i, key, top, h = hit
        # bottom edge → start resize
        if y >= top + h - 5:
            self._resize_key = key
            self._resize_start_y = int(y)
            self._resize_start_h = h
            self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
            return
        # select row
        if key != self._selected_key:
            self._selected_key = key
            self.selection_changed.emit(key)
            self.update()
        # seek if click in plot / value area
        left = self._plot_left()
        if x >= left:
            plot_w = max(1, self.width() - left - self._plot_right_margin())
            t = self._t_of(x, plot_w)
            self.seek_ns_requested.emit(int(t))

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        y = float(event.position().y())
        if self._resize_key is not None:
            dy = int(y) - self._resize_start_y
            new_h = max(36, min(220, self._resize_start_h + dy))
            self._row_heights[self._resize_key] = new_h
            self._relayout()
            return
        hit = self._row_at_y(y)
        if hit is not None:
            _i, _key, top, h = hit
            if y >= top + h - 5:
                self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
                return
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._resize_key = None
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#f7f7f7"))
        if self._model is None or self._model.empty:
            p.setPen(QColor("#888"))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                t("Open a session, then ▼ to pick variables"),
            )
            return
        if not self._keys:
            p.setPen(QColor("#888"))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                t("No variables yet — ▼ then Add →"),
            )
            return

        left = self._plot_left()
        right_m = self._plot_right_margin()
        plot_w = max(1, self.width() - left - right_m)
        t0, t1, span = self._view_span()
        clock = self._model.clock
        play_t: int | None = None
        if 0 <= self._play_idx < len(self._model.events):
            play_t = int(self._model.events[self._play_idx].t_ns)

        axis_y = self._total_rows_h() + 4
        p.setPen(QPen(QColor("#bbb"), 1))
        p.drawLine(left, axis_y, left + plot_w, axis_y)
        for frac, align in (
            (0.0, Qt.AlignmentFlag.AlignLeft),
            (0.5, Qt.AlignmentFlag.AlignHCenter),
            (1.0, Qt.AlignmentFlag.AlignRight),
        ):
            t = t0 + int(span * frac)
            x = left + int(plot_w * frac)
            label = clock.format(t, compact=True) if clock.ready else str(t)
            p.setPen(QColor("#444"))
            p.drawText(
                x - 90 if frac > 0 else x,
                axis_y + 2,
                180,
                22,
                align | Qt.AlignmentFlag.AlignTop,
                label,
            )

        top = 0
        for i, key in enumerate(self._keys):
            row_h = self.row_height(key)
            pad_v = max(3, min(10, row_h // 10))
            plot_top = top + pad_v
            plot_h = max(8, row_h - 2 * pad_v)
            color = _COLORS[i % len(_COLORS)]
            selected = key == self._selected_key

            if selected:
                bg = QColor("#fff3e0")  # 浅橙高亮
            elif i % 2 == 0:
                bg = QColor("#ffffff")
            else:
                bg = QColor("#f0f4f8")
            p.fillRect(0, top, self.width(), row_h, bg)
            if selected:
                p.setPen(QPen(QColor("#ffb74d"), 2))
                p.drawRect(1, top + 1, self.width() - 2, row_h - 2)
            p.setPen(QPen(QColor("#c5cdd6"), 1))
            p.drawLine(0, top + row_h - 1, self.width(), top + row_h - 1)
            # resize grip hint
            p.setPen(QColor("#b0bec5"))
            mid_x = self.width() // 2
            p.drawLine(mid_x - 12, top + row_h - 3, mid_x + 12, top + row_h - 3)

            val_font = QFont(p.font())
            val_font.setBold(True)
            val_font.setPointSize(max(9, min(14, 8 + row_h // 20)))

            # name
            p.setPen(color)
            p.drawText(
                4,
                top,
                _LABEL_W - 6,
                row_h,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                key,
            )

            # plot frame
            p.setPen(QPen(QColor("#c5cdd6"), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(left, plot_top, plot_w, plot_h)

            pts = series_points(self._model, key)
            in_view = [(t, y) for t, y in pts if t0 <= t <= t1]
            cur_val = value_at_or_before(pts, play_t) if play_t is not None else None

            # right-side value readout（选中行反色，避免与行高亮同色难辨）
            vx = left + plot_w + 4
            vw = _VALUE_W - 4
            if selected:
                p.fillRect(vx, plot_top, vw, plot_h, QColor("#bf360c"))
                p.setPen(QPen(QColor("#ffe0b2"), 1))
                p.drawRect(vx, plot_top, vw, plot_h)
                p.setFont(val_font)
                p.setPen(QColor("#fff8e1"))
            else:
                p.fillRect(vx, plot_top, vw, plot_h, QColor("#fff8e1"))
                p.setPen(QPen(QColor("#e65100"), 1))
                p.drawRect(vx, plot_top, vw, plot_h)
                p.setFont(val_font)
                p.setPen(QColor("#bf360c"))
            p.drawText(
                left + plot_w + 6,
                plot_top,
                _VALUE_W - 8,
                plot_h,
                Qt.AlignmentFlag.AlignCenter,
                _fmt_val(cur_val),
            )
            p.setFont(QFont())

            p.save()
            p.setClipRect(left, plot_top, plot_w, plot_h)

            if in_view:
                # Y scale from in-view samples only (tight auto-scale)
                ys = [y for _, y in in_view]
                ymin, ymax = _y_range(ys)
                yspan = max(ymax - ymin, 1e-12)

                def y_of(val: float) -> float:
                    yn = (val - ymin) / yspan
                    return float(plot_top + plot_h) - yn * float(plot_h)

                # draw with one neighbor outside for step continuity (not for y-scale)
                idxs = [j for j, (t, _) in enumerate(pts) if t0 <= t <= t1]
                j0 = max(0, idxs[0] - 1)
                j1 = min(len(pts) - 1, idxs[-1] + 1)
                draw_pts = pts[j0 : j1 + 1]

                path = QPainterPath()
                markers: list[QPointF] = []
                prev_x: float | None = None
                prev_y: float | None = None
                for t_ns, y in draw_pts:
                    x = self._x_of_f(t_ns, plot_w)
                    yy = y_of(y)
                    if prev_x is None:
                        path.moveTo(x, yy)
                    else:
                        path.lineTo(x, prev_y if prev_y is not None else yy)
                        path.lineTo(x, yy)
                    if t0 <= t_ns <= t1:
                        markers.append(QPointF(x, yy))
                    prev_x, prev_y = x, yy

                pen = QPen(color, 2.2)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.drawPath(path)
                p.setBrush(color)
                for pt in markers:
                    p.drawEllipse(pt, 3.5, 3.5)

                p.restore()

                # Y ticks (left of plot)
                p.setPen(QColor("#555"))
                for yv, align_flag in (
                    (ymax, Qt.AlignmentFlag.AlignTop),
                    ((ymin + ymax) / 2, Qt.AlignmentFlag.AlignVCenter),
                    (ymin, Qt.AlignmentFlag.AlignBottom),
                ):
                    yy = int(y_of(yv))
                    p.drawText(
                        _LABEL_W + 2,
                        yy - 8,
                        _MARGIN_L - 4,
                        16,
                        Qt.AlignmentFlag.AlignRight | align_flag,
                        _fmt_val(yv),
                    )
                    p.setPen(QPen(QColor("#cfd8dc"), 1, Qt.PenStyle.DotLine))
                    p.drawLine(left, yy, left + plot_w, yy)
                    p.setPen(QColor("#555"))
            else:
                p.restore()
                p.setPen(QColor("#999"))
                msg = t("no samples") if not pts else t("out of view — fit row")
                p.drawText(
                    left + 8,
                    plot_top,
                    plot_w,
                    plot_h,
                    Qt.AlignmentFlag.AlignCenter,
                    msg,
                )

            for tag in self._tags:
                at = tag.at_ns()
                if at is None or at < t0 or at > t1:
                    continue
                x = int(self._x_of_f(int(at), plot_w))
                p.setPen(QPen(QColor("#ad1457"), 1))
                p.drawLine(x, plot_top, x - 4, plot_top + 8)
                p.drawLine(x, plot_top, x + 4, plot_top + 8)
                p.drawLine(x - 4, plot_top + 8, x + 4, plot_top + 8)

            if play_t is not None and t0 <= play_t <= t1:
                x = int(self._x_of_f(play_t, plot_w))
                p.setPen(QPen(QColor("#e65100"), 2))
                p.drawLine(x, plot_top, x, plot_top + plot_h)

            top += row_h


class _ArrowStrip(QWidget):
    """中间一条扁条，只画 ▲/▼，点击展开/收起（不是按钮样式）。"""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expanded = False
        self.setToolTip(t("Toggle variable picker"))

    def set_expanded(self, on: bool) -> None:
        self._expanded = bool(on)
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#eceff1"))
        p.setPen(QPen(QColor("#cfd8dc"), 1))
        p.drawLine(0, 0, self.width(), 0)
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.setPen(QColor("#607d8b"))
        font = QFont(p.font())
        font.setPointSize(11)
        p.setFont(font)
        glyph = "▲" if self._expanded else "▼"
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, glyph)

    def mousePressEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        self.clicked.emit()


class _ZoomScrollArea(QScrollArea):
    def wheelEvent(self, event: QWheelEvent) -> None:
        w = self.widget()
        if isinstance(w, _MultiStripCanvas):
            w.wheelEvent(event)
            if event.isAccepted():
                return
        super().wheelEvent(event)


class VarStripView(QWidget):
    seek_ns_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: SessionModel | None = None
        self._play_idx = 0
        self._keys: list[str] = []
        self._catalog: set[str] = set()
        self._picker_open = False

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(4)
        bar.addStretch(1)
        _row_h_btn = "QPushButton { font-size: 12px; padding: 0; }"
        self._btn_row_minus = QPushButton("▼")
        self._btn_row_minus.setFixedSize(30, 28)
        self._btn_row_minus.setStyleSheet(_row_h_btn)
        self._btn_row_minus.setToolTip(t("Shrink all rows"))
        self._btn_row_minus.clicked.connect(lambda: self._canvas.nudge_all_row_heights(-8))
        bar.addWidget(self._btn_row_minus)
        lbl_row_h = QLabel(t("Height"))
        lbl_row_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_row_h.setFixedHeight(28)
        f = lbl_row_h.font()
        f.setPointSize(max(f.pointSize(), 11) + 1)
        f.setBold(True)
        lbl_row_h.setFont(f)
        bar.addWidget(lbl_row_h)
        self._btn_row_plus = QPushButton("▲")
        self._btn_row_plus.setFixedSize(30, 28)
        self._btn_row_plus.setStyleSheet(_row_h_btn)
        self._btn_row_plus.setToolTip(t("Grow all rows"))
        self._btn_row_plus.clicked.connect(lambda: self._canvas.nudge_all_row_heights(8))
        bar.addWidget(self._btn_row_plus)
        bar.addStretch(1)

        self._avail = QListWidget()
        self._avail.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._avail.itemDoubleClicked.connect(self._on_avail_double)
        self._added = QListWidget()
        self._added.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._added.itemDoubleClicked.connect(self._on_added_double)
        self._added.currentTextChanged.connect(self._on_added_sel)

        self._btn_add = QPushButton(t("Add →"))
        self._btn_add.clicked.connect(self._on_add)
        self._btn_remove = QPushButton(t("← Remove"))
        self._btn_remove.clicked.connect(self._on_remove)

        mid = QVBoxLayout()
        mid.addStretch(1)
        mid.addWidget(self._btn_add)
        mid.addWidget(self._btn_remove)
        mid.addStretch(1)
        mid_w = QWidget()
        mid_w.setLayout(mid)

        lists = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(t("Available")))
        left_col.addWidget(self._avail, stretch=1)
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel(t("Added")))
        right_col.addWidget(self._added, stretch=1)
        left_w = QWidget()
        left_w.setLayout(left_col)
        right_w = QWidget()
        right_w.setLayout(right_col)
        lists.addWidget(left_w, stretch=2)
        lists.addWidget(mid_w)
        lists.addWidget(right_w, stretch=2)

        self._picker_panel = QWidget()
        picker_lay = QVBoxLayout(self._picker_panel)
        picker_lay.setContentsMargins(0, 2, 0, 0)
        picker_lay.addLayout(lists)
        self._picker_panel.setMinimumHeight(150)
        self._picker_panel.setMaximumHeight(220)
        self._picker_panel.setVisible(False)

        self._arrow = _ArrowStrip()
        self._arrow.clicked.connect(self._toggle_picker)

        self._canvas = _MultiStripCanvas()
        self._canvas.seek_ns_requested.connect(self.seek_ns_requested.emit)
        self._canvas.selection_changed.connect(self._on_canvas_sel)
        scroll = _ZoomScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._canvas)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        lay.addLayout(bar)
        lay.addWidget(self._picker_panel)
        lay.addWidget(self._arrow)
        lay.addWidget(scroll, stretch=1)

    def set_model(self, model: SessionModel | None) -> None:
        same = model is self._model
        self._model = model
        for k in discover_available_keys(model):
            self._catalog.add(k)
        self._refill_lists()
        self._canvas.set_state(
            self._model,
            self._keys,
            self._play_idx,
            self._tags(),
            keep_view=same,
        )
        if self._catalog and not self._keys and not same:
            self._set_picker_open(True)

    def _set_picker_open(self, open_: bool) -> None:
        self._picker_open = bool(open_)
        self._picker_panel.setVisible(self._picker_open)
        self._arrow.set_expanded(self._picker_open)

    def _toggle_picker(self) -> None:
        self._set_picker_open(not self._picker_open)

    def set_playhead_index(self, index: int) -> None:
        self._play_idx = int(index)
        self._canvas.set_state(
            self._model,
            self._keys,
            self._play_idx,
            self._tags(),
            keep_view=True,
        )

    def _tags(self) -> list[TagRecord]:
        if self._model is None or self._model.path is None:
            return []
        tp = tags_path_for_session(self._model.path)
        try:
            return load_tags(tp)
        except OSError:
            return []

    def _refill_lists(self) -> None:
        live = set(discover_available_keys(self._model))
        self._catalog |= live
        self._avail.blockSignals(True)
        self._avail.clear()
        for key in sorted(self._catalog):
            if key in self._keys:
                continue
            item = QListWidgetItem(key)
            if key not in live:
                item.setForeground(QColor("#999"))
                item.setToolTip("当前 session 暂无此字段（曾出现过，仍可添加/保留）")
            self._avail.addItem(item)
        self._avail.blockSignals(False)

        self._added.blockSignals(True)
        self._added.clear()
        for key in self._keys:
            self._added.addItem(key)
        self._added.blockSignals(False)

    def _on_avail_double(self, item: QListWidgetItem) -> None:
        self._add_key(item.text())

    def _on_added_double(self, item: QListWidgetItem) -> None:
        self._canvas.fit_series(item.text())
        self._canvas.update()

    def _on_added_sel(self, text: str) -> None:
        key = text.strip()
        if key:
            self._canvas.set_selected_key(key)

    def _on_canvas_sel(self, key: str) -> None:
        matches = self._added.findItems(key, Qt.MatchFlag.MatchExactly)
        if matches:
            self._added.blockSignals(True)
            self._added.setCurrentItem(matches[0])
            self._added.blockSignals(False)

    def _add_key(self, key: str) -> None:
        key = key.strip()
        if not key or key in self._keys:
            return
        self._keys.append(key)
        self._catalog.add(key)
        self._refill_lists()
        matches = self._added.findItems(key, Qt.MatchFlag.MatchExactly)
        if matches:
            self._added.setCurrentItem(matches[0])
        self._canvas.set_state(
            self._model,
            self._keys,
            self._play_idx,
            self._tags(),
            keep_view=True,
            fit_key=key,
        )
        # 不自动收起，方便连续添加；要空间时点中间 ▲

    def _on_add(self) -> None:
        selected = self._avail.selectedItems()
        if not selected and self._avail.currentItem() is not None:
            selected = [self._avail.currentItem()]
        # 先拷贝文本：后续 refill 会销毁 item
        keys = [it.text().strip() for it in selected if it is not None]
        added: list[str] = []
        for key in keys:
            if key and key not in self._keys:
                self._keys.append(key)
                self._catalog.add(key)
                added.append(key)
        if not added:
            return
        self._refill_lists()
        last = added[-1]
        matches = self._added.findItems(last, Qt.MatchFlag.MatchExactly)
        if matches:
            self._added.setCurrentItem(matches[0])
        self._canvas.set_state(
            self._model,
            self._keys,
            self._play_idx,
            self._tags(),
            keep_view=True,
            fit_key=last,
        )

    def _on_remove(self) -> None:
        selected = self._added.selectedItems()
        if not selected and self._added.currentItem() is not None:
            selected = [self._added.currentItem()]
        keys = [it.text().strip() for it in selected if it is not None]
        removed = False
        for key in keys:
            if key and key in self._keys:
                self._keys.remove(key)
                removed = True
        if not removed:
            return
        self._refill_lists()
        self._canvas.set_state(
            self._model,
            self._keys,
            self._play_idx,
            self._tags(),
            keep_view=True,
        )
