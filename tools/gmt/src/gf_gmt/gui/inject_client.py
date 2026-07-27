"""GMT → inject control client (TCP JSON lines, playhead mode).

Protocol matches apps/tools/iox_obs_inject (GF_INJECT_MODE=playhead).
GMT never launches run_sil — only connects to an already-running inject.
"""

from __future__ import annotations

import json
import select
import socket
import time
from typing import Any

DEFAULT_INJECT_PORT = 8767
PROTO = "gf_inject_ctrl"


class InjectCtrlClient:
    """Non-blocking TCP client for gf_inject_ctrl."""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._buf = ""
        self._connected = False
        self.last_hello: dict[str, Any] | None = None
        self.last_status: dict[str, Any] | None = None
        self.last_published: dict[str, Any] | None = None

    @property
    def connected(self) -> bool:
        return self._connected and self._sock is not None

    def send_cmd(self, obj: dict[str, Any]) -> None:
        if self._sock is None:
            raise ConnectionError("not connected")
        # compact JSON — C++ parser tolerates spaces, but keep wire format stable
        line = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            self._sock.sendall(line.encode("utf-8"))
        except (BlockingIOError, InterruptedError):
            # non-blocking: wait briefly then retry once
            assert self._sock is not None
            select.select([], [self._sock], [], 1.0)
            try:
                self._sock.sendall(line.encode("utf-8"))
            except OSError as exc:
                self.close()
                raise ConnectionError(str(exc)) from exc
        except OSError as exc:
            self.close()
            raise ConnectionError(str(exc)) from exc

    def connect(self, host: str, port: int = DEFAULT_INJECT_PORT, *, timeout: float = 5.0) -> None:
        """Blocking hello handshake. Prefer host=127.0.0.1 on the SIL machine."""
        self.close()
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.settimeout(timeout)
        self._sock = sock
        self._buf = ""
        self._connected = True
        payload = json.dumps({"cmd": "hello"}, separators=(",", ":")) + "\n"
        sock.sendall(payload.encode("utf-8"))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(65536)
            except TimeoutError:
                continue
            if not chunk:
                self.close()
                raise ConnectionError("inject closed during hello")
            self._buf += chunk.decode("utf-8", errors="replace")
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("op") == "hello":
                    if obj.get("proto") and obj.get("proto") != PROTO:
                        continue
                    self.last_hello = obj
                    sock.setblocking(False)
                    return
        self.close()
        raise TimeoutError(
            f"inject ctrl hello timeout @ {host}:{port}\n"
            "请确认：GF_INJECT_MODE=playhead、端口 8767（TCP）、防火墙放行；\n"
            "不要用上方 Live 的 ws://8766。"
        )

    def seek(self, index: int) -> None:
        self.send_cmd({"cmd": "seek", "index": int(index)})

    def step(self) -> None:
        self.send_cmd({"cmd": "step"})

    def play(self, rate: float = 1.0) -> None:
        self.send_cmd({"cmd": "play", "rate": float(rate)})

    def pause(self) -> None:
        self.send_cmd({"cmd": "pause"})

    def request_status(self) -> None:
        self.send_cmd({"cmd": "status"})

    def poll_messages(self) -> list[dict[str, Any]]:
        if self._sock is None:
            return []
        try:
            while True:
                try:
                    r, _, _ = select.select([self._sock], [], [], 0)
                except (ValueError, OSError):
                    self.close()
                    return []
                if not r:
                    break
                try:
                    chunk = self._sock.recv(65536)
                except BlockingIOError:
                    break
                except TimeoutError:
                    break
                except OSError:
                    self.close()
                    return []
                if not chunk:
                    self.close()
                    break
                self._buf += chunk.decode("utf-8", errors="replace")
        except OSError:
            self.close()
            return []

        out: list[dict[str, Any]] = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            op = obj.get("op")
            if op == "hello":
                self.last_hello = obj
            elif op == "status":
                self.last_status = obj
            elif op == "published":
                self.last_published = obj
            out.append(obj)
        return out

    def close(self) -> None:
        self._connected = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._buf = ""
