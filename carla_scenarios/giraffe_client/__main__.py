"""giraffe_client — host CARLA Client B (not a Giraffe module).

Connects to UE (truth + camera + apply_control) and to board gf_carla_io over TCP cosim.
Launched with scenario_client so users do not start two clients by hand.

Env (user-facing via carla.env):
  CARLA_HOST / CARLA_PORT
  GF_COSIM_HOST / GF_COSIM_PORT  (board or localhost gf_carla_io)
  GF_CARLA_CAM_W / GF_CARLA_CAM_H
"""

from __future__ import annotations

import argparse
import math
import os
import signal
import socket
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from _ctrl_tip import TipSender  # noqa: E402
from _fake_perc_pack import pack_fake_perc_pod  # noqa: E402
from _lane_truth import measure_lane_topology  # noqa: E402
from _objects_truth import collect_dyn_objects  # noqa: E402
from _perf import PerfAgg, dump_ue_settings, perf_enabled  # noqa: E402

# POD magic / version — keep in sync with boundary_pods.h / cosim_protocol.h
GF_CH_VEHICLE_STATE_MAGIC = 0x47565354
GF_CH_VEHICLE_CMD_MAGIC = 0x4756434D
GF_CH_POD_VERSION = 1
GF_CHANNEL_FMT_NV12 = 0

GF_COSIM_MAGIC = 0x4743494D
GF_COSIM_VERSION = 2
GF_COSIM_MSG_HELLO = 1
GF_COSIM_MSG_HEARTBEAT = 2
GF_COSIM_MSG_VEHICLE_STATE = 10
GF_COSIM_MSG_FAKE_PERC = 11
GF_COSIM_MSG_CAMERA_NV12 = 12
GF_COSIM_MSG_VEHICLE_CMD = 20
GF_COSIM_SLOT_ID_LEN = 32

_FRAME_HDR = struct.Struct("<IHHIQQ")
assert _FRAME_HDR.size == 28

# width, height, format, reserved, slot_id[32]
_CAM_HDR = struct.Struct("<IIHH32s")
assert _CAM_HDR.size == 44

_VS = struct.Struct("<IHHQfffB3x")
assert _VS.size == 32

_CMD = struct.Struct("<IHHQQfffffBB2x")
assert _CMD.size == 48

STOP = False


def _on_sig(signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    print(f"[giraffe_client] signal {signum} -> stop", flush=True)


def _env(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    return v if v is not None and v != "" else default


def _giraffe_cam_on() -> bool:
    """Host default off. Board/surround: GF_GIRAFFE_CAM=1."""
    v = (_env("GF_GIRAFFE_CAM", "0")).strip().lower()
    return v in ("1", "on", "true", "yes")


def _now_ns() -> int:
    return time.time_ns()


def rgb_to_nv12(rgb: bytes, w: int, h: int) -> bytes:
    """Naive RGB8 → NV12 (BT.601)."""
    y_sz = w * h
    out = bytearray(y_sz + y_sz // 2)
    for j in range(h):
        for i in range(w):
            o = (j * w + i) * 3
            r, g, b = rgb[o], rgb[o + 1], rgb[o + 2]
            y = (66 * r + 129 * g + 25 * b + 128) >> 8
            out[j * w + i] = max(0, min(255, y + 16))
    uv = y_sz
    for j in range(0, h, 2):
        for i in range(0, w, 2):
            acc_u = 0
            acc_v = 0
            for dj in (0, 1):
                for di in (0, 1):
                    o = ((j + dj) * w + (i + di)) * 3
                    r, g, b = rgb[o], rgb[o + 1], rgb[o + 2]
                    acc_u += (-38 * r - 74 * g + 112 * b + 128) >> 8
                    acc_v += (112 * r - 94 * g - 18 * b + 128) >> 8
            u = acc_u // 4 + 128
            v = acc_v // 4 + 128
            out[uv] = max(0, min(255, u))
            out[uv + 1] = max(0, min(255, v))
            uv += 2
    return bytes(out)


class CosimSock:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self.seq = 0

    def connect(self, timeout_s: float = 5.0) -> None:
        s = socket.create_connection((self.host, self.port), timeout=timeout_s)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 64 * 1024)
        except OSError:
            pass
        self.sock = s
        print(f"[giraffe_client] cosim connected {self.host}:{self.port}", flush=True)

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _send_frame(self, msg_type: int, payload: bytes, ts: int) -> None:
        assert self.sock is not None
        self.seq += 1
        hdr = _FRAME_HDR.pack(
            GF_COSIM_MAGIC,
            GF_COSIM_VERSION,
            msg_type,
            len(payload),
            ts & 0xFFFFFFFFFFFFFFFF,
            self.seq & 0xFFFFFFFFFFFFFFFF,
        )
        with self._lock:
            self.sock.sendall(hdr + payload)

    def send_state(self, blob: bytes, ts: int) -> None:
        self._send_frame(GF_COSIM_MSG_VEHICLE_STATE, blob, ts)

    def send_fake_perc(self, blob: bytes, ts: int) -> None:
        self._send_frame(GF_COSIM_MSG_FAKE_PERC, blob, ts)

    def send_camera(self, slot_id: str, w: int, h: int, nv12: bytes, ts: int) -> None:
        sid = slot_id.encode("ascii", "ignore")[:GF_COSIM_SLOT_ID_LEN]
        sid = sid + b"\0" * (GF_COSIM_SLOT_ID_LEN - len(sid))
        payload = _CAM_HDR.pack(w, h, GF_CHANNEL_FMT_NV12, 0, sid) + nv12
        self._send_frame(GF_COSIM_MSG_CAMERA_NV12, payload, ts)

    def try_recv_cmd(self) -> Optional[dict[str, float]]:
        """Non-blocking: drain socket; return latest VEHICLE_CMD if any."""
        if not self.sock:
            return None
        last: Optional[dict[str, float]] = None
        self.sock.setblocking(False)
        try:
            while True:
                hdr_b = self._recv_exact(28)
                if hdr_b is None:
                    break
                magic, ver, mtype, plen, ts, seq = _FRAME_HDR.unpack(hdr_b)
                if magic != GF_COSIM_MAGIC or ver != GF_COSIM_VERSION:
                    # Desync risk — drop rest of this attempt
                    break
                payload = b""
                if plen:
                    got = self._recv_exact(plen)
                    if got is None:
                        break
                    payload = got
                if mtype != GF_COSIM_MSG_VEHICLE_CMD or len(payload) < _CMD.size:
                    continue
                fields = _CMD.unpack_from(payload)
                if fields[0] != GF_CH_VEHICLE_CMD_MAGIC:
                    continue
                last = {
                    # _CMD: magic,ver,res,ts,seq, thr,brk,steer,tgt,spd, mode,lane
                    "throttle": float(fields[5]),
                    "brake": float(fields[6]),
                    "steer": float(fields[7]),
                    "target_speed_mps": float(fields[8]),
                    "speed_mps": float(fields[9]),
                    "ctrl_mode": int(fields[10]),
                }
        except BlockingIOError:
            pass
        except OSError:
            pass
        finally:
            try:
                self.sock.setblocking(True)
            except OSError:
                pass
        return last

    def _recv_exact(self, n: int) -> Optional[bytes]:
        assert self.sock is not None
        buf = bytearray()
        while len(buf) < n:
            try:
                chunk = self.sock.recv(n - len(buf))
            except BlockingIOError:
                if not buf:
                    return None
                # wait briefly for rest
                self.sock.setblocking(True)
                self.sock.settimeout(0.5)
                try:
                    while len(buf) < n:
                        chunk = self.sock.recv(n - len(buf))
                        if not chunk:
                            return None
                        buf.extend(chunk)
                finally:
                    self.sock.settimeout(None)
                    self.sock.setblocking(False)
                break
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)


def pack_vehicle_state(*, speed_mps: float, yaw_rate_degps: float, steer_deg: float, gear: int) -> bytes:
    return _VS.pack(
        GF_CH_VEHICLE_STATE_MAGIC,
        GF_CH_POD_VERSION,
        0,
        _now_ns(),
        float(speed_mps),
        float(yaw_rate_degps),
        float(steer_deg),
        int(gear) & 0xFF,
    )


def _find_hero(world: Any, role: str = "hero") -> Any:
    heroes = [a for a in world.get_actors().filter("vehicle.*") if a.attributes.get("role_name") == role]
    if not heroes:
        return None
    return max(heroes, key=lambda v: int(v.id))


def run() -> int:
    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)

    # Load scenario carla.env if present (same as scenario_client).
    env_path = Path(__file__).resolve().parents[1] / "carla.env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v

    host = _env("CARLA_HOST", "127.0.0.1")
    port = int(_env("CARLA_PORT", "2000"))
    cosim_host = _env("GF_COSIM_HOST", "127.0.0.1")
    cosim_port = int(_env("GF_COSIM_PORT", "7600"))
    wait_hero_s = float(_env("GF_CARLA_WAIT_HERO_S", "120"))
    want_cam = _giraffe_cam_on()

    host_cams: list[Any] = []
    if want_cam:
        # Host camera rig (前视+环视) — no GF_PROJECT_DIR.
        _lib = Path(__file__).resolve().parents[1] / "src" / "lib"
        if str(_lib) not in sys.path:
            sys.path.insert(0, str(_lib))
        from _camera_mount import load_host_cameras  # noqa: WPS433

        host_cams = load_host_cameras(enabled_only=True)
        filt = _env("GF_COSIM_CAMERAS", "").strip()
        if filt:
            allow = {x.strip() for x in filt.split(",") if x.strip()}
            host_cams = [c for c in host_cams if c.id in allow]
            if not host_cams:
                print("[giraffe_client] ERROR: GF_COSIM_CAMERAS filter empty set", file=sys.stderr)
                return 2
    else:
        print(
            "[giraffe_client] camera off (GF_GIRAFFE_CAM=0) — no RGB/NV12/send_camera",
            flush=True,
        )

    try:
        import carla  # type: ignore
    except ImportError:
        print(
            "[giraffe_client] ERROR: carla Python API missing. "
            "Install wheel from CARLA_0.9.16/PythonAPI/carla/dist matching this Python.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    print(
        f"[giraffe_client] UE {host}:{port} cosim->{cosim_host}:{cosim_port} "
        f"cam={'on ' + ','.join(c.id for c in host_cams) if want_cam else 'off'}",
        flush=True,
    )

    client = carla.Client(host, port)
    client.set_timeout(float(_env("GF_CARLA_CONNECT_TIMEOUT_S", "10")))
    world = client.get_world()
    dump_ue_settings(world)

    cosim = CosimSock(cosim_host, cosim_port)
    deadline = time.monotonic() + float(_env("GF_COSIM_WAIT_S", "120"))
    while not STOP and time.monotonic() < deadline:
        try:
            cosim.connect(timeout_s=3.0)
            break
        except OSError as exc:
            print(f"[giraffe_client] waiting gf_carla_io ({exc})...", flush=True)
            time.sleep(2.0)
    if cosim.sock is None:
        print("[giraffe_client] ERROR: cannot connect gf_carla_io", file=sys.stderr)
        return 3
    cosim.try_recv_cmd()  # drain HELLO; overlay-latest, do not wait per perc

    print("[giraffe_client] waiting for role_name=hero...", flush=True)
    hero = None
    hero_deadline = time.monotonic() + wait_hero_s
    while not STOP and time.monotonic() < hero_deadline:
        hero = _find_hero(world)
        if hero is not None:
            break
        time.sleep(0.5)
    if hero is None:
        print("[giraffe_client] ERROR: no hero", file=sys.stderr)
        cosim.close()
        return 4

    loop_sleep_s = 0.05
    try:
        loop_sleep_s = max(0.0, float(_env("GF_COSIM_LOOP_S", "0.05")))
    except ValueError:
        loop_sleep_s = 0.05
    cmd_wait_s = 2.0
    try:
        cmd_wait_s = max(0.2, float(_env("GF_COSIM_CMD_WAIT_S", "2")))
    except ValueError:
        cmd_wait_s = 2.0

    print(
        f"[giraffe_client] attached hero id={hero.id} "
        f"cosim overlay-latest (no wait; first-cmd log after {cmd_wait_s:.1f}s)",
        flush=True,
    )

    bp_lib = world.get_blueprint_library() if want_cam else None
    latest_rgb: dict[str, Optional[bytes]] = {c.id: None for c in host_cams}
    latest_cam_t: dict[str, float] = {}
    lock = threading.Lock()
    sensors: dict[str, Any] = {}
    perf = PerfAgg("giraffe")
    last_ue_frame = -1

    def _attach_cameras(vehicle: Any) -> None:
        if not want_cam:
            return
        for old in list(sensors.values()):
            try:
                old.stop()
                old.destroy()
            except Exception:
                pass
        sensors.clear()
        for hc in host_cams:
            bp = bp_lib.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(hc.w))
            bp.set_attribute("image_size_y", str(hc.h))
            bp.set_attribute("fov", str(hc.mount.fov))
            tf = hc.mount.as_carla_transform(carla)
            cam = world.spawn_actor(bp, tf, attach_to=vehicle)
            cid = hc.id
            cw, ch = hc.w, hc.h

            def _on_image(image: Any, _cid: str = cid, _w: int = cw, _h: int = ch) -> None:
                array = bytes(image.raw_data)
                rgb = bytearray(_w * _h * 3)
                for i in range(_w * _h):
                    o = i * 4
                    rgb[i * 3] = array[o + 2]
                    rgb[i * 3 + 1] = array[o + 1]
                    rgb[i * 3 + 2] = array[o + 0]
                with lock:
                    latest_rgb[_cid] = bytes(rgb)
                    latest_cam_t[_cid] = time.perf_counter()
                perf.count("cam_cb")

            cam.listen(_on_image)
            sensors[cid] = cam
            print(f"[giraffe_client] camera {cid} {cw}x{ch} {hc.mount.describe()}", flush=True)

    _attach_cameras(hero)
    if perf_enabled():
        cam_s = (
            ",".join(f"{c.id}:{c.w}x{c.h}" for c in host_cams) if want_cam else "off"
        )
        print(
            f"[perf][giraffe] loop_sleep={loop_sleep_s:.3f}s "
            f"overlay-latest first_cmd_log={cmd_wait_s:.1f}s cams={cam_s}",
            flush=True,
        )

    thr = 0.0
    brk = 0.0
    steer = 0.0
    tip_seq = 0
    perc_seq = 0
    cmd_seen = False
    cmd_miss_logged = False
    first_perc_mono = 0.0
    tip = TipSender()
    lane_log_once = False

    while not STOP:
        t_loop = time.perf_counter()
        cur = _find_hero(world)
        if cur is not None and cur.id != hero.id:
            print(f"[giraffe_client] hero {hero.id} -> {cur.id}", flush=True)
            hero = cur
            _attach_cameras(hero)

        try:
            ctrl = carla.VehicleControl(throttle=thr, brake=brk, steer=steer, hand_brake=False)
            hero.apply_control(ctrl)
        except Exception as exc:
            print(f"[giraffe_client] apply_control failed: {exc}", flush=True)
            time.sleep(0.2)
            continue

        vel = hero.get_velocity()
        speed = math.sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z)
        ang = hero.get_angular_velocity()
        yaw_rate = float(ang.z)
        steer_deg = float(hero.get_control().steer) * 70.0

        ts = _now_ns()
        cam_ts: dict[str, float] = {}
        try:
            t0 = time.perf_counter()
            state_blob = pack_vehicle_state(
                speed_mps=speed,
                yaw_rate_degps=yaw_rate,
                steer_deg=steer_deg,
                gear=4,
            )
            cosim.send_state(state_blob, ts)
            t1 = time.perf_counter()
            lane = measure_lane_topology(hero, world)
            t2 = time.perf_counter()
            dyn = collect_dyn_objects(hero, world)
            t3 = time.perf_counter()
            perc_seq += 1
            perc_blob = pack_fake_perc_pod(lane=lane, dyn=dyn, seq=perc_seq, timestamp_ns=ts)
            cosim.send_fake_perc(perc_blob, ts)
            t4 = time.perf_counter()
            if first_perc_mono <= 0.0:
                first_perc_mono = time.monotonic()
            if not lane_log_once:
                lane_log_once = True
                print(
                    f"[giraffe_client] fake_perc lanes={lane.get('lane_count')} "
                    f"adj={lane.get('adj_n')} avail={lane.get('lane_avail')} "
                    f"dyn={dyn.get('dyn_n')} cipv={dyn.get('cipv_id')} "
                    f"reason={lane.get('lane_quality_reason')}",
                    flush=True,
                )
            tw = time.perf_counter()
            cmd = cosim.try_recv_cmd()
            perf.add("recv_cmd", time.perf_counter() - tw)
            if cmd is None:
                perf.count("cmd_hold")
                if (
                    not cmd_seen
                    and not cmd_miss_logged
                    and first_perc_mono > 0.0
                    and (time.monotonic() - first_perc_mono) >= cmd_wait_s
                ):
                    cmd_miss_logged = True
                    print(
                        f"[giraffe_client] no vehicle_cmd after {cmd_wait_s:.1f}s — "
                        "hold last ctrl (overlay-latest, world clock not blocked)",
                        flush=True,
                    )
            if cmd:
                thr = max(0.0, min(1.0, cmd["throttle"]))
                brk = max(0.0, min(1.0, cmd["brake"]))
                steer = max(-1.0, min(1.0, cmd["steer"]))
                tip_seq += 1
                tip.send(
                    seq=tip_seq,
                    throttle=thr,
                    brake=brk,
                    steer=steer,
                    target_speed_mps=float(cmd.get("target_speed_mps") or 0.0),
                    ctrl_mode=int(cmd.get("ctrl_mode") or 0),
                )
                try:
                    hero.apply_control(
                        carla.VehicleControl(
                            throttle=thr, brake=brk, steer=steer, hand_brake=False
                        )
                    )
                except Exception as exc:
                    print(f"[giraffe_client] apply_control failed: {exc}", flush=True)
                if not cmd_seen:
                    cmd_seen = True
                    print(
                        f"[giraffe_client] first vehicle_cmd thr={thr:.2f} brk={brk:.2f} "
                        f"steer={steer:.2f} (UDP tip)",
                        flush=True,
                    )
            if want_cam:
                with lock:
                    snap = {k: latest_rgb.get(k) for k in latest_rgb}
                    cam_ts = dict(latest_cam_t)
                t_cam0 = time.perf_counter()
                for hc in host_cams:
                    rgb = snap.get(hc.id)
                    if rgb is None:
                        continue
                    nv12 = rgb_to_nv12(rgb, hc.w, hc.h)
                    cosim.send_camera(hc.id, hc.w, hc.h, nv12, ts)
                perf.add("nv12", time.perf_counter() - t_cam0)
            else:
                perf.add("nv12", 0.0)
            perf.add("send_st", t1 - t0)
            perf.add("lane", t2 - t1)
            perf.add("dyn", t3 - t2)
            perf.add("send_perc", t4 - t3)
        except OSError as exc:
            print(f"[giraffe_client] cosim send failed: {exc} - reconnect?", flush=True)
            break

        try:
            snap_w = world.get_snapshot()
            if int(snap_w.frame) != last_ue_frame:
                last_ue_frame = int(snap_w.frame)
                perf.count("ue_frame")
        except Exception:  # noqa: BLE001
            snap_w = None

        work = time.perf_counter() - t_loop
        idle = max(0.0, loop_sleep_s - work)
        perf.add("work", work)
        perf.add("idle", idle)
        cam_age_ms = -1.0
        if cam_ts:
            cam_age_ms = 1000.0 * (time.perf_counter() - min(cam_ts.values()))
        extra = {
            "cam_age_ms": f"{cam_age_ms:.0f}",
            "work_ms": f"{1000.0 * work:.0f}",
            "cam": "on" if want_cam else "off",
            "cmd": "live" if cmd_seen else "hold",
        }
        if snap_w is not None:
            extra["ue_dt_ms"] = f"{1000.0 * float(snap_w.timestamp.delta_seconds):.1f}"
        perf.tick(extra=extra)
        time.sleep(idle)

    for old in list(sensors.values()):
        try:
            old.stop()
            old.destroy()
        except Exception:
            pass
    cosim.close()
    print("[giraffe_client] exit", flush=True)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="giraffe_client - UE truth/camera/cmd <-> gf_carla_io")
    p.parse_args()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
