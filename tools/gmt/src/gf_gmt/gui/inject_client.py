"""GMT → inject control client (TCP JSON lines, playhead mode).

Protocol matches apps/tools/iox_obs_inject (GF_INJECT_MODE=playhead).
GMT never launches run_sil — only connects to an already-running inject.

Stream mode (hello caps contains ``stream_window``): GMT owns the full session
and pushes A/B windows / single-frame inject cmds; board holds small buffers only.
Legacy mode: board already loaded a file; GMT only sends seek/step/play.
"""

from __future__ import annotations

import json
import select
import socket
import time
from typing import Any

DEFAULT_INJECT_PORT = 8767
PROTO = "gf_inject_ctrl"


def is_injectable_topic(topic: str) -> bool:
    """MVP: only EgoMotion (full path or trailing segment)."""
    t = (topic or "").rstrip("/")
    if t.endswith("EgoMotion"):
        return True
    last = t.split("/")[-1] if t else ""
    return "EgoMotion" in last


def hello_has_stream_window(hello: dict[str, Any] | None) -> bool:
    if not hello:
        return False
    caps = hello.get("caps")
    if isinstance(caps, list):
        return "stream_window" in caps
    return False


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

    def reset(self) -> None:
        self.send_cmd({"cmd": "reset"})

    def session(self, events: int) -> None:
        self.send_cmd({"cmd": "session", "events": int(events)})

    def window_begin(self, slot: str, base: int) -> None:
        self.send_cmd({"cmd": "window_begin", "slot": str(slot), "base": int(base)})

    def push(
        self,
        slot: str,
        index: int,
        t_ns: int,
        topic: str,
        data: dict[str, Any],
    ) -> None:
        self.send_cmd(
            {
                "cmd": "push",
                "slot": str(slot),
                "index": int(index),
                "t_ns": int(t_ns),
                "topic": str(topic),
                "data": data if isinstance(data, dict) else {},
            }
        )

    def window_end(self, slot: str) -> None:
        self.send_cmd({"cmd": "window_end", "slot": str(slot)})

    def inject_event(
        self,
        index: int,
        t_ns: int,
        topic: str,
        data: dict[str, Any],
    ) -> None:
        """Immediate one-shot publish (stream scrub primary path)."""
        self.send_cmd(
            {
                "cmd": "inject",
                "index": int(index),
                "t_ns": int(t_ns),
                "topic": str(topic),
                "data": data if isinstance(data, dict) else {},
            }
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


class InjectStreamHelper:
    """GMT-side: push EgoMotion windows / inject single frames."""

    WINDOW = 64

    def __init__(self, client: InjectCtrlClient) -> None:
        self.client = client
        self.stream_mode = False
        self.window_max_events = self.WINDOW
        self.window_buffers = 2
        # slot → base index of first pushed (window order / model index)
        self._slot_base: dict[str, int] = {}
        self._next_prefetch_from: int = 0

    def on_hello(self, hello: dict[str, Any] | None) -> None:
        self.stream_mode = hello_has_stream_window(hello)
        if not hello:
            return
        wmax = hello.get("window_max_events")
        if isinstance(wmax, int) and wmax > 0:
            self.window_max_events = wmax
        wb = hello.get("window_buffers")
        if isinstance(wb, int) and wb > 0:
            self.window_buffers = wb

    @property
    def window_size(self) -> int:
        return max(1, min(self.WINDOW, self.window_max_events))

    def configure_session(self, n_events: int) -> None:
        self.client.session(int(n_events))
        self.client.reset()
        self._slot_base.clear()
        self._next_prefetch_from = 0

    def inject_model_index(
        self, model: Any, index: int
    ) -> tuple[str, str]:
        """Inject one model row if EgoMotion.

        Returns (\"sent\"|\"skip\", topic).
        """
        events = getattr(model, "events", None) or []
        if index < 0 or index >= len(events):
            return ("skip", "")
        ev = events[index]
        topic = str(getattr(ev, "topic", "") or "")
        if not is_injectable_topic(topic):
            return ("skip", topic)
        data = getattr(ev, "data", None)
        if not isinstance(data, dict):
            data = {}
        self.client.inject_event(
            int(getattr(ev, "index", index)),
            int(getattr(ev, "t_ns", 0) or 0),
            topic,
            data,
        )
        return ("sent", topic)

    def fill_window(
        self,
        model: Any,
        slot: str,
        from_index: int,
        *,
        count: int | None = None,
    ) -> int:
        """Scan forward from ``from_index``; push only injectable frames.

        Returns number of frames pushed. ``base`` on the wire is the first
        *model* index scanned (from_index), not the first EgoMotion index.
        """
        events = getattr(model, "events", None) or []
        n = len(events)
        if from_index < 0 or from_index >= n:
            return 0
        limit = count if count is not None else self.window_size
        limit = max(1, min(int(limit), self.window_max_events))
        slot_s = str(slot)
        self.client.window_begin(slot_s, int(from_index))
        pushed = 0
        i = int(from_index)
        while i < n and pushed < limit:
            ev = events[i]
            topic = str(getattr(ev, "topic", "") or "")
            if is_injectable_topic(topic):
                data = getattr(ev, "data", None)
                if not isinstance(data, dict):
                    data = {}
                self.client.push(
                    slot_s,
                    int(getattr(ev, "index", i)),
                    int(getattr(ev, "t_ns", 0) or 0),
                    topic,
                    data,
                )
                pushed += 1
            i += 1
        self.client.window_end(slot_s)
        self._slot_base[slot_s] = int(from_index)
        self._next_prefetch_from = i
        return pushed

    def ensure_windows_around(self, model: Any, index: int) -> None:
        """Fill A from index (Ego only), B with the next chunk."""
        events = getattr(model, "events", None) or []
        if not events:
            return
        index = max(0, min(int(index), len(events) - 1))
        self.fill_window(model, "A", index)
        if self.window_buffers >= 2 and self._next_prefetch_from < len(events):
            self.fill_window(model, "B", self._next_prefetch_from)

    def handle_need_window(
        self,
        model: Any,
        msg: dict[str, Any],
    ) -> int:
        """Respond to board ``need_window`` — fill requested range into a slot."""
        try:
            frm = int(msg.get("from", 0))
        except (TypeError, ValueError):
            frm = 0
        try:
            count = int(msg.get("count", self.window_size))
        except (TypeError, ValueError):
            count = self.window_size
        slot = str(msg.get("slot") or "")
        if slot not in {"A", "B"}:
            # Prefer empty/other slot: A if unknown, else B when A was last base
            slot = "B" if "A" in self._slot_base and self.window_buffers >= 2 else "A"
        return self.fill_window(model, slot, frm, count=count)
