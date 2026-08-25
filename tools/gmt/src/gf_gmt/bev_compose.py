"""Compose BEV images from live module topics.

Primary inputs (iceoryx → tap NDJSON):
  /gf/EgoMotion   — ego speed / steer
  /gf/Trajectory  — path polyline (ego-frame: x forward, y left)
  /gf/Perception_MESSAGE_Out_St — FCM dyn (CIPV) + LH hostlines + LA adj lines
  /gf/UssZones    — optional nearest_cm (when tap supports it)

Output topic: /gf/driving/bev/compressed (foxglove.CompressedImage JSON).

Demo range contract (FOV is optical only — not these numbers):
  D_work ≈ 120 m — soft working / validity band (not a hard BEV cut)
  D_bev  = 130 m — canvas ≈ D_work×1.1; lanes/ticks/objects drawn to this
Object fill color is by stable OBJ_ID palette (video overlay will share later).
Trajectory polyline = planning `/gf/Trajectory`:
  green=accel, red=decel, blue=hold; line thickness ∝ |throttle−brake| (hold fixed thin).

BEV lane geometry comes only from FCM Out (Perception_LH_Out host lines and
Perception_LA_Out adjacent lines). Mark style follows gold lanemark_type
(1=solid, 2=dashed). Distance ticks sit on the outer edge of the whole corridor.

AdasDemo JSONL script enrichment is deprecated for live; kept only for offline
expand_rows_with_bev(..., script=...) tests if callers still pass a script.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gf_gmt.adas_scenarios import (
    TOPIC_ADAS,
    TOPIC_CAM,
    TOPIC_EGO,
    TOPIC_TRAJ,
    FrameState,
    compressed_image_msg,
    render_bev_png,
    _fill_rect,
    _line,
    _png_rgb,
)

TOPIC_USS = "/gf/UssZones"
TOPIC_PERC = "/gf/Perception_MESSAGE_Out_St"

# Demo contract — canvas is primary; work range is soft (avoid miss via ×1.1).
D_WORK_M = 120.0
D_BEV_M = 130.0
# Back-compat alias (prefer D_WORK_M / D_BEV_M in new code).
D_PERC_M = D_WORK_M

# Stable ID → RGB (adjacent hues). Video overlay will reuse the same map.
_ID_PALETTE: tuple[tuple[int, int, int], ...] = (
    (220, 90, 90),
    (90, 180, 220),
    (220, 180, 60),
    (180, 100, 220),
    (60, 200, 160),
    (230, 140, 80),
    (100, 140, 230),
    (200, 80, 160),
    (140, 200, 80),
    (80, 200, 220),
    (230, 100, 120),
    (160, 160, 90),
)


def color_for_obj_id(obj_id: int) -> tuple[int, int, int]:
    if obj_id <= 0:
        return _ID_PALETTE[0]
    return _ID_PALETTE[(int(obj_id) - 1) % len(_ID_PALETTE)]


@dataclass
class HostLanePoly:
    """Ego-frame host lane mark: y = C0 + C1 x + C2 x^2 + C3 x^3."""

    side: int = 0  # 1=left, 2=right
    c0: float = 0.0
    c1: float = 0.0
    c2: float = 0.0
    c3: float = 0.0
    x0: float = 0.0
    x1: float = D_BEV_M
    # Gold LH_Lanemark_Type: 1=solid, 2=dashed
    lanemark_type: int = 1

    def y_at(self, x: float) -> float:
        return self.c0 + self.c1 * x + self.c2 * x * x + self.c3 * x * x * x

    @property
    def is_dashed(self) -> bool:
        return int(self.lanemark_type) == 2


@dataclass
class AdjLanePoly:
    """Ego-frame adjacent lane mark: y = C0 + C1 x + C2 x^2 + C3 x^3."""

    side: int = 0
    c0: float = 0.0
    c1: float = 0.0
    c2: float = 0.0
    c3: float = 0.0
    x0: float = 0.0
    x1: float = D_BEV_M
    # Gold LA_Lanemark_Type: 1=solid, 2=dashed
    lanemark_type: int = 2

    def y_at(self, x: float) -> float:
        return self.c0 + self.c1 * x + self.c2 * x * x + self.c3 * x * x * x

    @property
    def is_dashed(self) -> bool:
        return int(self.lanemark_type) != 1


@dataclass
class BevDynObj:
    """One FCM dyn object for BEV (and later camera overlay)."""

    obj_id: int
    x_m: float
    y_m: float
    is_cipv: bool = False
    obj_class: int = 0
    length_m: float = 4.5
    width_m: float = 1.8
    heading_rad: float = 0.0  # vs ego +x (forward)


@dataclass
class AdasScriptIndex:
    """AdasDemo frames from a scenario JSONL, keyed by t_ns (for BEV only).

    Not published to Foxglove — story goes into CompressedImage.
    """

    by_t: dict[int, dict[str, Any]] = field(default_factory=dict)
    times: list[int] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> AdasScriptIndex | None:
        import json

        p = Path(path)
        if not p.is_file():
            return None
        by_t: dict[int, dict[str, Any]] = {}
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            topic = str(row.get("topic") or "")
            if not (topic.endswith("AdasDemo") or topic == TOPIC_ADAS):
                continue
            data = row.get("data")
            if not isinstance(data, dict):
                continue
            t_ns = int(row.get("t_ns") or data.get("timestamp_ns") or 0)
            if t_ns <= 0:
                continue
            by_t[t_ns] = data
        if not by_t:
            return None
        times = sorted(by_t)
        return cls(by_t=by_t, times=times)

    def nearest(self, t_ns: int) -> dict[str, Any] | None:
        if not self.times:
            return None
        # Exact or closest previous sample (scenario is 10 Hz).
        import bisect

        i = bisect.bisect_right(self.times, t_ns) - 1
        if i < 0:
            i = 0
        t = self.times[i]
        # Reject if more than 0.5s away (scrub / different session)
        if abs(t - t_ns) > 500_000_000:
            return None
        return self.by_t.get(t)


@dataclass
class LiveBevState:
    t_ns: int = 0
    speed_mps: float = 0.0
    yaw_rate_degps: float = 0.0
    steer_angle_deg: float = 0.0
    gear: int = 0
    traj_x: list[float] = field(default_factory=list)
    traj_y: list[float] = field(default_factory=list)
    nearest_cm: float | None = None
    # Integrated path length (m) for scrolling ground — ego-centric BEV motion cue
    odom_m: float = 0.0
    _last_t_ns: int = 0
    _last_speed_mps: float = 0.0
    # Smoothed longitudinal accel (m/s²) for Trajectory paint: +accel / −decel
    lon_accel_mps2: float = 0.0
    # Planning lite ctrl snapshot (file IPC) — preferred over measured a for paint
    throttle_cmd: float = 0.0
    brake_cmd: float = 0.0
    plan_mode: str = ""
    # Optional AdasDemo (offline only)
    has_adas: bool = False
    phase: str = ""
    lead_dist_m: float = 0.0
    lead_rel_v_mps: float = 0.0
    accel_cmd_mps2: float = 0.0
    brake_active: int = 0
    lane_offset_m: float = 0.0
    cipo_x_m: float = 0.0
    cipo_y_m: float = 0.0
    scenario_id: str = ""
    # Live FCM Out
    has_perc_lead: bool = False
    has_perc_lanes: bool = False
    host_lanes: list[HostLanePoly] = field(default_factory=list)
    adj_lanes: list[AdjLanePoly] = field(default_factory=list)
    lane_width_m: float = 3.5
    perc_objects: list[BevDynObj] = field(default_factory=list)
    cipv_id: int = 0


def lon_intent(st: LiveBevState) -> float:
    """Signed longitudinal intent in [-1, 1]: +accel, −decel, ~0 hold.

    Prefer planning throttle/brake (even when ego is physically stuck), then
    AdasDemo accel_cmd, then measured lon_accel.
    """
    thr = max(0.0, min(1.0, float(st.throttle_cmd)))
    brk = max(0.0, min(1.0, float(st.brake_cmd)))
    if thr > 0.04 or brk > 0.04:
        return max(-1.0, min(1.0, thr - brk))
    if st.has_adas:
        if int(st.brake_active) > 0 or float(st.accel_cmd_mps2) < -0.2:
            return max(-1.0, min(0.0, float(st.accel_cmd_mps2) / 3.0))
        if float(st.accel_cmd_mps2) > 0.2:
            return max(0.0, min(1.0, float(st.accel_cmd_mps2) / 3.0))
    a = float(st.lon_accel_mps2)
    return max(-1.0, min(1.0, a / 2.5))


def traj_color_for_lon(st: LiveBevState) -> tuple[int, int, int]:
    """Planning path color: green accel, red decel, blue hold."""
    intent = lon_intent(st)
    if intent > 0.08:
        return (70, 210, 110)  # accel
    if intent < -0.08:
        return (230, 80, 80)  # decel
    return (90, 160, 255)  # hold


def traj_thickness_for_lon(st: LiveBevState) -> int:
    """Hold stays thin (2); accel/decel thicken with |intent| → 3..7."""
    intent = abs(lon_intent(st))
    if intent <= 0.08:
        return 2
    return max(3, min(7, 2 + int(round(intent * 5.0))))


def render_ego_bev_png(st: LiveBevState, *, width: int = 480, height: int = 360) -> bytes:
    """Lane-anchored BEV: +x along host-lane heading, +y left of road.

    Ego-frame polys/objects from FCM are rotated into the road frame so extreme
    yaw no longer squashes the corridor. Canvas D_bev; objects/lanes to D_bev.
    """
    import math

    bg = (24, 28, 36)
    asphalt_host = (54, 58, 68)
    lh_c = (235, 235, 250)
    la_c = (170, 175, 190)
    dash_c = (200, 200, 90)
    ego_c = (80, 200, 120)
    traj_c = traj_color_for_lon(st)
    traj_thick = traj_thickness_for_lon(st)
    uss_c = (220, 180, 60)
    text_bar = (40, 44, 55)
    tick_c = (168, 168, 172)
    tick_major_c = (200, 200, 204)
    cipv_outline = (245, 245, 250)

    buf = bytearray(bytes(bg) * (width * height))
    _fill_rect(buf, width, height, 0, 0, width, 28, text_bar)

    ox, oy = width // 2, height - 44
    usable_h = max(80.0, float(oy - 28))
    sx = usable_h / D_BEV_M
    lane_w = float(st.lane_width_m) if st.lane_width_m > 0.5 else 3.5
    half = 0.5 * lane_w

    all_polys: list[HostLanePoly | AdjLanePoly] = list(st.host_lanes) + list(st.adj_lanes)
    left_poly: HostLanePoly | None = None
    right_poly: HostLanePoly | None = None
    for hl in st.host_lanes:
        if hl.side == 1:
            left_poly = hl
        elif hl.side == 2:
            right_poly = hl
    if left_poly is None and st.host_lanes:
        left_poly = st.host_lanes[0]
    if right_poly is None and len(st.host_lanes) > 1:
        right_poly = st.host_lanes[1]

    # Road yaw in ego frame from host C1 (straight-local tangent).
    c1_ref = 0.0
    if left_poly is not None and right_poly is not None:
        c1_ref = 0.5 * (left_poly.c1 + right_poly.c1)
    elif left_poly is not None:
        c1_ref = left_poly.c1
    elif right_poly is not None:
        c1_ref = right_poly.c1
    elif all_polys:
        c1_ref = float(all_polys[0].c1)
    psi = math.atan(max(-4.0, min(4.0, c1_ref)))
    c_psi, s_psi = math.cos(psi), math.sin(psi)

    def ego_to_road(xe: float, ye: float) -> tuple[float, float]:
        return xe * c_psi + ye * s_psi, -xe * s_psi + ye * c_psi

    def _host_y_ego(xe: float, side: str) -> float:
        if side == "l" and left_poly is not None:
            return left_poly.y_at(xe)
        if side == "r" and right_poly is not None:
            return right_poly.y_at(xe)
        return half if side == "l" else -half

    # Lateral span in ROAD frame near ego (stable under large yaw).
    y_road_samples: list[float] = []
    for xe_s in (0.0, 2.0, 5.0):
        for side in ("l", "r"):
            _xr, yr = ego_to_road(xe_s, _host_y_ego(xe_s, side))
            y_road_samples.append(yr)
        for poly in all_polys:
            _xr, yr = ego_to_road(xe_s, poly.y_at(xe_s))
            y_road_samples.append(yr)
    if y_road_samples:
        y_span_min, y_span_max = min(y_road_samples), max(y_road_samples)
        span_y = max(lane_w, y_span_max - y_span_min)
    else:
        y_span_min, y_span_max, span_y = -half, half, lane_w
    y_mid = 0.5 * (y_span_min + y_span_max)
    sy = min(
        52.0 / max(lane_w, 2.5),
        (width * 0.88) / max(span_y + 2.0, lane_w * 1.4),
    )

    dash_period = 12.0
    scroll = st.odom_m % dash_period
    # Draw horizon = min(canvas, host VR). Never extrapolate past Out VR_End.
    host_vr = D_BEV_M
    if st.host_lanes:
        host_vr = min(D_BEV_M, max(p.x1 for p in st.host_lanes))
    x_draw = max(0.0, host_vr)
    tick_stub_m = 0.55
    xe_span = (x_draw / max(0.2, abs(c_psi)) + 10.0) if x_draw > 0.5 else 0.0

    def e2p_road(xr: float, yr: float) -> tuple[int, int]:
        return int(ox - (yr - y_mid) * sy), int(oy - xr * sx)

    def e2p_ego(xe: float, ye: float) -> tuple[int, int]:
        return e2p_road(*ego_to_road(xe, ye))

    def _draw_poly_road(
        poly: HostLanePoly | AdjLanePoly,
        color: tuple[int, int, int],
        *,
        thick: int,
        dashed: bool = False,
    ) -> None:
        x_hi = min(float(poly.x1), x_draw)
        x_lo = max(0.0, float(poly.x0))
        if x_hi <= x_lo + 0.25:
            return
        prev: tuple[int, int] | None = None
        span = x_hi - x_lo
        steps = max(24, int(span) // 2 + 1)
        for i in range(steps + 1):
            xe = x_lo + span * i / steps
            if xe > float(poly.x1) + 1e-3:
                break
            ye = poly.y_at(xe)
            xr, yr = ego_to_road(xe, ye)
            if xr < -2.0 or xr > x_draw + 5.0:
                prev = None
                continue
            pt = e2p_road(xr, yr)
            if prev is not None:
                if not dashed or i % 3 != 0:
                    _line(buf, width, height, prev[0], prev[1], pt[0], pt[1], color, thick=thick)
            prev = pt

    # Host asphalt only within VR
    if x_draw > 0.5 and (left_poly is not None or right_poly is not None):
        steps_a = max(24, int(xe_span) // 2 + 1)
        for i in range(steps_a + 1):
            xe = min(x_draw, (xe_span) * i / max(1, steps_a))
            if left_poly is not None and xe > left_poly.x1:
                continue
            if right_poly is not None and xe > right_poly.x1:
                continue
            ya, yb = _host_y_ego(xe, "r"), _host_y_ego(xe, "l")
            p_a, p_b = e2p_ego(xe, ya), e2p_ego(xe, yb)
            xa, xb = sorted((p_a[0], p_b[0]))
            py = (p_a[1] + p_b[1]) // 2
            xr, _ = ego_to_road(xe, 0.5 * (ya + yb))
            if xr < -1.0 or xr > x_draw + 2.0:
                continue
            _fill_rect(buf, width, height, xa, max(28, py), xb + 1, min(height, py + 3), asphalt_host)

    for hl in st.host_lanes:
        _draw_poly_road(hl, lh_c, thick=3, dashed=hl.is_dashed)
    # No fallback schematic host when Out says unavailable.
    for al in st.adj_lanes:
        _draw_poly_road(al, la_c, thick=2, dashed=al.is_dashed)

    # Host center dashes / ruler only when host lanes are available within VR
    if x_draw > 0.5 and st.host_lanes:
        y_host_mid_e = 0.5 * (_host_y_ego(0.0, "l") + _host_y_ego(0.0, "r"))
        for seg in range(-int(dash_period), int(x_draw) + int(dash_period), max(1, int(dash_period // 2))):
            x0 = float(seg) - scroll
            x1 = x0 + dash_period * 0.45
            if x1 < 0 or x0 > x_draw:
                continue

            def _pt_at_road_x(xr: float) -> tuple[int, int]:
                xe = xr * c_psi
                ye = 0.5 * (_host_y_ego(xe, "l") + _host_y_ego(xe, "r"))
                return e2p_ego(xe, ye)

            p0, p1 = _pt_at_road_x(max(0.0, x0)), _pt_at_road_x(min(x_draw, x1))
            _line(buf, width, height, p0[0], p0[1], p1[0], p1[1], dash_c, thick=2)

        def _corridor_yr(xr_t: float) -> tuple[float, float]:
            ys: list[float] = []
            xe = xr_t * c_psi
            for _ in range(3):
                ye_mid = 0.5 * (_host_y_ego(xe, "l") + _host_y_ego(xe, "r"))
                xr_now, _ = ego_to_road(xe, ye_mid)
                xe += (xr_t - xr_now) * c_psi
            for poly in all_polys:
                _xr, yr = ego_to_road(xe, poly.y_at(min(xe, float(poly.x1))))
                ys.append(yr)
            if not ys:
                for side in ("l", "r"):
                    _xr, yr = ego_to_road(xe, _host_y_ego(xe, side))
                    ys.append(yr)
            return min(ys), max(ys)

        y0_lo, y0_hi = _corridor_yr(0.0)
        _xr0, yr_host = ego_to_road(0.0, y_host_mid_e)
        use_left_outer = abs(y0_hi - yr_host) <= abs(y0_lo - yr_host)
        for k in range(0, int(x_draw) // 20 + 1):
            xr = float(k * 20)
            if xr <= 0.0 or xr > x_draw:
                continue
            y_lo, y_hi = _corridor_yr(xr)
            if use_left_outer:
                y_edge = y_hi
                y_tip = y_edge + tick_stub_m * (1.35 if (k % 2 == 0) else 0.85)
            else:
                y_edge = y_lo
                y_tip = y_edge - tick_stub_m * (1.35 if (k % 2 == 0) else 0.85)
            major = k % 2 == 0
            p0, p1 = e2p_road(xr, y_edge), e2p_road(xr, y_tip)
            _line(
                buf, width, height, p0[0], p0[1], p1[0], p1[1],
                tick_major_c if major else tick_c, thick=2 if major else 1,
            )

    if len(st.traj_x) >= 2:
        for i in range(len(st.traj_x) - 1):
            a = e2p_ego(st.traj_x[i], st.traj_y[i])
            b = e2p_ego(st.traj_x[i + 1], st.traj_y[i + 1])
            _line(buf, width, height, a[0], a[1], b[0], b[1], traj_c, thick=traj_thick)

    if st.nearest_cm is not None and st.nearest_cm > 0:
        dist_m = max(0.5, min(float(st.nearest_cm) / 100.0, D_BEV_M))
        cx, cy = e2p_ego(dist_m, 0.0)
        _fill_rect(buf, width, height, cx - 4, cy - 4, cx + 4, cy + 4, uss_c)

    objs = list(st.perc_objects)
    if not objs and (st.has_perc_lead or st.lead_dist_m > 0.5):
        objs = [
            BevDynObj(
                obj_id=st.cipv_id or 1,
                x_m=float(st.cipo_x_m or st.lead_dist_m),
                y_m=float(st.cipo_y_m),
                is_cipv=True,
            )
        ]

    max_hx = max(2, int(0.42 * lane_w * sy))

    def _paint_box_road(
        xe: float,
        ye: float,
        length_m: float,
        width_m: float,
        heading_ego: float,
        fill: tuple[int, int, int],
        *,
        outline: tuple[int, int, int] | None = None,
    ) -> None:
        xr, yr = ego_to_road(xe, ye)
        heading_r = heading_ego - psi
        c = math.cos(heading_r)
        s = math.sin(heading_r)
        hl, hw = 0.5 * length_m, 0.5 * width_m
        if abs(heading_r) < 0.08:
            hx = max(2, min(max_hx, int(hw * sy)))
            hy = max(2, int(hl * sx))
            cx, cy = e2p_road(xr, yr)
            if outline is not None:
                _fill_rect(
                    buf, width, height, cx - hx - 2, cy - hy - 2, cx + hx + 2, cy + hy + 2, outline
                )
            _fill_rect(buf, width, height, cx - hx, cy - hy, cx + hx, cy + hy, fill)
            return
        steps_l = max(4, int(length_m * sx / 2) + 1)
        steps_w = max(3, int(width_m * sy / 2) + 1)
        for i in range(steps_l + 1):
            for j in range(steps_w + 1):
                dl = -hl + length_m * i / steps_l
                dw = -hw + width_m * j / steps_w
                pxr = xr + dl * c - dw * s
                pyr = yr + dl * s + dw * c
                px, py = e2p_road(pxr, pyr)
                col = outline if (
                    outline is not None and (i in (0, steps_l) or j in (0, steps_w))
                ) else fill
                if 0 <= px < width and 0 <= py < height:
                    _fill_rect(buf, width, height, px, py, px + 1, py + 1, col)

    for obj in objs:
        xr, _yr = ego_to_road(obj.x_m, obj.y_m)
        if obj.x_m < -2.0 or xr > D_BEV_M + 5.0:
            continue
        # Class tint: pedestrians slightly different palette index
        fill = color_for_obj_id(obj.obj_id)
        if int(obj.obj_class) == 5:
            fill = (220, 160, 80)
        _paint_box_road(
            obj.x_m,
            obj.y_m,
            obj.length_m,
            obj.width_m,
            float(obj.heading_rad),
            fill,
            outline=cipv_outline if obj.is_cipv else None,
        )

    # Ego: nose relative to road = -psi
    _paint_box_road(0.0, 0.0, 4.5, 1.8, 0.0, ego_c)

    bar_w = int(min(200, max(8, st.speed_mps * 6)))
    _fill_rect(buf, width, height, 8, 6, 8 + bar_w, 22, (80, 180, 90))
    spark = 8 + int(st.odom_m * 10) % max(1, width - 16)
    _fill_rect(buf, width, height, spark, 6, spark + 3, 22, (240, 240, 80))

    return _png_rgb(width, height, bytes(buf))



_CTRL_MODE_NAMES = {0: "cruise", 1: "acc", 2: "aeb", 3: "pullaway"}


def _lane_line_quality(it: dict[str, Any], *, conf_key: str, avail_key: str) -> tuple[float, int] | None:
    """(conf, avail) or None to skip.

    obs_tap HostLine allowlist historically omits Availability. Missing Availability
    must NOT mean NA(0) when Confidence/VR are present — that blacked out healthy lanes.
    """
    has_conf = conf_key in it and it.get(conf_key) is not None
    has_avail = avail_key in it and it.get(avail_key) is not None
    conf = float(it[conf_key]) if has_conf else 0.95
    if has_avail:
        avail = int(it[avail_key])
    else:
        avail = 2 if conf >= 0.15 else 0
    if avail == 0 or conf < 0.15:
        return None
    return conf, avail


class LiveBevComposer:
    """Accumulate tap/session rows → optional CompressedImage row."""

    def __init__(self, *, script: AdasScriptIndex | None = None) -> None:
        self.state = LiveBevState()
        self._emit_every = 1
        self._n = 0
        self._script = script

    def _apply_traj_ctrl(self, data: dict[str, Any]) -> None:
        if data.get("throttle") is not None:
            self.state.throttle_cmd = float(data["throttle"])
        if data.get("brake") is not None:
            self.state.brake_cmd = float(data["brake"])
        if data.get("ctrl_mode") is not None:
            try:
                mid = int(data["ctrl_mode"])
                self.state.plan_mode = _CTRL_MODE_NAMES.get(mid, str(mid))
            except (TypeError, ValueError):
                pass
        elif data.get("mode") is not None:
            self.state.plan_mode = str(data["mode"])

    def _apply_adas_data(self, data: dict[str, Any]) -> None:
        self.state.has_adas = True
        self.state.phase = str(data.get("phase") or "")
        self.state.lead_dist_m = float(data.get("lead_dist_m") or 0.0)
        self.state.lead_rel_v_mps = float(data.get("lead_rel_v_mps") or 0.0)
        self.state.accel_cmd_mps2 = float(data.get("accel_cmd_mps2") or 0.0)
        self.state.brake_active = int(data.get("brake_active") or 0)
        self.state.lane_offset_m = float(data.get("lane_offset_m") or 0.0)
        self.state.cipo_x_m = float(data.get("cipo_x_m") or self.state.lead_dist_m)
        self.state.cipo_y_m = float(data.get("cipo_y_m") or 0.0)
        self.state.scenario_id = str(data.get("scenario_id") or "")
        if data.get("speed_mps") is not None:
            self.state.speed_mps = float(data["speed_mps"])

    def _apply_perc_lh(self, data: dict[str, Any]) -> None:
        lh = data.get("Perception_LH_Out")
        if not isinstance(lh, dict):
            self.state.has_perc_lanes = False
            self.state.host_lanes = []
            return
        items = lh.get("m_hostline") or []
        n = int(lh.get("m_hostline_num") or 0)
        if not isinstance(items, list) or n <= 0:
            self.state.has_perc_lanes = False
            self.state.host_lanes = []
            return
        lanes: list[HostLanePoly] = []
        for it in items[: max(0, n)]:
            if not isinstance(it, dict):
                continue
            q = _lane_line_quality(
                it, conf_key="m_LH_Confidence", avail_key="m_LH_Availability_State"
            )
            if q is None:
                continue
            x0 = float(it.get("m_LH_First_VR_Start") or 0.0)
            x1 = float(it.get("m_LH_First_VR_End") or 0.0)
            if x1 <= x0 + 0.25:
                continue  # no inventing horizon past VR
            x1 = min(x1, D_BEV_M)
            lanes.append(
                HostLanePoly(
                    side=int(it.get("m_LH_Side") or 0),
                    c0=float(it.get("m_LH_Line_First_C0") or 0.0),
                    c1=float(it.get("m_LH_Line_First_C1") or 0.0),
                    c2=float(it.get("m_LH_Line_First_C2") or 0.0),
                    c3=float(it.get("m_LH_Line_First_C3") or 0.0),
                    x0=x0,
                    x1=x1,
                    lanemark_type=int(it.get("m_LH_Lanemark_Type") or 1),
                )
            )
        self.state.host_lanes = lanes
        self.state.has_perc_lanes = len(lanes) >= 1
        w = float(lh.get("m_LH_Estimated_Width") or 0.0)
        if w > 0.5:
            self.state.lane_width_m = w

    def _apply_perc_la(self, data: dict[str, Any]) -> None:
        la = data.get("Perception_LA_Out")
        if not isinstance(la, dict):
            self.state.adj_lanes = []
            return
        items = la.get("m_adj_line") or []
        n = int(la.get("m_adj_line_num") or 0)
        if not isinstance(items, list) or n <= 0:
            self.state.adj_lanes = []
            return
        lanes: list[AdjLanePoly] = []
        for it in items[: max(0, n)]:
            if not isinstance(it, dict):
                continue
            q = _lane_line_quality(
                it, conf_key="m_LA_Confidence", avail_key="m_LA_Availability_State"
            )
            if q is None:
                continue
            x0 = float(it.get("m_LA_View_Range_Start") or 0.0)
            x1 = float(it.get("m_LA_View_Range_End") or 0.0)
            if x1 <= x0 + 0.25:
                continue
            x1 = min(x1, D_BEV_M)
            lanes.append(
                AdjLanePoly(
                    side=int(it.get("m_LA_Line_Side") or 0),
                    c0=float(it.get("m_LA_Line_C0") or 0.0),
                    c1=float(it.get("m_LA_Line_C1") or 0.0),
                    c2=float(it.get("m_LA_Line_C2") or 0.0),
                    c3=float(it.get("m_LA_Line_C3") or 0.0),
                    x0=x0,
                    x1=x1,
                    lanemark_type=int(it.get("m_LA_Lanemark_Type") or 2),
                )
            )
        self.state.adj_lanes = lanes

    def _apply_perc_out(self, data: dict[str, Any]) -> None:
        """Parse gold-like Perception_MESSAGE_Out_St NDJSON from obs_tap."""
        self._apply_perc_lh(data)
        self._apply_perc_la(data)
        dyn = data.get("Perception_DYN_OBJ_Out")
        if not isinstance(dyn, dict):
            # flat fallbacks
            if data.get("lead_dist_m") is not None:
                dist = float(data["lead_dist_m"])
                self.state.has_perc_lead = 0.5 < dist <= D_BEV_M
                self.state.lead_dist_m = dist
                self.state.cipo_x_m = dist
                self.state.cipo_y_m = float(data.get("lead_lat_m") or 0.0)
                self.state.lead_rel_v_mps = float(data.get("lead_rel_v_mps") or 0.0)
                self.state.cipv_id = 1
                self.state.perc_objects = (
                    [
                        BevDynObj(
                            obj_id=1,
                            x_m=dist,
                            y_m=self.state.cipo_y_m,
                            is_cipv=True,
                        )
                    ]
                    if self.state.has_perc_lead
                    else []
                )
            return
        vd = int(dyn.get("m_OBJ_VD_Count") or 0)
        items = dyn.get("m_Obj_item") or []
        cipv = int(dyn.get("m_OBJ_VD_CIPV_ID") or 0)
        self.state.cipv_id = cipv
        objs: list[BevDynObj] = []
        if isinstance(items, list) and vd > 0:
            for it in items[:vd]:
                if not isinstance(it, dict):
                    continue
                oid = int(it.get("m_OBJ_ID") or 0)
                dist = float(it.get("m_OBJ_Long_Distance") or 0.0)
                if oid <= 0 or dist <= 0.5 or dist > D_BEV_M:
                    continue
                objs.append(
                    BevDynObj(
                        obj_id=oid,
                        x_m=dist,
                        y_m=float(it.get("m_OBJ_Lat_Distance") or 0.0),
                        is_cipv=(cipv != 0 and oid == cipv),
                        obj_class=int(it.get("m_OBJ_Object_Class") or 0),
                        length_m=float(it.get("m_OBJ_Length") or 4.5),
                        width_m=float(it.get("m_OBJ_Width") or 1.8),
                        heading_rad=float(it.get("m_OBJ_Heading") or 0.0),
                    )
                )
        self.state.perc_objects = objs
        if not objs:
            self.state.has_perc_lead = False
            self.state.lead_dist_m = 0.0
            return
        lead = next((o for o in objs if o.is_cipv), objs[0])
        if not lead.is_cipv:
            lead.is_cipv = True
            self.state.cipv_id = lead.obj_id
        self.state.has_perc_lead = True
        self.state.lead_dist_m = lead.x_m
        self.state.cipo_x_m = lead.x_m
        self.state.cipo_y_m = lead.y_m
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and int(it.get("m_OBJ_ID") or 0) == lead.obj_id:
                    self.state.lead_rel_v_mps = float(
                        it.get("m_OBJ_Relative_Long_Velocity") or 0.0
                    )
                    break

    def _maybe_script_at(self, t_ns: int) -> None:
        if self._script is None or t_ns <= 0:
            return
        data = self._script.nearest(t_ns)
        if data is not None:
            self._apply_adas_data(data)

    def _advance_odom(self, t_ns: int, speed_mps: float) -> None:
        if t_ns <= 0:
            return
        if self.state._last_t_ns > 0 and t_ns > self.state._last_t_ns:
            dt = (t_ns - self.state._last_t_ns) / 1e9
            # Cap dt so scrub jumps don't teleport the scroll
            dt = min(dt, 0.5)
            self.state.odom_m += max(0.0, speed_mps) * dt
            if dt >= 0.02:
                raw_a = (speed_mps - self.state._last_speed_mps) / dt
                raw_a = max(-6.0, min(6.0, raw_a))
                self.state.lon_accel_mps2 = 0.65 * self.state.lon_accel_mps2 + 0.35 * raw_a
        elif self.state._last_t_ns == 0:
            # first sample: nudge so first frames still differ after start
            self.state.odom_m += max(0.0, speed_mps) * 0.05
        self.state._last_t_ns = t_ns
        self.state._last_speed_mps = float(speed_mps)

    def update(self, row: dict[str, Any]) -> dict[str, Any] | None:
        """Feed one NDJSON row. Returns a camera row to publish, or None."""
        topic = str(row.get("topic") or "")
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        t_ns = int(row.get("t_ns") or 0)
        if t_ns:
            self.state.t_ns = t_ns

        leaf = topic.rstrip("/")
        emit = False

        if leaf.endswith("EgoMotion") or leaf == TOPIC_EGO:
            self.state.speed_mps = float(data.get("speed_mps") or 0.0)
            self.state.yaw_rate_degps = float(data.get("yaw_rate_degps") or 0.0)
            self.state.steer_angle_deg = float(data.get("steer_angle_deg") or 0.0)
            self.state.gear = int(data.get("gear") or 0)
            if data.get("timestamp_ns"):
                self.state.t_ns = int(data["timestamp_ns"])
            self._maybe_script_at(self.state.t_ns or t_ns)
            self._advance_odom(self.state.t_ns or t_ns, self.state.speed_mps)
            emit = True
        elif leaf.endswith("Trajectory") or leaf == TOPIC_TRAJ:
            xs = data.get("points_x_m") or []
            ys = data.get("points_y_m") or []
            if isinstance(xs, list) and isinstance(ys, list):
                self.state.traj_x = [float(x) for x in xs]
                self.state.traj_y = [float(y) for y in ys]
            self._apply_traj_ctrl(data)
            if data.get("timestamp_ns"):
                self.state.t_ns = int(data["timestamp_ns"])
            self._maybe_script_at(self.state.t_ns or t_ns)
            emit = True
        elif "UssZones" in leaf or leaf == TOPIC_USS:
            if data.get("nearest_cm") is not None:
                self.state.nearest_cm = float(data["nearest_cm"])
            emit = True
        elif "Perception_MESSAGE_Out" in leaf or leaf == TOPIC_PERC:
            self._apply_perc_out(data)
            emit = True
        elif leaf.endswith("AdasDemo") or leaf == TOPIC_ADAS:
            # Offline/jsonl only; live path uses FCM Out.
            self._apply_adas_data(data)
            self._advance_odom(self.state.t_ns or t_ns, self.state.speed_mps)
            emit = True

        if not emit:
            return None

        self._n += 1
        if self._n % self._emit_every != 0:
            return None

        t = self.state.t_ns or t_ns
        # Prefer unique log times for Studio Image panel (ns); bump if equal
        if t <= 0:
            t = self._n * 100_000_000  # 0.1s steps
        if self.state.has_adas and not self.state.has_perc_lead:
            lo = self.state.lane_offset_m
            # Prefer planning Trajectory (ego-frame → world y for render_bev_png).
            if len(self.state.traj_x) >= 2 and len(self.state.traj_y) >= 2:
                traj_x = list(self.state.traj_x)
                traj_y = [lo + y for y in self.state.traj_y]
            else:
                traj_x = [0.0, 20.0, 40.0]
                traj_y = [lo, lo, lo]
            fs = FrameState(
                t_ns=t,
                scenario_id=self.state.scenario_id or "live",
                phase=self.state.phase or "live",
                speed_mps=self.state.speed_mps,
                yaw_rate_degps=self.state.yaw_rate_degps,
                steer_angle_deg=self.state.steer_angle_deg,
                gear=self.state.gear,
                lead_dist_m=self.state.lead_dist_m,
                lead_rel_v_mps=self.state.lead_rel_v_mps,
                accel_cmd_mps2=self.state.accel_cmd_mps2,
                brake_active=self.state.brake_active,
                lane_offset_m=lo,
                cipo_x_m=self.state.cipo_x_m,
                cipo_y_m=self.state.cipo_y_m,
                traj_x=traj_x,
                traj_y=traj_y,
            )
            png = render_bev_png(fs)
        else:
            png = render_ego_bev_png(self.state)

        return {
            "t_ns": t,
            "topic": TOPIC_CAM,
            "data": compressed_image_msg(t, png),
        }


def expand_rows_with_bev(
    rows: list[dict[str, Any]],
    *,
    script: AdasScriptIndex | None = None,
    drop_adas_topic: bool = True,
) -> list[dict[str, Any]]:
    """Offline/jsonl: pass-through rows + synthesized camera frames.

    By default drop /gf/AdasDemo from the output list (story is in the Image).
    """
    comp = LiveBevComposer(script=script)
    out: list[dict[str, Any]] = []
    for row in rows:
        topic = str(row.get("topic") or "")
        is_adas = topic.endswith("AdasDemo") or topic == TOPIC_ADAS
        if not (drop_adas_topic and is_adas):
            out.append(row)
        cam = comp.update(row)
        if cam is not None:
            out.append(cam)
    return out


def is_adas_demo_topic(topic: str) -> bool:
    t = topic.rstrip("/")
    return t.endswith("AdasDemo") or t == TOPIC_ADAS
