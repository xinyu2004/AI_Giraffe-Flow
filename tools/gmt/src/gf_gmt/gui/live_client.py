"""WebSocket client for GMT live bridge (NDJSON lines)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import select
import socket
import struct
import time

from gf_gmt.bridge_live import _parse, is_hello


class LiveWsSession:
    """Non-blocking client for gf_gmt_live bridge."""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._raw = b""
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and self._sock is not None

    def connect(self, host: str, port: int, *, timeout: float = 3.0) -> None:
        self.close()
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(req.encode("ascii"))
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise ConnectionError("live bridge closed during handshake")
            resp += chunk
        header_end = resp.index(b"\r\n\r\n") + 4
        headers = resp[:header_end]
        leftover = resp[header_end:]
        if b"101" not in headers.split(b"\r\n", 1)[0]:
            sock.close()
            raise ConnectionError(headers.decode("utf-8", errors="replace")[:200])

        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        expect = base64.b64encode(
            hashlib.sha1((key + guid).encode("ascii")).digest()
        ).decode("ascii")
        if expect.encode() not in headers:
            sock.close()
            raise ConnectionError("invalid Sec-WebSocket-Accept")

        sock.setblocking(False)
        self._sock = sock
        self._raw = leftover
        self._connected = True
        self._wait_for_hello(timeout=timeout)

    def _wait_for_hello(self, *, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._recv_available()
            while True:
                frame = self._next_frame()
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:
                    self.close()
                    raise ConnectionError("live bridge closed")
                if opcode == 0x1 and is_hello(_parse(payload.decode("utf-8", errors="replace"))):
                    return
            time.sleep(0.01)
        raise TimeoutError("live bridge hello timeout")

    def poll_lines(self) -> list[str]:
        """Return newly received NDJSON lines (non-blocking)."""
        if not self.connected or self._sock is None:
            return []
        try:
            self._recv_available()
            return self._decode_lines()
        except (ConnectionResetError, BrokenPipeError, OSError):
            self.close()
            return []

    def _recv_available(self) -> bytes:
        if self._sock is None:
            return b""
        chunks: list[bytes] = []
        while True:
            r, _, _ = select.select([self._sock], [], [], 0)
            if not r:
                break
            chunk = self._sock.recv(65536)
            if not chunk:
                self.close()
                break
            chunks.append(chunk)
        if chunks:
            self._raw += b"".join(chunks)
        return b""

    def _decode_lines(self) -> list[str]:
        out: list[str] = []
        while True:
            frame = self._next_frame()
            if frame is None:
                break
            opcode, payload = frame
            if opcode == 0x8:
                self.close()
                break
            if opcode != 0x1:
                continue
            text = payload.decode("utf-8", errors="replace")
            if is_hello(_parse(text)):
                continue
            out.append(text)
        return out

    def _next_frame(self) -> tuple[int, bytes] | None:
        raw = self._raw
        if len(raw) < 2:
            return None
        b0, b1 = raw[0], raw[1]
        opcode = b0 & 0x0F
        masked = (b1 & 0x80) != 0
        length = b1 & 0x7F
        idx = 2
        if length == 126:
            if len(raw) < idx + 2:
                return None
            length = struct.unpack("!H", raw[idx : idx + 2])[0]
            idx += 2
        elif length == 127:
            if len(raw) < idx + 8:
                return None
            length = struct.unpack("!Q", raw[idx : idx + 8])[0]
            idx += 8
        mask_len = 4 if masked else 0
        total = idx + mask_len + length
        if len(raw) < total:
            return None
        if masked:
            mask = raw[idx : idx + 4]
            payload = raw[idx + 4 : total]
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        else:
            payload = raw[idx:total]
        self._raw = raw[total:]
        return opcode, payload

    def close(self) -> None:
        self._connected = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._raw = b""
