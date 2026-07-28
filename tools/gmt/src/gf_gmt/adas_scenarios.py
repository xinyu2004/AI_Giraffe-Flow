"""ADAS demo scenarios (ACC / AEB / lane-change) — Phase 0, no Vision Pilot.

Produces session JSONL compatible with GMT + Foxglove replay, plus optional
synthetic BEV frames (stdlib PNG, no Pillow).
"""

from __future__ import annotations

import base64
import json
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


TOPIC_EGO = "/gf/EgoMotion"
TOPIC_TRAJ = "/gf/Trajectory"
TOPIC_ADAS = "/gf/AdasDemo"
TOPIC_CAM = "/gf/camera/front/compressed"

HZ = 10
DT_NS = int(1e9 / HZ)


def _png_rgb(width: int, height: int, rgb: bytes) -> bytes:
    """Minimal RGB PNG encoder (stdlib only)."""
    if len(rgb) != width * height * 3:
        raise ValueError("rgb size mismatch")

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(
        b"\x00" + rgb[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def _set_pixel(buf: bytearray, w: int, h: int, x: int, y: int, rgb: tuple[int, int, int]) -> None:
    if x < 0 or y < 0 or x >= w or y >= h:
        return
    i = (y * w + x) * 3
    buf[i] = rgb[0]
    buf[i + 1] = rgb[1]
    buf[i + 2] = rgb[2]


def _fill_rect(
    buf: bytearray,
    w: int,
    h: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rgb: tuple[int, int, int],
) -> None:
    for y in range(max(0, y0), min(h, y1)):
        for x in range(max(0, x0), min(w, x1)):
            _set_pixel(buf, w, h, x, y, rgb)


def _line(
    buf: bytearray,
    w: int,
    h: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rgb: tuple[int, int, int],
    thick: int = 1,
) -> None:
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        for oy in range(-thick // 2, thick // 2 + 1):
            for ox in range(-thick // 2, thick // 2 + 1):
                _set_pixel(buf, w, h, x + ox, y + oy, rgb)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


@dataclass
class FrameState:
    t_ns: int
    scenario_id: str
    phase: str
    speed_mps: float
    yaw_rate_degps: float
    steer_angle_deg: float
    gear: int
    lead_dist_m: float
    lead_rel_v_mps: float
    accel_cmd_mps2: float
    brake_active: int
    lane_offset_m: float
    cipo_x_m: float
    cipo_y_m: float
    traj_x: list[float]
    traj_y: list[float]


LANE_WIDTH_M = 3.5
RIGHT_LANE_Y = 0.0
LEFT_LANE_Y = LANE_WIDTH_M  # 3.5 — second lane center


def render_bev_png(st: FrameState, *, width: int = 480, height: int = 360) -> bytes:
    """Top-down sketch: **two lanes**, ego, lead, trajectory (world y), phase banner."""
    bg = (24, 28, 36)
    asphalt = (42, 46, 54)
    lane = (200, 200, 210)
    dash_c = (160, 160, 80)
    ego_c = (80, 200, 120)
    lead_c = (220, 90, 90)
    traj_c = (90, 160, 255)
    text_bar = (40, 44, 55)

    buf = bytearray(bytes(bg) * (width * height))
    _fill_rect(buf, width, height, 0, 0, width, 28, text_bar)

    # World → pixel: camera follows ego laterally; +x forward (up), +y left
    scale = 8.0  # px / m
    ox, oy = width // 2, height - 50

    def w2p(xm: float, ym: float) -> tuple[int, int]:
        px = int(ox - (ym - st.lane_offset_m) * scale)
        py = int(oy - xm * scale)
        return px, py

    # Two-lane road: centers at y=0 (right) and y=3.5 (left); edges ±half-width
    y_right_edge = RIGHT_LANE_Y - LANE_WIDTH_M / 2  # -1.75
    y_mid = (RIGHT_LANE_Y + LEFT_LANE_Y) / 2  # 1.75
    y_left_edge = LEFT_LANE_Y + LANE_WIDTH_M / 2  # 5.25

    # Asphalt band (sample along x, fill between outer edges in pixel space)
    for xi in range(0, 45):
        xm = float(xi)
        for ym_i in range(int(y_right_edge * 10), int(y_left_edge * 10) + 1):
            ym = ym_i / 10.0
            px, py = w2p(xm, ym)
            _set_pixel(buf, width, height, px, py, asphalt)

    # Solid outer lane lines
    for y_lane in (y_right_edge, y_left_edge):
        p0 = w2p(0.0, y_lane)
        p1 = w2p(42.0, y_lane)
        _line(buf, width, height, p0[0], p0[1], p1[0], p1[1], lane, thick=2)
    # Dashed center line between the two lanes
    for seg in range(0, 42, 4):
        p0 = w2p(float(seg), y_mid)
        p1 = w2p(float(seg + 2), y_mid)
        _line(buf, width, height, p0[0], p0[1], p1[0], p1[1], dash_c, thick=2)

    # Trajectory in **world** y (must stay on a lane center after settle)
    if len(st.traj_x) >= 2:
        for i in range(len(st.traj_x) - 1):
            a = w2p(st.traj_x[i], st.traj_y[i])
            b = w2p(st.traj_x[i + 1], st.traj_y[i + 1])
            _line(buf, width, height, a[0], a[1], b[0], b[1], traj_c, thick=2)

    # Lead vehicle (world)
    if st.lead_dist_m > 0.5:
        lx, ly = st.cipo_x_m, st.cipo_y_m
        cx, cy = w2p(lx, ly)
        _fill_rect(buf, width, height, cx - 10, cy - 16, cx + 10, cy + 16, lead_c)

    # Ego at (0, lane_offset_m) in world
    ex, ey = w2p(0.0, st.lane_offset_m)
    _fill_rect(buf, width, height, ex - 12, ey - 18, ex + 12, ey + 18, ego_c)

    phase_color = {
        "cruise": (80, 180, 90),
        "follow": (200, 180, 60),
        "brake": (220, 60, 60),
        "stopped": (160, 40, 40),
        "prepare": (100, 140, 220),
        "changing": (180, 100, 220),
        "done": (80, 180, 90),
    }.get(st.phase, (150, 150, 150))
    _fill_rect(buf, width, height, 8, 6, 8 + 40, 22, phase_color)
    if st.brake_active:
        _fill_rect(buf, width, height, width - 48, 6, width - 8, 22, (255, 40, 40))

    return _png_rgb(width, height, bytes(buf))


def compressed_image_msg(t_ns: int, png: bytes, *, frame_id: str = "front") -> dict[str, Any]:
    sec = int(t_ns // 1_000_000_000)
    nsec = int(t_ns % 1_000_000_000)
    return {
        "timestamp": {"sec": sec, "nsec": nsec},
        "frame_id": frame_id,
        "format": "png",
        "data": base64.b64encode(png).decode("ascii"),
    }


def _traj_points_world(
    length_m: float,
    y0: float,
    y1: float,
    n: int = 12,
) -> tuple[list[float], list[float]]:
    """Polyline in world frame: x forward from ego, y = lane lateral."""
    xs: list[float] = []
    ys: list[float] = []
    for i in range(n):
        u = i / max(1, n - 1)
        xs.append(u * length_m)
        ys.append(_lerp(y0, y1, u * u * (3 - 2 * u)))
    return xs, ys


def _traj_points(length_m: float, lateral_m: float, n: int = 12) -> tuple[list[float], list[float]]:
    """Legacy helper: world traj along y=0 → y=lateral_m (right→target)."""
    return _traj_points_world(length_m, RIGHT_LANE_Y, lateral_m, n=n)


def _ego_data(st: FrameState) -> dict[str, Any]:
    return {
        "timestamp_ns": st.t_ns,
        "speed_mps": round(st.speed_mps, 4),
        "yaw_rate_degps": round(st.yaw_rate_degps, 4),
        "steer_angle_deg": round(st.steer_angle_deg, 4),
        "gear": int(st.gear),
    }


def _traj_data(st: FrameState) -> dict[str, Any]:
    return {
        "timestamp_ns": st.t_ns,
        "point_count": len(st.traj_x),
        "points_x_m": [round(x, 4) for x in st.traj_x],
        "points_y_m": [round(y, 4) for y in st.traj_y],
        "gear_shift_first": 0,
        "gear_shift_second": 0,
    }


def _adas_data(st: FrameState) -> dict[str, Any]:
    return {
        "scenario_id": st.scenario_id,
        "phase": st.phase,
        "lead_dist_m": round(st.lead_dist_m, 4),
        "lead_rel_v_mps": round(st.lead_rel_v_mps, 4),
        "accel_cmd_mps2": round(st.accel_cmd_mps2, 4),
        "brake_active": int(st.brake_active),
        "lane_offset_m": round(st.lane_offset_m, 4),
        "cipo_x_m": round(st.cipo_x_m, 4),
        "cipo_y_m": round(st.cipo_y_m, 4),
        "speed_mps": round(st.speed_mps, 4),
    }


def frames_to_rows(frames: Iterable[FrameState]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for st in frames:
        rows.append({"t_ns": st.t_ns, "topic": TOPIC_EGO, "data": _ego_data(st)})
        rows.append({"t_ns": st.t_ns, "topic": TOPIC_TRAJ, "data": _traj_data(st)})
        rows.append({"t_ns": st.t_ns, "topic": TOPIC_ADAS, "data": _adas_data(st)})
    return rows


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def gen_acc_follow(*, duration_s: float = 30.0) -> list[FrameState]:
    """Cruise → close gap / decelerate → accelerate with lead → cruise."""
    n = int(duration_s * HZ)
    out: list[FrameState] = []
    speed = 25.0
    lead = 40.0
    for i in range(n):
        t = i / HZ
        t_ns = i * DT_NS
        if t < 8:
            phase = "cruise"
            accel = 0.0
            speed = 25.0
            lead = 40.0 - 0.3 * t
        elif t < 16:
            phase = "follow"
            u = (t - 8) / 8
            accel = _lerp(0.0, -2.0, u)
            speed = max(12.0, 25.0 + accel * (t - 8) * 0.5)
            lead = _lerp(37.0, 18.0, u)
        elif t < 24:
            phase = "follow"
            u = (t - 16) / 8
            accel = _lerp(-0.5, 1.2, u)
            speed = min(25.0, 14.0 + 1.2 * (t - 16))
            lead = _lerp(18.0, 28.0, u)
        else:
            phase = "cruise"
            accel = 0.0
            speed = 25.0
            lead = 30.0
        xs, ys = _traj_points_world(35.0, RIGHT_LANE_Y, RIGHT_LANE_Y)
        out.append(
            FrameState(
                t_ns=t_ns,
                scenario_id="acc_follow",
                phase=phase,
                speed_mps=speed,
                yaw_rate_degps=0.0,
                steer_angle_deg=0.0,
                gear=4,
                lead_dist_m=lead,
                lead_rel_v_mps=-0.5 if phase == "follow" else 0.0,
                accel_cmd_mps2=accel,
                brake_active=0,
                lane_offset_m=RIGHT_LANE_Y,
                cipo_x_m=lead,
                cipo_y_m=RIGHT_LANE_Y,
                traj_x=xs,
                traj_y=ys,
            )
        )
    return out


def gen_aeb_cutin(*, duration_s: float = 25.0) -> list[FrameState]:
    """Normal follow → sudden close → hard brake → near stop."""
    n = int(duration_s * HZ)
    out: list[FrameState] = []
    for i in range(n):
        t = i / HZ
        t_ns = i * DT_NS
        if t < 6:
            phase = "cruise"
            speed = 20.0
            lead = 35.0
            accel = 0.0
            brake = 0
        elif t < 9:
            phase = "follow"
            u = (t - 6) / 3
            speed = 20.0
            lead = _lerp(35.0, 12.0, u)  # cut-in
            accel = -1.0
            brake = 0
        elif t < 14:
            phase = "brake"
            u = (t - 9) / 5
            accel = -6.0
            speed = max(0.5, 20.0 - 6.0 * (t - 9))
            lead = max(2.0, _lerp(12.0, 3.0, u))
            brake = 1
        else:
            phase = "stopped"
            speed = 0.0
            lead = 3.0
            accel = 0.0
            brake = 1 if t < 18 else 0
        xs, ys = _traj_points_world(max(8.0, speed * 1.5), RIGHT_LANE_Y, RIGHT_LANE_Y)
        out.append(
            FrameState(
                t_ns=t_ns,
                scenario_id="aeb_cutin",
                phase=phase,
                speed_mps=speed,
                yaw_rate_degps=0.0,
                steer_angle_deg=0.0,
                gear=4 if speed > 0.1 else 0,
                lead_dist_m=lead,
                lead_rel_v_mps=-8.0 if phase == "brake" else -1.0,
                accel_cmd_mps2=accel,
                brake_active=brake,
                lane_offset_m=RIGHT_LANE_Y,
                cipo_x_m=lead,
                cipo_y_m=RIGHT_LANE_Y + (0.2 if 6 <= t < 9 else 0.0),
                traj_x=xs,
                traj_y=ys,
            )
        )
    return out


def gen_lane_change(*, duration_s: float = 28.0) -> list[FrameState]:
    """Straight → prepare → change to left lane → settle on left lane."""
    n = int(duration_s * HZ)
    out: list[FrameState] = []
    for i in range(n):
        t = i / HZ
        t_ns = i * DT_NS
        speed = 22.0
        lead = 45.0
        if t < 6:
            phase = "cruise"
            offset = RIGHT_LANE_Y
            yaw = 0.0
            steer = 0.0
            target_lat = RIGHT_LANE_Y
        elif t < 10:
            phase = "prepare"
            u = (t - 6) / 4
            offset = RIGHT_LANE_Y
            yaw = 0.0
            steer = _lerp(0.0, 4.0, u)
            target_lat = LEFT_LANE_Y
        elif t < 18:
            phase = "changing"
            u = (t - 10) / 8
            offset = _lerp(RIGHT_LANE_Y, LEFT_LANE_Y, u * u * (3 - 2 * u))
            yaw = 4.0 * math.sin(math.pi * u)
            steer = 8.0 * math.sin(math.pi * u)
            target_lat = LEFT_LANE_Y
        else:
            phase = "done"
            offset = LEFT_LANE_Y
            yaw = 0.0
            steer = 0.0
            target_lat = LEFT_LANE_Y
        xs, ys = _traj_points_world(40.0, offset, target_lat)
        out.append(
            FrameState(
                t_ns=t_ns,
                scenario_id="lane_change",
                phase=phase,
                speed_mps=speed,
                yaw_rate_degps=yaw,
                steer_angle_deg=steer,
                gear=4,
                lead_dist_m=lead,
                lead_rel_v_mps=0.0,
                accel_cmd_mps2=0.0,
                brake_active=0,
                lane_offset_m=offset,
                cipo_x_m=lead,
                cipo_y_m=RIGHT_LANE_Y,  # slower traffic in right lane
                traj_x=xs,
                traj_y=ys,
            )
        )
    return out


def gen_overtake_acc_aeb(*, duration_s: float = 75.0) -> list[FrameState]:
    """One story: lane-change overtake → ACC follow → congestion AEB (two lanes).

    Timeline (default 75s @ 10Hz):
      0–20s   lane_change right→left (centers 0 → 3.5m)
      20–45s  ACC follow in **left** lane
      45–75s  AEB in left lane
    """
    n = int(duration_s * HZ)
    out: list[FrameState] = []
    lane_end = 20.0
    acc_end = 45.0

    for i in range(n):
        t = i / HZ
        t_ns = i * DT_NS

        if t < lane_end:
            if t < 4:
                phase = "cruise"
                offset = RIGHT_LANE_Y
                yaw = 0.0
                steer = 0.0
                target_lat = RIGHT_LANE_Y
            elif t < 8:
                phase = "prepare"
                u = (t - 4) / 4
                offset = RIGHT_LANE_Y
                yaw = 0.0
                steer = _lerp(0.0, 4.0, u)
                target_lat = LEFT_LANE_Y
            elif t < 16:
                phase = "changing"
                u = (t - 8) / 8
                offset = _lerp(RIGHT_LANE_Y, LEFT_LANE_Y, u * u * (3 - 2 * u))
                yaw = 4.0 * math.sin(math.pi * u)
                steer = 8.0 * math.sin(math.pi * u)
                target_lat = LEFT_LANE_Y
            else:
                phase = "done"
                offset = LEFT_LANE_Y
                yaw = 0.0
                steer = 0.0
                target_lat = LEFT_LANE_Y
            speed = 24.0
            lead = 50.0
            accel = 0.3 if t < 16 else 0.0
            brake = 0
            lead_rel = 2.0
            cipo_y = RIGHT_LANE_Y  # overtake vehicle still in right lane
            xs, ys = _traj_points_world(40.0, offset, target_lat)

        elif t < acc_end:
            phase = "follow"
            offset = LEFT_LANE_Y
            yaw = 0.0
            steer = 0.0
            u = (t - lane_end) / (acc_end - lane_end)
            if u < 0.4:
                uu = u / 0.4
                accel = _lerp(0.0, -1.8, uu)
                speed = _lerp(24.0, 16.0, uu)
                lead = _lerp(42.0, 22.0, uu)
            else:
                uu = (u - 0.4) / 0.6
                accel = _lerp(-0.4, 0.2, uu)
                speed = _lerp(16.0, 18.0, uu)
                lead = _lerp(22.0, 26.0, uu)
            brake = 0
            lead_rel = -1.0
            cipo_y = LEFT_LANE_Y  # lead ahead in same (left) lane
            xs, ys = _traj_points_world(35.0, LEFT_LANE_Y, LEFT_LANE_Y)

        else:
            offset = LEFT_LANE_Y
            yaw = 0.0
            steer = 0.0
            u = (t - acc_end) / max(1.0, duration_s - acc_end)
            if u < 0.15:
                phase = "follow"
                accel = -1.0
                speed = 18.0
                lead = _lerp(26.0, 12.0, u / 0.15)
                brake = 0
                lead_rel = -4.0
            elif u < 0.45:
                phase = "brake"
                uu = (u - 0.15) / 0.30
                accel = -6.5
                speed = max(0.3, _lerp(18.0, 0.5, uu))
                lead = max(2.5, _lerp(12.0, 3.0, uu))
                brake = 1
                lead_rel = -10.0
            else:
                phase = "stopped"
                accel = 0.0
                speed = 0.0
                lead = 3.0
                brake = 1 if u < 0.7 else 0
                lead_rel = 0.0
            cipo_y = LEFT_LANE_Y
            xs, ys = _traj_points_world(max(6.0, speed * 1.2), LEFT_LANE_Y, LEFT_LANE_Y)

        out.append(
            FrameState(
                t_ns=t_ns,
                scenario_id="overtake_acc_aeb",
                phase=phase,
                speed_mps=speed,
                yaw_rate_degps=yaw,
                steer_angle_deg=steer,
                gear=4 if speed > 0.15 else 0,
                lead_dist_m=lead,
                lead_rel_v_mps=lead_rel,
                accel_cmd_mps2=accel,
                brake_active=brake,
                lane_offset_m=offset,
                cipo_x_m=lead,
                cipo_y_m=cipo_y,
                traj_x=xs,
                traj_y=ys,
            )
        )
    return out


SCENARIO_GENERATORS: dict[str, Callable[..., list[FrameState]]] = {
    "overtake_acc_aeb": gen_overtake_acc_aeb,
    "acc_follow": gen_acc_follow,
    "aeb_cutin": gen_aeb_cutin,
    "lane_change": gen_lane_change,
}


def write_scenario_jsonl(path: Path, frames: list[FrameState]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = frames_to_rows(frames)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(rows)


def generate_all(out_dir: Path) -> dict[str, Path]:
    written: dict[str, Path] = {}
    for name, gen in SCENARIO_GENERATORS.items():
        p = out_dir / f"{name}.jsonl"
        write_scenario_jsonl(p, gen())
        written[name] = p
    return written


def iter_playback_rows(
    rows: list[dict[str, Any]],
    *,
    synth_bev: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield original rows; after each AdasDemo, optionally emit CompressedImage."""
    last_adas: dict[str, Any] | None = None
    last_traj: dict[str, Any] | None = None
    last_ego: dict[str, Any] | None = None
    for row in rows:
        topic = str(row.get("topic") or "")
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        if topic == TOPIC_EGO:
            last_ego = data
        elif topic == TOPIC_TRAJ:
            last_traj = data
        elif topic == TOPIC_ADAS:
            last_adas = data
        yield row
        if synth_bev and topic == TOPIC_ADAS and last_adas is not None:
            t_ns = int(row.get("t_ns") or 0)
            st = FrameState(
                t_ns=t_ns,
                scenario_id=str(last_adas.get("scenario_id") or "demo"),
                phase=str(last_adas.get("phase") or ""),
                speed_mps=float((last_ego or {}).get("speed_mps") or last_adas.get("speed_mps") or 0),
                yaw_rate_degps=float((last_ego or {}).get("yaw_rate_degps") or 0),
                steer_angle_deg=float((last_ego or {}).get("steer_angle_deg") or 0),
                gear=int((last_ego or {}).get("gear") or 0),
                lead_dist_m=float(last_adas.get("lead_dist_m") or 0),
                lead_rel_v_mps=float(last_adas.get("lead_rel_v_mps") or 0),
                accel_cmd_mps2=float(last_adas.get("accel_cmd_mps2") or 0),
                brake_active=int(last_adas.get("brake_active") or 0),
                lane_offset_m=float(last_adas.get("lane_offset_m") or 0),
                cipo_x_m=float(last_adas.get("cipo_x_m") or last_adas.get("lead_dist_m") or 0),
                cipo_y_m=float(last_adas.get("cipo_y_m") or 0),
                traj_x=list((last_traj or {}).get("points_x_m") or [0.0, 20.0]),
                traj_y=list((last_traj or {}).get("points_y_m") or [0.0, 0.0]),
            )
            png = render_bev_png(st)
            yield {
                "t_ns": t_ns,
                "topic": TOPIC_CAM,
                "data": compressed_image_msg(t_ns, png),
            }
