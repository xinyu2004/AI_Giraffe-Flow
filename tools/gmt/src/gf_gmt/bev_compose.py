"""Compose BEV images from live module topics (+ optional scenario script).

Primary inputs (iceoryx → tap NDJSON):
  /gf/EgoMotion   — ego speed / steer
  /gf/Trajectory  — path polyline (ego-frame: x forward, y left)
  /gf/UssZones    — optional nearest_cm (when tap supports it)

Optional story enrichment (NOT published to Foxglove):
  --bev-script JSONL AdasDemo frames → phase / lead / lane_offset drawn into Image

Output topic: /gf/camera/front/compressed (foxglove.CompressedImage JSON).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gf_gmt.adas_scenarios import (
    TOPIC_ADAS,
    TOPIC_CAM,
    TOPIC_EGO,
    TOPIC_TRAJ,
    FrameState,
    LEFT_LANE_Y,
    RIGHT_LANE_Y,
    compressed_image_msg,
    render_bev_png,
    _fill_rect,
    _line,
    _png_rgb,
    _set_pixel,
)

TOPIC_USS = "/gf/UssZones"


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
    # Optional AdasDemo
    has_adas: bool = False
    phase: str = ""
    lead_dist_m: float = 0.0
    accel_cmd_mps2: float = 0.0
    brake_active: int = 0
    lane_offset_m: float = 0.0
    cipo_x_m: float = 0.0
    cipo_y_m: float = 0.0
    scenario_id: str = ""


def render_ego_bev_png(st: LiveBevState, *, width: int = 480, height: int = 360) -> bytes:
    """Ego-centric dual-lane BEV; ground scrolls with odom_m so motion is visible."""
    bg = (24, 28, 36)
    asphalt = (42, 46, 54)
    lane = (200, 200, 210)
    dash_c = (160, 160, 80)
    ego_c = (80, 200, 120)
    traj_c = (90, 160, 255)
    uss_c = (220, 180, 60)
    text_bar = (40, 44, 55)
    tick_c = (70, 90, 110)

    buf = bytearray(bytes(bg) * (width * height))
    _fill_rect(buf, width, height, 0, 0, width, 28, text_bar)

    scale = 8.0
    ox, oy = width // 2, height - 50
    # Scroll ground toward ego (positive odom → dashes move down / toward bottom)
    scroll = st.odom_m % 8.0

    def e2p(xm: float, ym: float) -> tuple[int, int]:
        return int(ox - ym * scale), int(oy - xm * scale)

    y_re = RIGHT_LANE_Y - 1.75
    y_mid = 1.75
    y_le = LEFT_LANE_Y + 1.75
    for xi in range(0, 45):
        xm = float(xi)
        for ym_i in range(int(y_re * 10), int(y_le * 10) + 1):
            px, py = e2p(xm, ym_i / 10.0)
            _set_pixel(buf, width, height, px, py, asphalt)
    for y_lane in (y_re, y_le):
        p0, p1 = e2p(0.0, y_lane), e2p(42.0, y_lane)
        _line(buf, width, height, p0[0], p0[1], p1[0], p1[1], lane, thick=2)

    # Dashed center line — phase shifts with odom so the road "moves"
    for seg in range(-8, 48, 4):
        x0 = float(seg) - scroll
        x1 = x0 + 2.0
        if x1 < 0 or x0 > 42:
            continue
        p0, p1 = e2p(max(0.0, x0), y_mid), e2p(min(42.0, x1), y_mid)
        _line(buf, width, height, p0[0], p0[1], p1[0], p1[1], dash_c, thick=2)

    # Lateral tick marks every 5 m (also scrolled) — strong motion cue
    for k in range(-2, 12):
        xm = (k * 5.0) - (st.odom_m % 5.0)
        if xm < 0 or xm > 40:
            continue
        p0, p1 = e2p(xm, y_re + 0.2), e2p(xm, y_re + 0.8)
        _line(buf, width, height, p0[0], p0[1], p1[0], p1[1], tick_c, thick=1)
        p0, p1 = e2p(xm, y_le - 0.8), e2p(xm, y_le - 0.2)
        _line(buf, width, height, p0[0], p0[1], p1[0], p1[1], tick_c, thick=1)

    if len(st.traj_x) >= 2:
        for i in range(len(st.traj_x) - 1):
            a = e2p(st.traj_x[i], st.traj_y[i])
            b = e2p(st.traj_x[i + 1], st.traj_y[i + 1])
            _line(buf, width, height, a[0], a[1], b[0], b[1], traj_c, thick=2)

    if st.nearest_cm is not None and st.nearest_cm > 0:
        dist_m = float(st.nearest_cm) / 100.0
        dist_m = max(0.5, min(dist_m, 40.0))
        cx, cy = e2p(dist_m, 0.0)
        _fill_rect(buf, width, height, cx - 8, cy - 8, cx + 8, cy + 8, uss_c)

    ex, ey = e2p(0.0, 0.0)
    _fill_rect(buf, width, height, ex - 12, ey - 18, ex + 12, ey + 18, ego_c)

    # Speed bar + small odom hash so consecutive PNGs differ even at const speed
    bar_w = int(min(200, max(8, st.speed_mps * 6)))
    _fill_rect(buf, width, height, 8, 6, 8 + bar_w, 22, (80, 180, 90))
    # 1px odom spark in the banner (changes every ~0.1 m)
    spark = 8 + int(st.odom_m * 10) % max(1, width - 16)
    _fill_rect(buf, width, height, spark, 6, spark + 3, 22, (240, 240, 80))

    return _png_rgb(width, height, bytes(buf))


class LiveBevComposer:
    """Accumulate tap/session rows → optional CompressedImage row."""

    def __init__(self, *, script: AdasScriptIndex | None = None) -> None:
        self.state = LiveBevState()
        self._emit_every = 1
        self._n = 0
        self._script = script

    def _apply_adas_data(self, data: dict[str, Any]) -> None:
        self.state.has_adas = True
        self.state.phase = str(data.get("phase") or "")
        self.state.lead_dist_m = float(data.get("lead_dist_m") or 0.0)
        self.state.accel_cmd_mps2 = float(data.get("accel_cmd_mps2") or 0.0)
        self.state.brake_active = int(data.get("brake_active") or 0)
        self.state.lane_offset_m = float(data.get("lane_offset_m") or 0.0)
        self.state.cipo_x_m = float(data.get("cipo_x_m") or self.state.lead_dist_m)
        self.state.cipo_y_m = float(data.get("cipo_y_m") or 0.0)
        self.state.scenario_id = str(data.get("scenario_id") or "")
        if data.get("speed_mps") is not None:
            self.state.speed_mps = float(data["speed_mps"])

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
        elif self.state._last_t_ns == 0:
            # first sample: nudge so first frames still differ after start
            self.state.odom_m += max(0.0, speed_mps) * 0.05
        self.state._last_t_ns = t_ns

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
            if data.get("timestamp_ns"):
                self.state.t_ns = int(data["timestamp_ns"])
            self._maybe_script_at(self.state.t_ns or t_ns)
            emit = True
        elif "UssZones" in leaf or leaf == TOPIC_USS:
            if data.get("nearest_cm") is not None:
                self.state.nearest_cm = float(data["nearest_cm"])
            emit = True
        elif leaf.endswith("AdasDemo") or leaf == TOPIC_ADAS:
            # Allowed in NDJSON for offline/jsonl; not forwarded to Studio.
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
        if self.state.has_adas:
            lo = self.state.lane_offset_m
            # Scenario story path follows lane_offset — ignore stub Trajectory crooks.
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
                lead_rel_v_mps=0.0,
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
