"""Minimal COVESA/GENIVI DLT protocol v1 TCP client (port 3490).

Parses standard + extended headers and verbose STRING payloads
(enough for gf_ara::log / dlt_log_string). Not a full dlt-viewer.
"""

from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT_DLT_PORT = 3490

# Standard header htyp bits (DLT protocol v1)
_HTYP_UEH = 0x01
_HTYP_MSBF = 0x02
_HTYP_WEID = 0x04
_HTYP_WSID = 0x08
_HTYP_WTMS = 0x10

# Extended header MSIN: MTIN (log level) in bits 4..7 when MSTP=log(0)
_LOG_LEVELS = {
    0x01: "FATAL",
    0x02: "ERROR",
    0x03: "WARN",
    0x04: "INFO",
    0x05: "DEBUG",
    0x06: "VERBOSE",
}

# Verbose type_info (COVESA): DLT_TYPE_INFO_STRG
_TYPE_INFO_STRG = 0x00000200


@dataclass(frozen=True)
class DltMessage:
    ecu: str
    app_id: str
    ctx_id: str
    level: str
    text: str
    raw_len: int

    def display(self) -> str:
        return f"[{self.level}] {self.app_id}/{self.ctx_id} {self.text}"


def _four(b: bytes) -> str:
    return b.decode("ascii", errors="replace").rstrip("\x00")


def parse_dlt_message(msg: bytes) -> DltMessage | None:
    """Parse one DLT v1 message (length already sliced). Returns None if unusable."""
    if len(msg) < 4:
        return None
    htyp = msg[0]
    length = struct.unpack(">H", msg[2:4])[0]
    if length != len(msg) or length < 4:
        return None

    off = 4
    ecu = "----"
    if htyp & _HTYP_WEID:
        if off + 4 > len(msg):
            return None
        ecu = _four(msg[off : off + 4])
        off += 4
    if htyp & _HTYP_WSID:
        off += 4
    if htyp & _HTYP_WTMS:
        off += 4

    app_id = "----"
    ctx_id = "----"
    level = "INFO"
    text = ""

    if htyp & _HTYP_UEH:
        if off + 10 > len(msg):
            return None
        msin = msg[off]
        # noar = msg[off + 1]
        app_id = _four(msg[off + 2 : off + 6])
        ctx_id = _four(msg[off + 6 : off + 10])
        mtin = (msin >> 4) & 0x0F
        level = _LOG_LEVELS.get(mtin, f"L{mtin}")
        off += 10

    payload = msg[off:]
    be = bool(htyp & _HTYP_MSBF)
    text = _extract_verbose_strings(payload, big_endian=be)
    if not text:
        # Fallback: printable ASCII from payload (control / non-verbose)
        text = "".join(chr(b) if 32 <= b < 127 else "" for b in payload).strip()
    if not text:
        return None
    return DltMessage(
        ecu=ecu, app_id=app_id, ctx_id=ctx_id, level=level, text=text, raw_len=length
    )


def _extract_verbose_strings(payload: bytes, *, big_endian: bool) -> str:
    """Walk verbose args; collect STRING / UTF8STRING payloads."""
    if len(payload) < 4:
        return ""
    endian = ">" if big_endian else "<"
    parts: list[str] = []
    off = 0
    # Bound iterations (BL-MEM-BOUND style — no unbounded walk)
    for _ in range(32):
        if off + 4 > len(payload):
            break
        (type_info,) = struct.unpack_from(endian + "I", payload, off)
        off += 4
        if (type_info & _TYPE_INFO_STRG) == 0:
            break
        if off + 2 > len(payload):
            break
        (slen,) = struct.unpack_from(endian + "H", payload, off)
        off += 2
        if slen <= 0 or off + slen > len(payload):
            break
        raw = payload[off : off + slen]
        off += slen
        if raw.endswith(b"\x00"):
            raw = raw[:-1]
        parts.append(raw.decode("utf-8", errors="replace"))
    return " ".join(parts)


def iter_dlt_frames(buf: bytearray) -> list[bytes]:
    """Extract complete frames from a TCP byte buffer; consumes them from buf."""
    out: list[bytes] = []
    while len(buf) >= 4:
        length = struct.unpack(">H", buf[2:4])[0]
        if length < 4 or length > 65535:
            del buf[0]
            continue
        if len(buf) < length:
            break
        out.append(bytes(buf[:length]))
        del buf[:length]
    return out


class DltTcpReader:
    """Background TCP reader → callback with DltMessage."""

    def __init__(
        self,
        on_message: Callable[[DltMessage], None],
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self._on_message = on_message
        self._on_status = on_status or (lambda _s: None)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    @property
    def connected(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, host: str, port: int = DEFAULT_DLT_PORT) -> None:
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(host, port), name="dlt-tcp", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None

    def _run(self, host: str, port: int) -> None:
        try:
            sock = socket.create_connection((host, port), timeout=3.0)
        except OSError as exc:
            self._on_status(f"connect failed: {exc}")
            return
        self._sock = sock
        sock.settimeout(0.4)
        self._on_status(f"connected tcp://{host}:{port}")
        buf = bytearray()
        try:
            while not self._stop.is_set():
                try:
                    chunk = sock.recv(8192)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buf.extend(chunk)
                # Cap buffer (BL-MEM-BOUND)
                if len(buf) > 256 * 1024:
                    del buf[: len(buf) - 128 * 1024]
                for frame in iter_dlt_frames(buf):
                    msg = parse_dlt_message(frame)
                    if msg is not None:
                        self._on_message(msg)
        finally:
            try:
                sock.close()
            except OSError:
                pass
            self._sock = None
            self._on_status("disconnected")
