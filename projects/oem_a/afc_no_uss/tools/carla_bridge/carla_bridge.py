#!/usr/bin/env python3
"""CARLA camera bridge for afc_no_uss.

Writes configurable YUV camera protocol for perception.fcm and executes
throttle/brake/steer (+ lane_change) from vehicle_can_gateway.

Stream negotiate once (format/w/h); per-frame meta is timestamp_ns/seq only.
Does not decide lane changes.

HIL default: keep reconnecting to remote UE (scenario switches / RPC timeouts
must not kill camera→FCM). GF_CARLA_BRIDGE_ON_FAIL=exit|idle|reconnect.
"""

from __future__ import annotations

def _ipc_default(name: str) -> str:
    """SIL file-IPC under project/runtime_ipc (not /tmp)."""
    import os
    from pathlib import Path
    proj = (os.environ.get("GF_PROJECT_DIR") or "").strip()
    if proj:
        return str(Path(proj) / "runtime_ipc" / name)
    rt = (os.environ.get("GF_RUNTIME_DIR") or "").strip()
    if rt:
        return str(Path(rt) / "var" / name)
    return str(Path("runtime_ipc") / name)


import argparse
import json
import math
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Allow `python carla_bridge.py` without package install.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from camera_mount import load_camera_mount  # noqa: E402
from yuv_codec import plane_size, rgb_to_yuv, synth_rgb  # noqa: E402

STOP = False


def _env(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    return v if v else default


def _log(msg: str, *, error: bool = False) -> None:
    prefix = "[ERROR] carla_bridge" if error else "[carla_bridge]"
    print(f"{prefix}: {msg}", file=sys.stderr if error else sys.stdout, flush=True)


def _on_signal(signum: int, _frame: Any) -> None:
    global STOP
    STOP = True
    _log(f"signal {signum} → stop")


def stream_path(frame_path: Path) -> Path:
    return frame_path.with_name(frame_path.stem + ".stream.json")


def meta_path(frame_path: Path) -> Path:
    return frame_path.with_name(frame_path.stem + ".meta.json")


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


def write_stream_negotiate(frame_path: Path, fmt: str, w: int, h: int) -> None:
    meta = {"format": fmt, "w": w, "h": h}
    atomic_write_text(stream_path(frame_path), json.dumps(meta, separators=(",", ":")))


def write_frame(
    frame_path: Path,
    plane: bytes,
    seq: int,
    timestamp_ns: int,
    *,
    record_dir: Optional[Path] = None,
) -> None:
    # GfChannel live path (frame_ingest Create; we Open+Publish).
    camera_slot = os.environ.get("GF_CAMERA_SLOT", "").strip()
    transport = (os.environ.get("GF_CHANNEL_TRANSPORT") or "shm").strip().lower()
    if camera_slot and transport == "shm":
        try:
            pub = _camera_publisher()
            if callable(pub):
                pub(plane, timestamp_ns, seq)
        except Exception as exc:  # noqa: BLE001
            _log(f"camera publish error: {exc}", error=True)
    # File camera / tee only when transport=file or GF_CAMERA_FILE_TEE=1 (Foxglove uses GfChannel).
    tee = transport == "file" or os.environ.get("GF_CAMERA_FILE_TEE", "0") == "1"
    if tee or not camera_slot or transport != "shm":
        atomic_write_bytes(frame_path, plane)
        meta = {"timestamp_ns": timestamp_ns, "seq": seq}
        atomic_write_text(meta_path(frame_path), json.dumps(meta, separators=(",", ":")))
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(record_dir / f"{seq:08d}.bin", plane)
        with (record_dir / "frames.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"seq": seq, "timestamp_ns": timestamp_ns, "file": f"{seq:08d}.bin"},
                    separators=(",", ":"),
                )
                + "\n"
            )


_CAMERA_PUB = None


def _camera_publisher():
    """Lazy Open GfChannel for GF_CAMERA_SLOT; returns publish(plane, ts, seq)."""
    global _CAMERA_PUB
    if _CAMERA_PUB is not None:
        return _CAMERA_PUB
    slot = os.environ.get("GF_CAMERA_SLOT", "").strip()
    if not slot:
        return None
    try:
        fi = Path(__file__).resolve().parents[2] / "apps" / "frame_ingest"
        if str(fi) not in sys.path:
            sys.path.insert(0, str(fi))
        from gf_channel_py import GfChannel  # noqa: WPS433

        ch = GfChannel.open(slot)
        def _pub(plane: bytes, timestamp_ns: int, seq: int) -> None:
            ch.publish(plane, int(timestamp_ns), int(seq))

        _CAMERA_PUB = _pub
        _log(f"camera channel open {slot}")
        return _CAMERA_PUB
    except Exception as exc:  # noqa: BLE001
        _log(f"camera channel unavailable ({exc}); file camera only")
        _CAMERA_PUB = False  # type: ignore[assignment]
        return None


def write_ego(
    ego_path: Path,
    *,
    speed_mps: float,
    yaw_rate_degps: float,
    steer_angle_deg: float,
    gear: int,
    seq: int,
    timestamp_ns: int,
) -> None:
    payload = {
        "timestamp_ns": timestamp_ns,
        "seq": seq,
        "speed_mps": float(speed_mps),
        "yaw_rate_degps": float(yaw_rate_degps),
        "steer_angle_deg": float(steer_angle_deg),
        "gear": int(gear),
    }
    atomic_write_text(ego_path, json.dumps(payload, separators=(",", ":")) + "\n")


def write_truth(
    truth_path: Path,
    *,
    lead_distance_m: float,
    lead_rel_speed_mps: float,
    scenario: str,
    seq: int,
    timestamp_ns: int,
) -> None:
    payload = {
        "timestamp_ns": timestamp_ns,
        "seq": seq,
        "scenario": scenario,
        "lead_distance_m": float(lead_distance_m),
        "lead_rel_speed_mps": float(lead_rel_speed_mps),
        "dyn_obj_count": 1 if lead_distance_m < 120.0 else 0,
    }
    atomic_write_text(truth_path, json.dumps(payload, separators=(",", ":")) + "\n")


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


def apply_lane_change(vehicle: Any, tm: Any, lane: str) -> None:
    lane = (lane or "none").lower()
    if lane == "none" or vehicle is None or tm is None:
        return
    if lane == "left":
        tm.force_lane_change(vehicle, True)
        _log("force_lane_change left")
    elif lane == "right":
        tm.force_lane_change(vehicle, False)
        _log("force_lane_change right")


def apply_vehicle_control(vehicle: Any, cmd: dict[str, Any]) -> None:
    """Apply throttle/brake/steer when present (CARLA VehicleControl)."""
    if vehicle is None:
        return
    try:
        import carla  # type: ignore
    except ImportError:
        return
    has_any = any(k in cmd for k in ("throttle", "brake", "steer"))
    if not has_any:
        return
    ctrl = vehicle.get_control()
    if "throttle" in cmd:
        ctrl.throttle = max(0.0, min(1.0, float(cmd["throttle"])))
    if "brake" in cmd:
        ctrl.brake = max(0.0, min(1.0, float(cmd["brake"])))
    if "steer" in cmd:
        ctrl.steer = max(-1.0, min(1.0, float(cmd["steer"])))
    vehicle.apply_control(ctrl)


def scenario_lead(scenario: str, t0: float, seq: int) -> tuple[float, float]:
    """Synthetic lead target for dry-run / no-NPC fallback."""
    elapsed = max(0.0, time.time() - t0)
    if scenario == "aeb":
        # Closing target: 50m → 5m over ~8s
        dist = max(4.0, 50.0 - elapsed * 5.5)
        return dist, -5.0
    if scenario == "acc":
        # Soft follow: oscillate around 30m
        dist = 28.0 + 6.0 * math.sin(elapsed * 0.35)
        return dist, -0.5 + 0.3 * math.sin(seq * 0.05)
    return 80.0 + (seq % 20), 0.0


def run_dry(
    frame_path: Path,
    cmd_path: Path,
    ego_path: Path,
    truth_path: Path,
    fmt: str,
    w: int,
    h: int,
    period_s: float,
    scenario: str,
    record_dir: Optional[Path],
) -> int:
    _log(f"dry-run: synth {fmt} → {frame_path} (no CARLA)")
    write_stream_negotiate(frame_path, fmt, w, h)
    if record_dir is not None:
        atomic_write_text(
            record_dir / "stream.json",
            json.dumps({"format": fmt, "w": w, "h": h}, separators=(",", ":")),
        )
    seq = 0
    last_cmd_seq = -1
    last_cmd_mtime = -1.0
    t0 = time.time()
    speed = 12.0
    while not STOP:
        seq += 1
        ts = time.time_ns()
        rgb = synth_rgb(w, h, seq)
        plane = rgb_to_yuv(fmt, rgb, w, h)
        write_frame(frame_path, plane, seq, ts, record_dir=record_dir)

        # Dry-run longitudinal response from last cmd (log only + ego write).
        cmd, last_cmd_seq, last_cmd_mtime = load_cmd(
            cmd_path, last_cmd_seq, last_cmd_mtime
        )
        if cmd:
            thr = float(cmd.get("throttle", 0.0) or 0.0)
            brk = float(cmd.get("brake", 0.0) or 0.0)
            speed = max(0.0, speed + thr * 0.8 - brk * 2.5)
            _log(
                f"dry-run cmd seq={cmd.get('seq')} lane={cmd.get('lane_change')} "
                f"thr={thr:.2f} brk={brk:.2f} steer={cmd.get('steer', 0)} "
                f"speed≈{speed:.1f}"
            )
        else:
            speed = max(0.0, speed - 0.01)

        write_ego(
            ego_path,
            speed_mps=speed,
            yaw_rate_degps=0.05 * math.sin(seq * 0.02),
            steer_angle_deg=float((cmd or {}).get("steer", 0.0) or 0.0) * 25.0,
            gear=4,
            seq=seq,
            timestamp_ns=ts,
        )
        dist, rel = scenario_lead(scenario, t0, seq)
        write_truth(
            truth_path,
            lead_distance_m=dist,
            lead_rel_speed_mps=rel,
            scenario=scenario,
            seq=seq,
            timestamp_ns=ts,
        )
        time.sleep(period_s)
    return 0


def _actor_alive(actor: Any) -> bool:
    if actor is None:
        return False
    try:
        return bool(actor.is_alive)
    except Exception:  # noqa: BLE001
        return False


def _find_role(world: Any, role: str) -> Any:
    heroes = _find_roles(world, role)
    if not heroes:
        return None
    # Prefer highest actor id (= newest spawn) when leftovers share the role.
    try:
        return max(heroes, key=lambda v: int(v.id))
    except Exception:  # noqa: BLE001
        return heroes[0]


def _find_roles(world: Any, role: str) -> list[Any]:
    out: list[Any] = []
    try:
        vehicles = world.get_actors().filter("vehicle.*")
    except Exception:  # noqa: BLE001
        return out
    for v in vehicles:
        try:
            if v.attributes.get("role_name") == role:
                out.append(v)
        except Exception:  # noqa: BLE001
            continue
    return out


def _connect_world(
    carla_mod: Any,
    host: str,
    port: int,
    timeout_s: float,
    *,
    wait_s: float,
    forever: bool,
) -> tuple[Any, Any]:
    """Connect to UE. Raises RuntimeError on API mismatch or give-up (forever=False)."""
    deadline = time.monotonic() + max(0.0, wait_s)
    last_err: Optional[BaseException] = None
    attempt = 0
    while not STOP:
        attempt += 1
        client = carla_mod.Client(host, port)
        client.set_timeout(timeout_s)
        try:
            cv = str(client.get_client_version())
            sv = str(client.get_server_version())
            print("===", flush=True)
            print(f"carla API  client={cv}  server={sv}", flush=True)
            print("===", flush=True)
            if cv.strip() != sv.strip():
                raise RuntimeError(f"CARLA API mismatch client={cv} server={sv}")
            world = client.get_world()
            _log(f"connected {host}:{port} map={world.get_map().name} attempt={attempt}")
            return client, world
        except RuntimeError as e:
            if "API mismatch" in str(e):
                raise
            last_err = e
        except Exception as e:  # noqa: BLE001
            last_err = e
        if not forever and time.monotonic() >= deadline:
            break
        _log(f"waiting for CARLA {host}:{port} ({last_err})")
        time.sleep(min(2.0, max(0.5, float(_env("GF_CARLA_RECONNECT_S", "2")))))
    raise RuntimeError(f"connect {host}:{port} failed: {last_err}")


def _stats_path() -> Path:
    return Path(_env("GF_CARLA_BRIDGE_STATS_PATH", _ipc_default("carla_bridge_stats.json")))


def _write_bridge_stats(
    *,
    carla_fps: float,
    cam_fps: float,
    hero_id: int,
    seq: int,
    waiting_hero: bool = False,
    t_convert_ms: float = 0.0,
    t_write_ms: float = 0.0,
) -> None:
    payload = {
        "carla_fps": round(float(carla_fps), 2),
        "cam_fps": round(float(cam_fps), 2),
        "hero_id": int(hero_id),
        "seq": int(seq),
        "waiting_hero": bool(waiting_hero),
        "t_convert_ms": round(float(t_convert_ms), 2),
        "t_write_ms": round(float(t_write_ms), 2),
        "timestamp_ns": time.time_ns(),
    }
    try:
        atomic_write_text(_stats_path(), json.dumps(payload, separators=(",", ":")))
    except Exception:  # noqa: BLE001
        pass


def _run_carla_session(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    frame_path: Path,
    cmd_path: Path,
    ego_path: Path,
    truth_path: Path,
    fmt: str,
    w: int,
    h: int,
    scenario: str,
    record_dir: Optional[Path],
) -> str:
    """One camera session. Scheme-1: never spawn hero/lead — scenario owns world.

    Returns: stop | ego_lost | rpc_error | waiting_hero
    """
    del truth_path, scenario  # truth owned by scenarios; keep signature stable
    write_stream_negotiate(frame_path, fmt, w, h)
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            record_dir / "stream.json",
            json.dumps({"format": fmt, "w": w, "h": h}, separators=(",", ":")),
        )

    # Product path: wait for scenario hero. Do not spawn ego/lead (overlap removed).
    _log("waiting for scenario hero (role_name=hero); bridge will not spawn vehicles")
    vehicle: Any = None
    wait_hero_s = float(_env("GF_CARLA_WAIT_HERO_S", "120"))
    hero_deadline = time.monotonic() + max(1.0, wait_hero_s)
    last_wait_log = 0.0
    while not STOP and time.monotonic() < hero_deadline:
        vehicle = _find_role(world, "hero")
        if _actor_alive(vehicle):
            break
        now = time.monotonic()
        if now - last_wait_log >= 5.0:
            _write_bridge_stats(
                carla_fps=0.0, cam_fps=0.0, hero_id=-1, seq=0, waiting_hero=True
            )
            _log("still waiting for scenario hero…")
            last_wait_log = now
        time.sleep(0.5)
    if STOP:
        return "stop"
    if not _actor_alive(vehicle):
        _log(f"no scenario hero after {wait_hero_s:.0f}s → retry session")
        return "waiting_hero"

    _log(f"attached driving camera to scenario hero id={vehicle.id}")
    try:
        vehicle.set_autopilot(False)
    except Exception:  # noqa: BLE001
        pass
    tm = client.get_trafficmanager()
    try:
        tm.ignore_lights_percentage(vehicle, 100)
    except Exception:  # noqa: BLE001
        pass

    mount = load_camera_mount()
    cam_bp = world.get_blueprint_library().find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", str(w))
    cam_bp.set_attribute("image_size_y", str(h))
    cam_bp.set_attribute("fov", str(float(mount.fov)))
    cam_transform = mount.as_carla_transform(carla_mod)
    camera = world.spawn_actor(cam_bp, cam_transform, attach_to=vehicle)
    _log(f"camera_mount {mount.describe()} → perception (pygame view does not move this)")

    seq_holder = {"seq": 0}
    last_cmd = {"seq": -1, "mtime": -1.0}
    need = plane_size(fmt, w, h)
    ego_ref: dict[str, Any] = {"v": vehicle}
    # FPS: CARLA camera callbacks vs successful camera writes (windowed).
    fps_win = {"t0": time.monotonic(), "carla_n": 0, "cam_n": 0}
    fps_pub = {"carla": 0.0, "cam": 0.0, "last_log": 0.0, "t_convert_ms": 0.0, "t_write_ms": 0.0}

    def _bump_fps(*, carla: bool = False, cam_ok: bool = False) -> None:
        if carla:
            fps_win["carla_n"] += 1
        if cam_ok:
            fps_win["cam_n"] += 1
        now = time.monotonic()
        dt = now - float(fps_win["t0"])
        if dt < 1.0:
            return
        fps_pub["carla"] = float(fps_win["carla_n"]) / dt
        fps_pub["cam"] = float(fps_win["cam_n"]) / dt
        fps_win["t0"] = now
        fps_win["carla_n"] = 0
        fps_win["cam_n"] = 0
        _write_bridge_stats(
            carla_fps=float(fps_pub["carla"]),
            cam_fps=float(fps_pub["cam"]),
            hero_id=int(getattr(ego_ref["v"], "id", -1)),
            seq=int(seq_holder["seq"]),
            t_convert_ms=float(fps_pub.get("t_convert_ms", 0.0)),
            t_write_ms=float(fps_pub.get("t_write_ms", 0.0)),
        )
        if now - float(fps_pub["last_log"]) >= 2.0:
            _log(
                f"fps carla={fps_pub['carla']:.1f} cam_write={fps_pub['cam']:.1f} "
                f"convert_ms={fps_pub.get('t_convert_ms', 0):.1f} "
                f"write_ms={fps_pub.get('t_write_ms', 0):.1f} "
                f"hero={getattr(ego_ref['v'], 'id', '?')} seq={seq_holder['seq']}"
            )
            fps_pub["last_log"] = now

    def on_image(image: Any) -> None:
        if STOP:
            return
        veh = ego_ref["v"]
        if not _actor_alive(veh):
            return
        _bump_fps(carla=True)
        try:
            raw = bytes(image.raw_data)
            # BGRA → RGB (fast path: memoryview slices)
            mv = memoryview(raw)
            rgb = bytearray(w * h * 3)
            di = 0
            for i in range(0, w * h * 4, 4):
                rgb[di] = mv[i + 2]
                rgb[di + 1] = mv[i + 1]
                rgb[di + 2] = mv[i]
                di += 3
            t0 = time.perf_counter()
            seq_holder["seq"] += 1
            seq = seq_holder["seq"]
            ts = time.time_ns()
            plane = rgb_to_yuv(fmt, bytes(rgb), w, h)
            t_convert_ms = (time.perf_counter() - t0) * 1000.0
            if len(plane) < need:
                return
            t1 = time.perf_counter()
            write_frame(frame_path, plane, seq, ts, record_dir=record_dir)
            t_write_ms = (time.perf_counter() - t1) * 1000.0
            fps_pub["t_convert_ms"] = (
                0.8 * float(fps_pub.get("t_convert_ms", t_convert_ms)) + 0.2 * t_convert_ms
            )
            fps_pub["t_write_ms"] = (
                0.8 * float(fps_pub.get("t_write_ms", t_write_ms)) + 0.2 * t_write_ms
            )
            _bump_fps(cam_ok=True)

            vel = veh.get_velocity()
            speed = math.sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z)
            ang = veh.get_angular_velocity()
            ctrl = veh.get_control()
            write_ego(
                ego_path,
                speed_mps=speed,
                yaw_rate_degps=float(ang.z),
                steer_angle_deg=float(ctrl.steer) * 25.0,
                gear=4,
                seq=seq,
                timestamp_ns=ts,
            )
        except Exception as exc:  # noqa: BLE001
            _log(f"on_image error (will re-session): {exc}", error=True)

    camera.listen(on_image)
    _log(f"camera listening → {frame_path} fmt={fmt} (Giraffe cmd only after IC handoff)")

    reason = "stop"
    try:
        while not STOP:
            if not _actor_alive(vehicle) or not _actor_alive(camera):
                reason = "ego_lost"
                _log("ego/camera gone (scenario switch?) → re-session")
                break
            # New case often spawns a new hero while the old wreck is still "alive".
            # Follow newest role_name=hero — same world as pygame — or Foxglove stays on case-1.
            try:
                heroes = _find_roles(world, "hero")
            except Exception:  # noqa: BLE001
                heroes = []
            if not heroes:
                reason = "ego_lost"
                _log("no role_name=hero in world → re-session")
                break
            try:
                old_id = int(vehicle.id)
                newest = max(heroes, key=lambda v: int(v.id))
                cur_id = int(newest.id)
            except Exception:  # noqa: BLE001
                cur_id, old_id = -1, -2
            if cur_id != old_id:
                reason = "hero_changed"
                _log(
                    f"hero id {old_id} → {cur_id} "
                    f"(heroes={len(heroes)}; new case?) → re-session"
                )
                break
            try:
                cmd, last_cmd["seq"], last_cmd["mtime"] = load_cmd(
                    cmd_path, last_cmd["seq"], last_cmd["mtime"]
                )
                if cmd:
                    apply_lane_change(
                        vehicle, tm, str(cmd.get("lane_change", "none"))
                    )
                    if any(k in cmd for k in ("throttle", "brake", "steer")):
                        vehicle.set_autopilot(False)
                        apply_vehicle_control(vehicle, cmd)
                    else:
                        sp = cmd.get("speed_mps")
                        if sp is not None:
                            try:
                                tm.vehicle_percentage_speed_difference(
                                    vehicle,
                                    max(-50.0, min(50.0, 30.0 - float(sp) * 2.0)),
                                )
                            except Exception as e:  # noqa: BLE001
                                _log(f"speed cmd ignored: {e}")
            except Exception as exc:  # noqa: BLE001
                reason = "rpc_error"
                _log(f"session RPC error: {exc}")
                break
            time.sleep(0.05)
    finally:
        _log("teardown driving camera (hero owned by scenario — not destroyed)")
        try:
            camera.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            if camera is not None and _actor_alive(camera):
                camera.destroy()
        except Exception:  # noqa: BLE001
            pass
    return reason


def run_carla(
    host: str,
    port: int,
    timeout_s: float,
    frame_path: Path,
    cmd_path: Path,
    ego_path: Path,
    truth_path: Path,
    fmt: str,
    w: int,
    h: int,
    on_fail: str,
    scenario: str,
    record_dir: Optional[Path],
) -> int:
    try:
        import carla  # type: ignore
    except ImportError:
        _log(
            f"carla Python module not installed in this interpreter: {sys.executable}. "
            "pip install into THAT env, or set GF_CARLA_PYTHON=/path/to/env/bin/python "
            "(e.g. conda env carla_env). See tools/carla_bridge/README.md",
            error=True,
        )
        if on_fail in ("idle", "reconnect"):
            _log(f"idle without frames (GF_CARLA_BRIDGE_ON_FAIL={on_fail})")
            while not STOP:
                time.sleep(1.0)
            return 0
        return 1

    wait_s = float(_env("GF_CARLA_WAIT_S", "0"))
    reconnect_s = float(_env("GF_CARLA_RECONNECT_S", "2"))
    # Default reconnect: HIL remote UE + scenario switches must not kill camera→FCM.
    mode = (on_fail or "reconnect").strip().lower()
    forever = mode in ("reconnect", "retry", "idle")
    _log(
        f"link mode={mode} wait_s={wait_s} reconnect_s={reconnect_s} "
        f"rpc_timeout_s={timeout_s} (camera stays alive across scenario switches)"
    )

    while not STOP:
        try:
            client, world = _connect_world(
                carla,
                host,
                port,
                timeout_s,
                wait_s=wait_s if wait_s > 0 else 1.0e9,
                forever=forever and mode != "exit",
            )
        except RuntimeError as exc:
            msg = str(exc)
            _log(msg, error=True)
            if "API mismatch" in msg:
                if mode == "idle":
                    while not STOP:
                        time.sleep(1.0)
                    return 0
                return 2
            if mode == "exit":
                return 1
            if mode == "idle":
                _log("idle without frames; SIL may keep running")
                while not STOP:
                    time.sleep(1.0)
                return 0
            _log(f"connect failed; retry in {reconnect_s:.1f}s", error=True)
            time.sleep(max(0.5, reconnect_s))
            continue

        # Optional sync / fixed-delta recording (25fps camera volume timebase).
        if _env("GF_CARLA_SYNC", "0") == "1":
            try:
                fps = float(_env("GF_CHANNEL_RECORD_FPS", "25"))
                settings = world.get_settings()
                settings.synchronous_mode = True
                settings.fixed_delta_seconds = 1.0 / max(1.0, fps)
                world.apply_settings(settings)
                _log(
                    f"CARLA sync on fixed_delta={settings.fixed_delta_seconds:.4f}s "
                    f"(record_fps={fps})"
                )
            except Exception as exc:  # noqa: BLE001
                _log(f"sync mode failed: {exc}", error=True)

        try:
            reason = _run_carla_session(
                carla,
                client,
                world,
                frame_path=frame_path,
                cmd_path=cmd_path,
                ego_path=ego_path,
                truth_path=truth_path,
                fmt=fmt,
                w=w,
                h=h,
                scenario=scenario,
                record_dir=record_dir,
            )
        except Exception as exc:  # noqa: BLE001
            reason = "rpc_error"
            _log(f"session crashed: {exc}", error=True)

        if STOP or reason == "stop":
            break
        if mode == "exit":
            return 1
        _log(f"session end reason={reason}; re-session in {reconnect_s:.1f}s")
        time.sleep(max(0.5, reconnect_s))

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="afc_no_uss CARLA YUV camera + cmd bridge")
    p.add_argument("--dry-run", action="store_true", help="synth frames, no CARLA")
    args = p.parse_args(argv)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    host = _env("CARLA_HOST", "127.0.0.1")
    port = int(_env("CARLA_PORT", "2000"))
    timeout_s = float(_env("GF_CARLA_CONNECT_TIMEOUT_S", "3"))
    frame_path = Path(_env("GF_CARLA_FRAME_PATH", _ipc_default("front.yuv")))
    cmd_path = Path(_env("GF_CARLA_CMD_PATH", _ipc_default("carla_cmd.json")))
    ego_path = Path(_env("GF_CARLA_EGO_PATH", _ipc_default("carla_ego.json")))
    truth_path = Path(_env("GF_CARLA_TRUTH_PATH", _ipc_default("carla_truth.json")))
    fmt = _env("GF_PIXEL_FORMAT", "nv12").lower()
    w = int(_env("GF_CARLA_CAM_W", "640"))
    h = int(_env("GF_CARLA_CAM_H", "480"))
    on_fail = _env("GF_CARLA_BRIDGE_ON_FAIL", "reconnect").lower()
    dry = args.dry_run or _env("GF_CARLA_BRIDGE_DRY_RUN", "0") == "1"
    period_s = float(_env("GF_CARLA_DRY_PERIOD_S", "0.05"))
    # Optional debug only — product ACC/AEB live in repo carla_scenarios/*.py
    scenario = _env("GF_CARLA_SCENARIO", "none").lower()
    rec = _env("GF_RECORD_FRAMES_DIR", "")
    record_dir = Path(rec) if rec else None

    _log(
        f"frame={frame_path} fmt={fmt} cmd={cmd_path} ego={ego_path} "
        f"host={host}:{port} dry={int(dry)} "
        f"debug_scenario={scenario} on_fail={on_fail}"
    )

    if dry:
        return run_dry(
            frame_path,
            cmd_path,
            ego_path,
            truth_path,
            fmt,
            w,
            h,
            period_s,
            scenario,
            record_dir,
        )
    return run_carla(
        host,
        port,
        timeout_s,
        frame_path,
        cmd_path,
        ego_path,
        truth_path,
        fmt,
        w,
        h,
        on_fail,
        scenario,
        record_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
