#!/usr/bin/env python3
"""CARLA tip bridge for afc_no_uss (P3-5 wave C).

Writes the wave-B frame file protocol for perception.fcm and executes
lane-change commands from vehicle_can_gateway (GF_CARLA_CMD_PATH).

Does not decide lane changes. CARLA is optional: dry-run or connect-fail
exits cleanly so SIL without UE still works.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Optional

STOP = False


def _env(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    return v if v else default


def _log(msg: str) -> None:
    print(f"[carla_bridge] {msg}", flush=True)


def _on_signal(signum: int, _frame: Any) -> None:
    global STOP
    STOP = True
    _log(f"signal {signum} → stop")


def sidecar_path(rgb_path: Path) -> Path:
    s = str(rgb_path)
    if s.endswith(".rgb"):
        return Path(s[:-4] + ".json")
    return Path(s + ".json")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_frame(
    rgb_path: Path,
    rgb: bytes,
    w: int,
    h: int,
    seq: int,
    timestamp_ns: int,
) -> None:
    stride = w * 3
    if len(rgb) < stride * h:
        raise ValueError(f"rgb too short: {len(rgb)} < {stride * h}")
    atomic_write_bytes(rgb_path, rgb[: stride * h])
    meta = {
        "w": w,
        "h": h,
        "stride": stride,
        "timestamp_ns": timestamp_ns,
        "seq": seq,
    }
    atomic_write_text(sidecar_path(rgb_path), json.dumps(meta, separators=(",", ":")))


def load_cmd(cmd_path: Path, last_seq: int, last_mtime: float) -> tuple[Optional[dict], int, float]:
    if not cmd_path.is_file():
        return None, last_seq, last_mtime
    try:
        mtime = cmd_path.stat().st_mtime
        data = json.loads(cmd_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, last_seq, last_mtime
    seq = int(data.get("seq", 0))
    if seq == last_seq and mtime == last_mtime:
        return None, last_seq, last_mtime
    return data, seq, mtime


def synth_rgb(w: int, h: int, seq: int) -> bytes:
    """Color-bar frame when CARLA is unavailable (dry-run)."""
    out = bytearray(w * h * 3)
    phase = seq & 0xFF
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 3
            out[i] = (x + phase) & 0xFF
            out[i + 1] = (y + phase // 2) & 0xFF
            out[i + 2] = (x + y + phase) & 0xFF
    return bytes(out)


def apply_lane_change(vehicle: Any, tm: Any, lane: str) -> None:
    lane = (lane or "none").lower()
    if lane == "none" or vehicle is None or tm is None:
        return
    # force_lane_change(actor, direction): True=left, False=right (CARLA API)
    if lane == "left":
        tm.force_lane_change(vehicle, True)
        _log("force_lane_change left")
    elif lane == "right":
        tm.force_lane_change(vehicle, False)
        _log("force_lane_change right")


def run_dry(
    rgb_path: Path,
    cmd_path: Path,
    w: int,
    h: int,
    period_s: float,
) -> int:
    _log(f"dry-run: writing synth frames → {rgb_path} (no CARLA)")
    seq = 0
    last_cmd_seq = -1
    last_cmd_mtime = -1.0
    while not STOP:
        seq += 1
        ts = time.time_ns()
        write_frame(rgb_path, synth_rgb(w, h, seq), w, h, seq, ts)
        cmd, last_cmd_seq, last_cmd_mtime = load_cmd(
            cmd_path, last_cmd_seq, last_cmd_mtime
        )
        if cmd:
            _log(
                f"dry-run cmd seq={cmd.get('seq')} lane_change={cmd.get('lane_change')} "
                f"speed_mps={cmd.get('speed_mps')}"
            )
        time.sleep(period_s)
    return 0


def run_carla(
    host: str,
    port: int,
    timeout_s: float,
    rgb_path: Path,
    cmd_path: Path,
    w: int,
    h: int,
    on_fail: str,
) -> int:
    try:
        import carla  # type: ignore
    except ImportError:
        _log("carla Python module not installed — see tools/carla_bridge/README.md")
        if on_fail == "idle":
            _log("idle without frames (GF_CARLA_BRIDGE_ON_FAIL=idle)")
            while not STOP:
                time.sleep(1.0)
            return 0
        return 0

    client = carla.Client(host, port)
    client.set_timeout(timeout_s)
    try:
        world = client.get_world()
    except Exception as e:  # noqa: BLE001 — soft fail for missing UE
        _log(f"connect {host}:{port} failed: {e}")
        if on_fail == "idle":
            while not STOP:
                time.sleep(1.0)
            return 0
        return 0

    _log(f"connected {host}:{port} map={world.get_map().name}")
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
    spawn_points = world.get_map().get_spawn_points()
    if not spawn_points:
        _log("no spawn points")
        return 0
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_points[0])
    if vehicle is None:
        vehicle = world.spawn_actor(vehicle_bp, spawn_points[0])
    vehicle.set_autopilot(True)
    tm = client.get_trafficmanager()
    tm.ignore_lights_percentage(vehicle, 100)

    cam_bp = blueprint_library.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", str(w))
    cam_bp.set_attribute("image_size_y", str(h))
    cam_bp.set_attribute("fov", "90")
    cam_transform = carla.Transform(carla.Location(x=1.5, z=2.4))
    camera = world.spawn_actor(cam_bp, cam_transform, attach_to=vehicle)

    seq_holder = {"seq": 0}
    last_cmd = {"seq": -1, "mtime": -1.0}

    def on_image(image: Any) -> None:
        if STOP:
            return
        # CARLA raw: BGRA
        raw = bytes(image.raw_data)
        rgb = bytearray(w * h * 3)
        for i in range(w * h):
            b = raw[i * 4 + 0]
            g = raw[i * 4 + 1]
            r = raw[i * 4 + 2]
            rgb[i * 3 + 0] = r
            rgb[i * 3 + 1] = g
            rgb[i * 3 + 2] = b
        seq_holder["seq"] += 1
        write_frame(
            rgb_path,
            bytes(rgb),
            w,
            h,
            seq_holder["seq"],
            time.time_ns(),
        )

    camera.listen(on_image)
    _log(f"camera listening → {rgb_path}")

    try:
        while not STOP:
            cmd, last_cmd["seq"], last_cmd["mtime"] = load_cmd(
                cmd_path, last_cmd["seq"], last_cmd["mtime"]
            )
            if cmd:
                apply_lane_change(vehicle, tm, str(cmd.get("lane_change", "none")))
                sp = cmd.get("speed_mps")
                if sp is not None:
                    try:
                        # percentage relative to limit; coarse demo knob
                        tm.vehicle_percentage_speed_difference(
                            vehicle, max(-50.0, min(50.0, 30.0 - float(sp) * 2.0))
                        )
                    except Exception as e:  # noqa: BLE001
                        _log(f"speed cmd ignored: {e}")
            time.sleep(0.05)
    finally:
        _log("teardown sensors/vehicle")
        try:
            camera.stop()
        except Exception:  # noqa: BLE001
            pass
        for actor in (camera, vehicle):
            try:
                if actor is not None:
                    actor.destroy()
            except Exception:  # noqa: BLE001
                pass
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="afc_no_uss CARLA RGB tip + cmd bridge")
    p.add_argument("--dry-run", action="store_true", help="synth frames, no CARLA")
    args = p.parse_args(argv)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    host = _env("CARLA_HOST", "127.0.0.1")
    port = int(_env("CARLA_PORT", "2000"))
    timeout_s = float(_env("GF_CARLA_CONNECT_TIMEOUT_S", "3"))
    rgb_path = Path(_env("GF_CARLA_FRAME_PATH", "/tmp/gf_front.rgb"))
    cmd_path = Path(_env("GF_CARLA_CMD_PATH", "/tmp/gf_carla_cmd.json"))
    w = int(_env("GF_CARLA_CAM_W", "640"))
    h = int(_env("GF_CARLA_CAM_H", "480"))
    on_fail = _env("GF_CARLA_BRIDGE_ON_FAIL", "exit").lower()
    dry = args.dry_run or _env("GF_CARLA_BRIDGE_DRY_RUN", "0") == "1"
    period_s = float(_env("GF_CARLA_DRY_PERIOD_S", "0.05"))

    _log(
        f"frame={rgb_path} cmd={cmd_path} host={host}:{port} "
        f"dry={int(dry)} on_fail={on_fail}"
    )

    if dry:
        return run_dry(rgb_path, cmd_path, w, h, period_s)
    return run_carla(host, port, timeout_s, rgb_path, cmd_path, w, h, on_fail)


if __name__ == "__main__":
    sys.exit(main())
