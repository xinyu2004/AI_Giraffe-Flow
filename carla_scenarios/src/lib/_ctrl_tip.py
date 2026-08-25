"""Local UDP tip: giraffe_client → scenario_client (HUD CTRL / verdict only).

Not product IPC. No disk. Ego motion is owned solely by giraffe_client apply_control.
"""

from __future__ import annotations

import os
import socket
import struct
from dataclasses import dataclass, field
from typing import Optional

# magic u32 LE 'GCTL', seq, thr, brk, steer, target_speed_mps, ctrl_mode
_TIP = struct.Struct("<IIffffI")
assert _TIP.size == 28

GF_CTRL_TIP_MAGIC = 0x4C544347  # 'GCTL' little-endian
_CTRL_MODE_NAME = {0: "cruise", 1: "acc", 2: "aeb", 3: "pullaway"}


def tip_port() -> int:
    try:
        return int(os.environ.get("GF_CTRL_TIP_PORT") or "7610")
    except ValueError:
        return 7610


def tip_host() -> str:
    return (os.environ.get("GF_CTRL_TIP_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def pack_tip(
    *,
    seq: int,
    throttle: float,
    brake: float,
    steer: float,
    target_speed_mps: float = 0.0,
    ctrl_mode: int = 0,
) -> bytes:
    return _TIP.pack(
        GF_CTRL_TIP_MAGIC,
        int(seq) & 0xFFFFFFFF,
        float(throttle),
        float(brake),
        float(steer),
        float(target_speed_mps),
        int(ctrl_mode) & 0xFFFFFFFF,
    )


def unpack_tip(data: bytes) -> Optional[dict]:
    if len(data) < _TIP.size:
        return None
    magic, seq, thr, brk, steer, tgt, mode = _TIP.unpack_from(data)
    if magic != GF_CTRL_TIP_MAGIC:
        return None
    return {
        "seq": int(seq),
        "throttle": float(thr),
        "brake": float(brk),
        "steer": float(steer),
        "target_speed_mps": float(tgt),
        "ctrl_mode": int(mode),
        "mode": _CTRL_MODE_NAME.get(int(mode), "cruise"),
    }


class TipSender:
    """giraffe_client: fire-and-forget to localhost."""

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._addr = (tip_host(), tip_port())

    def send(
        self,
        *,
        seq: int,
        throttle: float,
        brake: float,
        steer: float,
        target_speed_mps: float = 0.0,
        ctrl_mode: int = 0,
    ) -> None:
        try:
            self._sock.sendto(
                pack_tip(
                    seq=seq,
                    throttle=throttle,
                    brake=brake,
                    steer=steer,
                    target_speed_mps=target_speed_mps,
                    ctrl_mode=ctrl_mode,
                ),
                self._addr,
            )
        except OSError:
            pass

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


@dataclass
class TipReceiver:
    """scenario_client: non-blocking poll for HUD / seen_control."""

    last_seq: int = -1
    fresh_count: int = 0
    _armed: bool = False
    target_speed_mps: Optional[float] = None
    mode: str = ""
    throttle: float = 0.0
    brake: float = 0.0
    steer: float = 0.0
    _sock: Optional[socket.socket] = field(default=None, repr=False)

    def _ensure(self) -> bool:
        if self._sock is not None:
            return True
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", tip_port()))
            s.setblocking(False)
            self._sock = s
            return True
        except OSError:
            self._sock = None
            return False

    def poll(self) -> bool:
        """Drain socket; return True if a new seq arrived after arm."""
        if not self._ensure() or self._sock is None:
            return False
        got_new = False
        while True:
            try:
                data, _ = self._sock.recvfrom(256)
            except BlockingIOError:
                break
            except OSError:
                break
            tip = unpack_tip(data)
            if tip is None:
                continue
            self.target_speed_mps = tip["target_speed_mps"]
            self.mode = str(tip["mode"] or "")
            self.throttle = tip["throttle"]
            self.brake = tip["brake"]
            self.steer = tip["steer"]
            seq = tip["seq"]
            if not self._armed:
                self.last_seq = seq
                self._armed = True
                continue
            if seq != self.last_seq:
                self.fresh_count += 1
                self.last_seq = seq
                got_new = True
        return got_new

    @property
    def seen_control(self) -> bool:
        return self.fresh_count > 0

    @property
    def seen(self) -> bool:
        return self.seen_control

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


_shared_rx: Optional[TipReceiver] = None


def shared_receiver() -> TipReceiver:
    global _shared_rx
    if _shared_rx is None:
        _shared_rx = TipReceiver()
    return _shared_rx
