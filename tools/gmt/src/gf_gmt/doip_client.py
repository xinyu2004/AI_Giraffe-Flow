"""Minimal ISO 13400-2 DoIP TCP client for GMT OTA sheet (SIL)."""

from __future__ import annotations

import socket
import struct
from typing import Optional


DOIP_ROUTING_REQ = 0x0005
DOIP_ROUTING_RESP = 0x0006
DOIP_DIAG = 0x8001
DOIP_DIAG_ACK = 0x8002

ROUTING_OK = 0x10


def _encode(payload_type: int, payload: bytes, version: int = 0x02) -> bytes:
    return struct.pack("!BBHI", version, (~version) & 0xFF, payload_type, len(payload)) + payload


def _try_decode(buf: bytes) -> tuple[Optional[tuple[int, bytes]], int]:
    """Returns ((ptype, payload), consumed) or (None, 0) if need more; (None, n) to drop n."""
    if len(buf) < 8:
        return None, 0
    ver, inv, ptype, plen = struct.unpack("!BBHI", buf[:8])
    if ((~ver) & 0xFF) != inv:
        return None, 1
    if plen > 65536:
        return None, 1
    if len(buf) < 8 + plen:
        return None, 0
    return (ptype, buf[8 : 8 + plen]), 8 + plen


class DoipClient:
    def __init__(self) -> None:
        self._sock: Optional[socket.socket] = None
        self._buf = bytearray()
        self.tester = 0x0E80
        self.entity = 0x0E00

    def connect(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.close()
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(timeout)
        self._sock = s
        self._buf.clear()

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._buf.clear()

    def _send(self, data: bytes) -> None:
        assert self._sock is not None
        self._sock.sendall(data)

    def _recv_payload(self, expect_type: int) -> bytes:
        assert self._sock is not None
        while True:
            decoded, consumed = _try_decode(bytes(self._buf))
            if decoded is not None:
                del self._buf[:consumed]
                ptype, payload = decoded
                if ptype == expect_type:
                    return payload
                continue
            if consumed > 0:
                del self._buf[:consumed]
                continue
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("DoIP connection closed")
            self._buf.extend(chunk)

    def routing_activation(self) -> None:
        payload = struct.pack("!HB", self.tester, 0x00) + b"\x00\x00\x00\x00"
        self._send(_encode(DOIP_ROUTING_REQ, payload))
        resp = self._recv_payload(DOIP_ROUTING_RESP)
        if len(resp) < 5 or resp[4] != ROUTING_OK:
            raise RuntimeError(f"RoutingActivation denied: {resp.hex()}")

    def transceive(self, uds: bytes) -> bytes:
        payload = struct.pack("!HH", self.tester, self.entity) + uds
        self._send(_encode(DOIP_DIAG, payload))
        self._recv_payload(DOIP_DIAG_ACK)
        resp = self._recv_payload(DOIP_DIAG)
        if len(resp) < 4:
            raise RuntimeError("short diagnostic response")
        return resp[4:]

    def tester_present(self) -> bytes:
        return self.transceive(bytes([0x3E, 0x00]))

    def start_ota(self, package_id: str, artifact_path: str) -> bytes:
        spec = f"{package_id}|{artifact_path}".encode("utf-8")
        return self.transceive(bytes([0x31, 0x01, 0xF1, 0x00]) + spec)

    def ota_progress(self) -> int:
        r = self.transceive(bytes([0x31, 0x03, 0xF1, 0x01]))
        if len(r) >= 5 and r[0] == 0x71:
            return int(r[4])
        return -1
