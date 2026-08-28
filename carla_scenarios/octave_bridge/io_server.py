"""TCP peer for giraffe_client (same role as board gf_carla_io; no GfChannel)."""

from __future__ import annotations

import select
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import protocol as P

OnTick = Callable[["BridgeState"], Optional[bytes]]


@dataclass
class BridgeState:
    """Latest wire blobs from giraffe_client."""

    state_blob: Optional[bytes] = None
    fake_perc_blob: Optional[bytes] = None
    state: Optional[dict] = None
    fake_perc: Optional[dict] = None
    cameras: dict[str, tuple[int, int, bytes]] = field(default_factory=dict)
    last_rx_ns: int = 0
    seq_in: int = 0


class CosimIoServer:
    """Listen GF_COSIM_PORT; plan once per FAKE_PERC (state is cache only)."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = P.GF_COSIM_DEFAULT_PORT,
        *,
        on_tick: Optional[OnTick] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.on_tick = on_tick
        self.state = BridgeState()
        self._stop = threading.Event()
        self._cmd_seq = 0
        self._listen: Optional[socket.socket] = None

    def stop(self) -> None:
        self._stop.set()
        if self._listen:
            try:
                self._listen.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((self.host, self.port))
        ls.listen(1)
        ls.settimeout(1.0)
        self._listen = ls
        print(f"[octave_bridge] listen {self.host}:{self.port} (gf_carla_io twin)", flush=True)
        while not self._stop.is_set():
            try:
                cli, addr = ls.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            print(f"[octave_bridge] client {addr}", flush=True)
            self._cmd_logged = False
            try:
                self._session(cli)
            except OSError as exc:
                print(f"[octave_bridge] session end: {exc}", flush=True)
            finally:
                try:
                    cli.close()
                except OSError:
                    pass
            print("[octave_bridge] waiting for giraffe_client…", flush=True)

    def _session(self, cli: socket.socket) -> None:
        cli.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        hello = P.pack_frame(P.GF_COSIM_MSG_HELLO, b"", time.time_ns(), 0)
        cli.sendall(hello)
        while not self._stop.is_set():
            r, _, _ = select.select([cli], [], [], 0.05)
            if not r:
                continue
            hdr_b = _recv_exact(cli, 28)
            if hdr_b is None:
                return
            magic, ver, mtype, plen, ts, seq = P.unpack_frame_hdr(hdr_b)
            if magic != P.GF_COSIM_MAGIC or ver != P.GF_COSIM_VERSION:
                print("[octave_bridge] bad magic/version — drop", flush=True)
                return
            if plen > 16 * 1024 * 1024:
                print("[octave_bridge] payload too large", flush=True)
                return
            payload = b""
            if plen:
                got = _recv_exact(cli, plen)
                if got is None:
                    return
                payload = got
            self._handle(cli, mtype, payload, ts, seq)

    def _handle(
        self, cli: socket.socket, mtype: int, payload: bytes, ts: int, seq: int
    ) -> None:
        st = self.state
        st.seq_in = int(seq)
        st.last_rx_ns = int(ts) or time.time_ns()
        if mtype in (P.GF_COSIM_MSG_HELLO, P.GF_COSIM_MSG_HEARTBEAT):
            return
        if mtype == P.GF_COSIM_MSG_VEHICLE_STATE:
            st.state_blob = payload
            st.state = P.unpack_vehicle_state(payload)
        elif mtype == P.GF_COSIM_MSG_FAKE_PERC:
            st.fake_perc_blob = payload
            st.fake_perc = P.unpack_fake_perc(payload)
        elif mtype == P.GF_COSIM_MSG_CAMERA_NV12:
            if len(payload) >= P.CAM_HDR.size:
                w, h, _fmt, _res, sid_b = P.CAM_HDR.unpack_from(payload)
                sid = sid_b.split(b"\0", 1)[0].decode("ascii", "ignore") or "front"
                st.cameras[sid] = (int(w), int(h), payload[P.CAM_HDR.size :])
            return
        else:
            return

        if self.on_tick is None:
            return
        # P clock: one plan per fake_perc. VEHICLE_STATE only refreshes cache.
        if mtype != P.GF_COSIM_MSG_FAKE_PERC:
            return
        cmd = self.on_tick(st)
        if not cmd:
            return
        self._cmd_seq += 1
        frame = P.pack_frame(
            P.GF_COSIM_MSG_VEHICLE_CMD, cmd, st.last_rx_ns, self._cmd_seq
        )
        cli.sendall(frame)
        if not getattr(self, "_cmd_logged", False):
            self._cmd_logged = True
            from .protocol import CMD

            fields = CMD.unpack(cmd)
            print(
                f"[octave_bridge] first vehicle_cmd → giraffe "
                f"thr={fields[5]:.2f} brk={fields[6]:.2f} st={fields[7]:.2f} "
                f"mode={int(fields[10])}",
                flush=True,
            )


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)
