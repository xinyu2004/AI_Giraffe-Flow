"""Compose BEV images from live module topics.

Primary inputs (iceoryx → tap NDJSON):
  /gf/EgoMotion   — ego speed / steer
  /gf/Trajectory  — path polyline (ego-frame: x forward, y left)
  /gf/Perception_MESSAGE_Out_St — FCM dyn (CIPV) + LH hostlines + LA adj lines
  /gf/UssZones    — optional nearest_cm (when tap supports it)

Output topic: /gf/driving/bev/compressed (foxglove.CompressedImage JSON).

Demo range contract:
  D_work ≈ 120 m — soft working / validity band (not a hard BEV cut)
  D_bev  = 130 m — canvas ≈ D_work×1.1; gray marks/ticks/objects drawn to this
  Teal wash + cap + path = host lane only, to D_see. Triangles only if an
  in-lane object notched the opening. No FOV overlay. Gray marks follow VR_End.

BEV lane geometry comes only from FCM Out (Perception_LH_Out host lines and
Perception_LA_Out adjacent lines). Mark style follows gold lanemark_type
(1=solid, 2=dashed). Distance ticks sit on the outer edge of the whole corridor.

AdasDemo JSONL script enrichment is deprecated for live; kept only for offline
expand_rows_with_bev(..., script=...) tests if callers still pass a script.
"""

from __future__ import annotations

import json
import math
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

# GB-style lane dash: 6 m paint + 9 m gap (along-road metres, not pixels).
DASH_ON_M = 6.0
DASH_GAP_M = 9.0
DASH_PERIOD_M = DASH_ON_M + DASH_GAP_M

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


def fill_convex_poly(
    buf: bytearray,
    width: int,
    height: int,
    pts: list[tuple[int, int]],
    fill: tuple[int, int, int],
    *,
    outline: tuple[int, int, int] | None = None,
    y_clip0: int = 0,
) -> None:
    """Solid scanline fill of a convex polygon (rotated vehicle boxes)."""
    if len(pts) < 3:
        return
    xs_at: dict[int, list[float]] = {}
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if y0 == y1:
            continue
        if y0 > y1:
            x0, y0, x1, y1 = x1, y1, x0, y0
        y_lo = max(int(y_clip0), int(y0))
        y_hi = min(height - 1, int(y1))
        if y_hi < y_lo:
            continue
        dy = float(y1 - y0)
        for y in range(y_lo, y_hi + 1):
            t = max(0.0, min(1.0, (y - y0) / dy))
            xs_at.setdefault(y, []).append(x0 + t * (x1 - x0))
    if not xs_at:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xa = max(0, min(xs))
        xb = min(width, max(xs) + 1)
        ya = max(int(y_clip0), min(ys))
        yb = min(height, max(ys) + 1)
        if xa < xb and ya < yb:
            _fill_rect(buf, width, height, xa, ya, xb, yb, fill)
    else:
        for y, xs in xs_at.items():
            xa = max(0, int(math.floor(min(xs))))
            xb = min(width - 1, int(math.ceil(max(xs))))
            if xa <= xb:
                _fill_rect(buf, width, height, xa, y, xb + 1, y + 1, fill)
    if outline is not None:
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            _line(buf, width, height, a[0], a[1], b[0], b[1], outline, thick=2)


def dash_lit_m(s_m: float, *, scroll_m: float = 0.0) -> bool:
    """True on the 6 m painted part of a 6+9 dash cycle (world-fixed via scroll)."""
    period = DASH_PERIOD_M
    u = (float(s_m) - float(scroll_m)) % period
    if u < 0.0:
        u += period
    return u < DASH_ON_M


def _vsub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vdot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vcross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vnorm(a: tuple[float, float, float]) -> tuple[float, float, float]:
    n = math.sqrt(_vdot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


@dataclass
class BevCam:
    """Behind-above pinhole looking down the road. +x forward, +y left, +z up."""

    ox: float
    oy_pp: float
    f: float
    cpos: tuple[float, float, float]
    right: tuple[float, float, float]
    up: tuple[float, float, float]
    fwd: tuple[float, float, float]

    def project(self, x: float, y: float, z: float = 0.0) -> tuple[int, int]:
        rel = (x - self.cpos[0], y - self.cpos[1], z - self.cpos[2])
        xc = _vdot(rel, self.right)
        yc = _vdot(rel, self.up)
        zc = max(0.85, _vdot(rel, self.fwd))
        u = self.ox + self.f * xc / zc
        v = self.oy_pp - self.f * yc / zc
        return int(round(u)), int(round(v))


def bev_cam_basis(
    *,
    back_m: float = 8.0,
    height_m: float = 14.0,
    look_m: float = 36.0,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    cpos = (-float(back_m), 0.0, float(height_m))
    tgt = (float(look_m), 0.0, 0.0)
    fwd = _vnorm(_vsub(tgt, cpos))
    right = _vnorm(_vcross(fwd, (0.0, 0.0, 1.0)))
    if abs(_vdot(right, right)) < 1e-8:
        right = (0.0, -1.0, 0.0)
    up = _vnorm(_vcross(right, fwd))
    return cpos, right, up, fwd


def make_bev_cam(
    width: int,
    height: int,
    *,
    x_far_m: float = D_BEV_M,
) -> BevCam:
    """Fit pinhole so ego is near the bottom and D_bev sits under the HUD."""
    ox = float(width) * 0.5
    oy_ego = float(height) - 44.0
    y_far = 32.0
    cpos, right, up, fwd = bev_cam_basis()

    def _yz(x: float, y: float, z: float) -> tuple[float, float]:
        rel = (x - cpos[0], y - cpos[1], z - cpos[2])
        return _vdot(rel, up), max(0.85, _vdot(rel, fwd))

    yc0, zc0 = _yz(0.0, 0.0, 0.0)
    yc1, zc1 = _yz(float(x_far_m), 0.0, 0.0)
    a0, a1 = yc0 / zc0, yc1 / zc1
    den = a0 - a1
    if abs(den) < 1e-6:
        f = 420.0
        oy_pp = oy_ego
    else:
        f = (y_far - oy_ego) / den
        if f < 40.0:
            f = 420.0
        oy_pp = oy_ego + f * a0
    return BevCam(ox=ox, oy_pp=oy_pp, f=f, cpos=cpos, right=right, up=up, fwd=fwd)


def obj_height_m(obj_class: int) -> float:
    c = int(obj_class)
    if c == 5:
        return 1.7
    if c == 2:
        return 3.0
    if c in (3, 4, 9):
        return 1.4
    return 1.5


def dash_line(
    buf: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rgb: tuple[int, int, int],
    *,
    thick: int = 2,
    dash_on: int = 7,
    dash_off: int = 6,
) -> None:
    dx = float(x1 - x0)
    dy = float(y1 - y0)
    length = math.hypot(dx, dy)
    if length < 1.5:
        return
    ux, uy = dx / length, dy / length
    pos = 0.0
    on = float(max(2, dash_on))
    off = float(max(1, dash_off))
    while pos < length:
        a = pos
        b = min(length, pos + on)
        _line(
            buf,
            width,
            height,
            int(round(x0 + ux * a)),
            int(round(y0 + uy * a)),
            int(round(x0 + ux * b)),
            int(round(y0 + uy * b)),
            rgb,
            thick=thick,
        )
        pos = b + off


def d_see_paint_marks(
    host_cap: tuple[float, float, float, float],
    *,
    far_left: tuple[float, float] | None = None,
    far_right: tuple[float, float] | None = None,
) -> tuple[
    list[tuple[float, float, float, float]],
    list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]],
]:
    """Host-lane cap; triangles only when adj marks continue past an occupy notch."""
    segs: list[tuple[float, float, float, float]] = []
    tris: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = []
    x0, y0, x1, y1 = (float(v) for v in host_cap)
    if max(abs(x1 - x0), abs(y1 - y0)) < 0.2:
        return segs, tris
    if y0 <= y1:
        xl, yl, xr, yr = x0, y0, x1, y1
    else:
        xl, yl, xr, yr = x1, y1, x0, y0
    segs.append((xl, yl, xr, yr))
    if far_left is not None:
        xf, yf = float(far_left[0]), float(far_left[1])
        if yf > max(yl, yr) + 0.35:
            segs.append((xr, yr, xf, yf))
            tris.append(((xr, yr), (xf, yf), (xf, yr)))
    if far_right is not None:
        xf, yf = float(far_right[0]), float(far_right[1])
        if yf < min(yl, yr) - 0.35:
            segs.append((xl, yl, xf, yf))
            tris.append(((xl, yl), (xf, yf), (xf, yl)))
    return segs, tris


# In-host-lane band; matches _objects_truth assign==HOST when |y|<=1.5.
_SEE_HOST_LAT_M = 1.5
_SEE_CANVAS_MARGIN_M = 3.0
_SEE_FILL = (44, 124, 144)
_SEE_CAP = (96, 224, 236)
_SEE_CAP_LIP_M = 2.0
# 1:1 gf_plan_cal.m see_fov_deg (length of host wash, not a drawn cone).
_SEE_FOV_DEG = 50.0


def see_cap_x_m(
    opening_m: float,
    x_draw_m: float,
    *,
    margin_m: float = _SEE_CANVAS_MARGIN_M,
) -> float:
    """Paint station for the see cap: opening, but not flush with the canvas rim."""
    hi = min(float(x_draw_m), D_BEV_M) - max(0.0, float(margin_m))
    return max(0.0, min(float(opening_m), hi))


def see_opening_m(
    host_vr_m: float,
    objects: list[BevDynObj],
    *,
    host_lat_m: float = _SEE_HOST_LAT_M,
) -> float:
    """See opening: nearest in-lane dyn, else mark VR. Adjacent-lane objects do not notch."""
    opening = max(0.0, float(host_vr_m))
    lat_max = max(0.8, float(host_lat_m))
    for obj in objects:
        x = float(obj.x_m)
        y = float(obj.y_m)
        if x <= 0.5 or x >= opening:
            continue
        if abs(y) > lat_max:
            continue
        opening = x
    return opening


def optical_d_along_poly(
    c0: float,
    c1: float,
    c2: float,
    c3: float,
    x_end: float,
    *,
    cap_m: float = 120.0,
    step_m: float = 2.0,
) -> float:
    """Along-poly optical see. 1:1 gf_plan_d_fov.m (bearing, not heading)."""
    d = min(float(cap_m), float(x_end) if float(x_end) > 0.5 else float(cap_m))
    half = 0.5 * math.radians(_SEE_FOV_DEG)
    x = 2.0
    while x <= d + 1e-6:
        y = c0 + c1 * x + c2 * x * x + c3 * x * x * x
        if abs(math.atan2(y, x)) > half:
            return x
        x += step_m
    return d


def optical_d_from_host(host_lanes: list[HostLanePoly], host_vr_m: float) -> float:
    """Mid-corridor poly from host L/R. Empty → mark VR."""
    vr = max(0.0, float(host_vr_m))
    if not host_lanes:
        return vr
    n = float(len(host_lanes))
    c0 = sum(float(p.c0) for p in host_lanes) / n
    c1 = sum(float(p.c1) for p in host_lanes) / n
    c2 = sum(float(p.c2) for p in host_lanes) / n
    c3 = sum(float(p.c3) for p in host_lanes) / n
    return optical_d_along_poly(c0, c1, c2, c3, vr if vr > 0.5 else 120.0)


def driving_see_m(
    st: LiveBevState,
    host_vr_m: float,
    objects: list[BevDynObj],
) -> float:
    """HUD D: Trajectory D_see_m if published, else min(in-lane occupy, optical)."""
    if float(st.traj_d_see_m) > 0.5:
        return float(st.traj_d_see_m)
    occ = see_opening_m(host_vr_m, objects)
    opt = optical_d_from_host(st.host_lanes, host_vr_m)
    return min(occ, opt)


def occupy_notched(host_vr_m: float, occupy_opening_m: float, *, slack_m: float = 2.0) -> bool:
    """True only when an in-lane object cut the opening inside mark VR."""
    return float(occupy_opening_m) + float(slack_m) < float(host_vr_m)


def see_far_adj(
    adj_lanes: list[AdjLanePoly],
    opening_m: float,
) -> tuple[AdjLanePoly | None, AdjLanePoly | None]:
    """Closest adj on each side whose mark continues past the opening (skip next-next if ±1 exists)."""
    left: list[AdjLanePoly] = []
    right: list[AdjLanePoly] = []
    for al in adj_lanes:
        if float(al.x1) <= float(opening_m) + 2.0:
            continue
        y0 = al.y_at(0.0)
        if y0 > 0.2:
            left.append(al)
        elif y0 < -0.2:
            right.append(al)
    far_l = min(left, key=lambda a: a.y_at(0.0)) if left else None
    far_r = max(right, key=lambda a: a.y_at(0.0)) if right else None
    return far_l, far_r


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
    traj_v: list[float] = field(default_factory=list)
    traj_d_see_m: float = 0.0
    traj_t_plan_s: float = 0.0
    traj_v_plan_mps: float = 0.0
    traj_horizon_m: float = 0.0
    allow_lc: bool = False
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
    """Fallback when `points_v_mps` is empty: this-tick thr−brk."""
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


def traj_color_for_v(v: float, v_hi: float = 12.0) -> tuple[int, int, int]:
    """Plan speed: red stop → amber crawl → green cruise."""
    t = max(0.0, min(1.0, float(v) / max(float(v_hi), 1.0)))
    if t < 0.45:
        u = t / 0.45
        return (
            int(220 + (230 - 220) * u),
            int(70 + (180 - 70) * u),
            int(70 + (60 - 70) * u),
        )
    u = (t - 0.45) / 0.55
    return (
        int(230 + (70 - 230) * u),
        int(180 + (210 - 180) * u),
        int(60 + (110 - 60) * u),
    )


def traj_seg_thickness(v0: float, v1: float) -> int:
    """Thicker where the plan is cutting speed."""
    dv = float(v1) - float(v0)
    if dv < -1.0:
        return 5
    if dv > 1.0:
        return 4
    return 3


# 5×7 column bitmaps (LSB = top). Digits + a few HUD letters.
_FONT5: dict[str, tuple[int, ...]] = {
    "0": (0x3E, 0x45, 0x49, 0x51, 0x3E),
    "1": (0x00, 0x21, 0x7F, 0x01, 0x00),
    "2": (0x21, 0x43, 0x45, 0x49, 0x31),
    "3": (0x42, 0x41, 0x51, 0x69, 0x46),
    "4": (0x0C, 0x14, 0x24, 0x7F, 0x04),
    "5": (0x72, 0x51, 0x51, 0x51, 0x4E),
    "6": (0x3E, 0x49, 0x49, 0x49, 0x26),
    "7": (0x40, 0x47, 0x48, 0x50, 0x60),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36),
    "9": (0x32, 0x49, 0x49, 0x49, 0x3E),
    ".": (0x00, 0x00, 0x03, 0x00, 0x00),
    " ": (0x00, 0x00, 0x00, 0x00, 0x00),
    "V": (0x7C, 0x02, 0x01, 0x02, 0x7C),
    "D": (0x7F, 0x41, 0x41, 0x41, 0x3E),
    "T": (0x40, 0x40, 0x7F, 0x40, 0x40),
    "L": (0x7F, 0x01, 0x01, 0x01, 0x01),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22),
}


def _blit_text(
    buf: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    rgb: tuple[int, int, int],
    *,
    scale: int = 1,
) -> None:
    cx = x
    sc = max(1, int(scale))
    for ch in text.upper():
        cols = _FONT5.get(ch, _FONT5[" "])
        for ci, bits in enumerate(cols):
            for row in range(7):
                if bits & (1 << row):
                    px = cx + ci * sc
                    py = y + row * sc
                    _fill_rect(buf, width, height, px, py, px + sc, py + sc, rgb)
        cx += (5 + 1) * sc


def render_ego_bev_png(st: LiveBevState, *, width: int = 480, height: int = 360) -> bytes:
    """Lane-anchored perception view: behind-above pinhole, +x road, +y left.

    Ego-frame polys/objects from FCM are rotated into the road frame. Dashed
    marks are 6 m paint + 9 m gap in road metres. Canvas D_bev.
    """
    import math

    bg = (24, 28, 36)
    lh_c = (235, 235, 250)
    la_c = (170, 175, 190)
    dash_c = (200, 200, 90)
    ego_c = (80, 200, 120)
    uss_c = (220, 180, 60)
    text_bar = (40, 44, 55)
    tick_c = (168, 168, 172)
    tick_major_c = (200, 200, 204)
    cipv_outline = (245, 245, 250)

    buf = bytearray(bytes(bg) * (width * height))
    _fill_rect(buf, width, height, 0, 0, width, 28, text_bar)

    cam = make_bev_cam(width, height)
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
    else:
        y_span_min, y_span_max = -half, half
    y_mid = 0.5 * (y_span_min + y_span_max)

    scroll = float(st.odom_m) % DASH_PERIOD_M
    # Draw horizon = min(canvas, host VR). Never extrapolate past Out VR_End.
    host_vr = D_BEV_M
    if st.host_lanes:
        host_vr = min(D_BEV_M, max(p.x1 for p in st.host_lanes))
    x_draw = max(0.0, host_vr)
    tick_stub_m = 0.55

    def e2p_road(xr: float, yr: float, zr: float = 0.0) -> tuple[int, int]:
        return cam.project(xr, yr - y_mid, zr)

    def e2p_ego(xe: float, ye: float, zr: float = 0.0) -> tuple[int, int]:
        xr, yr = ego_to_road(xe, ye)
        return e2p_road(xr, yr, zr)

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
        prev_lit = False
        span = x_hi - x_lo
        steps = max(48, int(span * 2) + 1)
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
            lit = (not dashed) or dash_lit_m(xe, scroll_m=scroll)
            if prev is not None and lit and prev_lit:
                _line(buf, width, height, prev[0], prev[1], pt[0], pt[1], color, thick=thick)
            prev = pt
            prev_lit = lit

    def _pix_on_canvas(pt: tuple[int, int]) -> bool:
        return 0 <= pt[0] < width and 28 <= pt[1] < height

    # Host-lane teal to D_see. Gray FCM marks still go to VR.
    d_see = 0.0
    if st.host_lanes:
        host_ends = [float(p.x1) for p in st.host_lanes if float(p.x1) > 0.5]
        if host_ends:
            d_see = min(host_ends)
    blockers_early = list(st.perc_objects)
    occupy_open = see_opening_m(d_see, blockers_early)
    opening = driving_see_m(st, d_see, blockers_early)
    xe_cap = see_cap_x_m(opening, x_draw)
    if xe_cap >= 2.0 and (left_poly is not None or right_poly is not None):
        steps_s = max(24, int(xe_cap) // 2 + 1)
        prev_l: tuple[int, int] | None = None
        prev_r: tuple[int, int] | None = None
        for i in range(steps_s + 1):
            xe = min(xe_cap, xe_cap * i / max(1, steps_s))
            if left_poly is not None and xe > left_poly.x1:
                continue
            if right_poly is not None and xe > right_poly.x1:
                continue
            pl = e2p_ego(xe, _host_y_ego(xe, "l"))
            pr = e2p_ego(xe, _host_y_ego(xe, "r"))
            if not (_pix_on_canvas(pl) or _pix_on_canvas(pr)):
                prev_l, prev_r = None, None
                continue
            if prev_l is not None and prev_r is not None:
                fill_convex_poly(
                    buf,
                    width,
                    height,
                    [prev_r, prev_l, pl, pr],
                    _SEE_FILL,
                    y_clip0=28,
                )
            prev_l, prev_r = pl, pr

    for hl in st.host_lanes:
        _draw_poly_road(hl, lh_c, thick=3, dashed=hl.is_dashed)
    # No fallback schematic host when Out says unavailable.
    for al in st.adj_lanes:
        _draw_poly_road(al, la_c, thick=2, dashed=al.is_dashed)

    # Host center dashes only inside the visible patch. Distance ticks still follow VR.
    if x_draw > 0.5 and st.host_lanes:
        y_host_mid_e = 0.5 * (_host_y_ego(0.0, "l") + _host_y_ego(0.0, "r"))
        dash_hi = xe_cap if xe_cap >= 2.0 else x_draw

        def _pt_at_road_x(xr: float) -> tuple[int, int]:
            xe = xr * c_psi
            ye = 0.5 * (_host_y_ego(xe, "l") + _host_y_ego(xe, "r"))
            return e2p_ego(xe, ye)

        k0 = int(math.floor((-DASH_PERIOD_M - scroll) / DASH_PERIOD_M))
        k1 = int(math.ceil((x_draw + DASH_PERIOD_M - scroll) / DASH_PERIOD_M))
        for k in range(k0, k1 + 1):
            x0 = float(k) * DASH_PERIOD_M - scroll
            x1 = x0 + DASH_ON_M
            if x1 < 0.0 or x0 > dash_hi:
                continue
            p0, p1 = _pt_at_road_x(max(0.0, x0)), _pt_at_road_x(min(dash_hi, x1))
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
        nseg = min(len(st.traj_x), len(st.traj_y)) - 1
        has_v = len(st.traj_v) >= nseg + 1
        v_hi = 12.0
        if has_v:
            v_hi = max(12.0, max(st.traj_v[: nseg + 1]))
        fallback_c = traj_color_for_lon(st)
        fallback_th = traj_thickness_for_lon(st)
        x_hi = opening if opening > 0.5 else x_draw
        for i in range(nseg):
            x0, y0 = float(st.traj_x[i]), float(st.traj_y[i])
            x1, y1 = float(st.traj_x[i + 1]), float(st.traj_y[i + 1])
            if min(x0, x1) > x_hi:
                break
            if x1 > x_hi and x1 > x0 + 1e-6:
                t = (x_hi - x0) / (x1 - x0)
                y1 = y0 + t * (y1 - y0)
                x1 = x_hi
            a = e2p_ego(x0, y0)
            b = e2p_ego(x1, y1)
            if has_v:
                v0 = st.traj_v[i]
                v1 = st.traj_v[min(i + 1, len(st.traj_v) - 1)]
                col = traj_color_for_v(0.5 * (v0 + v1), v_hi)
                th = traj_seg_thickness(v0, v1)
            else:
                col = fallback_c
                th = fallback_th
            _line(buf, width, height, a[0], a[1], b[0], b[1], col, thick=th)

    if opening >= 2.0:
        xe_see = xe_cap if xe_cap >= 2.0 else see_cap_x_m(opening, x_draw)
        pL = ego_to_road(xe_see, _host_y_ego(xe_see, "l"))
        pR = ego_to_road(xe_see, _host_y_ego(xe_see, "r"))
        far_l = far_r = None
        if occupy_notched(d_see, occupy_open):
            al_l, al_r = see_far_adj(st.adj_lanes, occupy_open)
            if al_l is not None:
                xe_f = min(float(al_l.x1), D_BEV_M)
                far_l = ego_to_road(xe_f, al_l.y_at(xe_f))
            if al_r is not None:
                xe_f = min(float(al_r.x1), D_BEV_M)
                far_r = ego_to_road(xe_f, al_r.y_at(xe_f))
        segs, tris = d_see_paint_marks(
            (pL[0], pL[1], pR[0], pR[1]),
            far_left=far_l,
            far_right=far_r,
        )
        for tri in tris:
            fill_convex_poly(
                buf,
                width,
                height,
                [e2p_road(px, py) for px, py in tri],
                _SEE_FILL,
                y_clip0=28,
            )
        if xe_see >= 2.0 and (left_poly is not None or right_poly is not None):
            xe_lip = max(0.0, xe_see - _SEE_CAP_LIP_M)
            fill_convex_poly(
                buf,
                width,
                height,
                [
                    e2p_ego(xe_lip, _host_y_ego(xe_lip, "r")),
                    e2p_ego(xe_lip, _host_y_ego(xe_lip, "l")),
                    e2p_ego(xe_see, _host_y_ego(xe_see, "l")),
                    e2p_ego(xe_see, _host_y_ego(xe_see, "r")),
                ],
                _SEE_CAP,
                y_clip0=28,
            )
        for x0, y0, x1, y1 in segs[1:]:
            pa, pb = e2p_road(x0, y0), e2p_road(x1, y1)
            dash_line(buf, width, height, pa[0], pa[1], pb[0], pb[1], _SEE_CAP, thick=2)

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

    def _paint_box_road(
        xe: float,
        ye: float,
        length_m: float,
        width_m: float,
        heading_ego: float,
        fill: tuple[int, int, int],
        *,
        outline: tuple[int, int, int] | None = None,
        height_m: float = 1.5,
    ) -> None:
        xr, yr = ego_to_road(xe, ye)
        heading_r = heading_ego - psi
        c = math.cos(heading_r)
        s = math.sin(heading_r)
        hl = 0.5 * max(float(length_m), 1.2)
        hw = 0.5 * max(float(width_m), 1.0)
        hh = max(0.6, float(height_m))
        corners_m = (
            (xr + hl * c - hw * s, yr + hl * s + hw * c),
            (xr + hl * c + hw * s, yr + hl * s - hw * c),
            (xr - hl * c + hw * s, yr - hl * s - hw * c),
            (xr - hl * c - hw * s, yr - hl * s + hw * c),
        )
        bot = [e2p_road(pxr, pyr, 0.0) for pxr, pyr in corners_m]
        top = [e2p_road(pxr, pyr, hh) for pxr, pyr in corners_m]
        shade = (
            max(0, int(fill[0] * 0.55)),
            max(0, int(fill[1] * 0.55)),
            max(0, int(fill[2] * 0.55)),
        )
        fill_convex_poly(buf, width, height, bot, shade, y_clip0=28)
        for i in range(4):
            fill_convex_poly(
                buf,
                width,
                height,
                [bot[i], bot[(i + 1) % 4], top[(i + 1) % 4], top[i]],
                fill,
                y_clip0=28,
            )
        fill_convex_poly(
            buf, width, height, top, fill, outline=outline, y_clip0=28
        )

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
            height_m=obj_height_m(int(obj.obj_class)),
        )

    # Ego: nose relative to road = -psi
    _paint_box_road(0.0, 0.0, 4.5, 1.8, 0.0, ego_c, height_m=1.5)

    bar_w = int(min(120, max(8, st.speed_mps * 6)))
    _fill_rect(buf, width, height, 8, 6, 8 + bar_w, 14, (80, 180, 90))
    v_plan = float(st.traj_v_plan_mps)
    if v_plan <= 0.0 and st.traj_v:
        v_plan = float(st.traj_v[0])
    plan_w = int(min(120, max(4, v_plan * 6)))
    _fill_rect(buf, width, height, 8, 15, 8 + plan_w, 22, (80, 190, 210))
    spark = 8 + int(st.odom_m * 10) % max(1, width - 16)
    _fill_rect(buf, width, height, spark, 6, spark + 3, 22, (240, 240, 80))

    hud = f"V{v_plan:4.1f} D{opening:3.0f} T{float(st.traj_t_plan_s):3.1f}"
    if st.allow_lc:
        hud += " LC"
    _blit_text(buf, width, height, 140, 7, hud, (220, 224, 230), scale=1)

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
        if data.get("target_speed_mps") is not None:
            self.state.traj_v_plan_mps = float(data["target_speed_mps"])
        if data.get("D_see_m") is not None:
            self.state.traj_d_see_m = float(data["D_see_m"])
        if data.get("T_plan_s") is not None:
            self.state.traj_t_plan_s = float(data["T_plan_s"])
        if data.get("horizon_m") is not None:
            self.state.traj_horizon_m = float(data["horizon_m"])
        if data.get("allow_lc") is not None:
            self.state.allow_lc = bool(int(data["allow_lc"]))

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
            vs = data.get("points_v_mps") or []
            if isinstance(xs, list) and isinstance(ys, list):
                self.state.traj_x = [float(x) for x in xs]
                self.state.traj_y = [float(y) for y in ys]
            if isinstance(vs, list):
                self.state.traj_v = [float(v) for v in vs]
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
