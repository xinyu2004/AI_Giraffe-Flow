"""GMT live NDJSON bridge — stdin tap → WebSocket for GMT GUI (Foxglove-style connect).

Protocol (stdlib WebSocket text frames):
  - Server → client: {"op":"hello","proto":"gf_gmt_live","version":1}
  - Server → client: raw NDJSON lines (one frame per line)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import select
import socket
import struct
import sys
from typing import Any, TextIO

DEFAULT_LIVE_PORT = 8766


def hello_payload() -> dict[str, Any]:
    return {"op": "hello", "proto": "gf_gmt_live", "version": 1}


def _parse(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def is_hello(msg: dict[str, Any] | None) -> bool:
    return bool(
        msg
        and msg.get("op") == "hello"
        and msg.get("proto") == "gf_gmt_live"
    )


def _ws_accept_key(sec_key: str) -> str:
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((sec_key + guid).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def _ws_frame(opcode: int, payload: bytes) -> bytes:
    header = bytearray([0x80 | (opcode & 0x0F)])
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < (1 << 16):
        header.append(126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", n))
    return bytes(header) + payload


def _ws_send_text(conn: socket.socket, text: str) -> None:
    conn.sendall(_ws_frame(0x1, text.encode("utf-8")))


def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _ws_recv_frame(conn: socket.socket) -> tuple[int, bytes] | None:
    hdr = _recv_exact(conn, 2)
    if hdr is None:
        return None
    opcode = hdr[0] & 0x0F
    masked = (hdr[1] & 0x80) != 0
    length = hdr[1] & 0x7F
    if length == 126:
        ext = _recv_exact(conn, 2)
        if ext is None:
            return None
        length = struct.unpack("!H", ext)[0]
    elif length == 127:
        ext = _recv_exact(conn, 8)
        if ext is None:
            return None
        length = struct.unpack("!Q", ext)[0]
    mask = b""
    if masked:
        m = _recv_exact(conn, 4)
        if m is None:
            return None
        mask = m
    raw = _recv_exact(conn, length) if length else b""
    if raw is None:
        return None
    if masked:
        raw = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
    return opcode, raw


def _ws_handshake(conn: socket.socket) -> bool:
    req = b""
    while b"\r\n\r\n" not in req:
        chunk = conn.recv(4096)
        if not chunk:
            return False
        req += chunk
    text = req.decode("utf-8", errors="replace")
    key = ""
    for line in text.split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
    if not key:
        return False
    accept = _ws_accept_key(key)
    resp = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    )
    conn.sendall(resp.encode("ascii"))
    return True


def _listen(host: str, port: int) -> socket.socket:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((host, port))
    except OSError as exc:
        srv.close()
        raise OSError(
            exc.errno,
            f"{exc.strerror}: ws://{host}:{port} already in use "
            f"(旧 run_sil / GMT bridge 未退出)。"
            f" 处理: 停掉另一终端的 run_sil，或 "
            f"GF_SIL_KILL_STALE=1 bash …/run_sil.sh，或 "
            f"`ss -ltnp | grep {port}` 后 kill",
        ) from exc
    srv.listen(1)
    srv.setblocking(False)
    return srv


def os_read_chunk(stream: TextIO, size: int = 4096) -> str:
    try:
        raw = os.read(stream.fileno(), size)
    except OSError:
        return ""
    if not raw:
        return ""
    return raw.decode("utf-8", errors="replace")


def serve_live_stdin(
    host: str,
    port: int,
    *,
    stream: TextIO | None = None,
) -> None:
    """Read NDJSON from stdin; forward each line to a connected GMT GUI client."""
    inp = stream if stream is not None else sys.stdin
    srv = _listen(host, port)
    print(f"GMT live ws://{host}:{port}", flush=True)
    print("  state=LISTENING — wait GMT GUI「连接 Live」", flush=True)
    print("  GMT GUI → 连接 host:port", flush=True)

    fd = -1
    if hasattr(inp, "fileno"):
        try:
            fd = inp.fileno()
        except (OSError, io.UnsupportedOperation):
            fd = -1

    conn: socket.socket | None = None
    buf = ""
    stdin_eof = False
    forwarded = 0

    def _close_client() -> None:
        nonlocal conn
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        conn = None

    try:
        while not stdin_eof or conn is not None:
            rlist: list[Any] = [srv]
            if fd >= 0 and not stdin_eof:
                rlist.append(fd)
            if conn is not None:
                rlist.append(conn)

            try:
                ready, _, _ = select.select(rlist, [], [], 0.2)
            except InterruptedError:
                continue

            if conn is None and srv in ready:
                try:
                    new_conn, addr = srv.accept()
                except OSError as exc:
                    print(f"[live-bridge] accept error: {exc}", flush=True)
                else:
                    print(f"[live-bridge] client {addr}", flush=True)
                    try:
                        new_conn.setblocking(True)
                        if not _ws_handshake(new_conn):
                            print("[live-bridge] state=HANDSHAKE_FAIL", flush=True)
                            new_conn.close()
                        else:
                            new_conn.setblocking(False)
                            _ws_send_text(new_conn, json.dumps(hello_payload()))
                            conn = new_conn
                            print(
                                f"[live-bridge] state=CONNECTED peer={addr[0]}:{addr[1]}",
                                flush=True,
                            )
                    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                        print(f"[live-bridge] handshake failed: {exc}", flush=True)
                        try:
                            new_conn.close()
                        except OSError:
                            pass

            if conn is not None and conn in ready:
                frame = _ws_recv_frame(conn)
                if frame is None:
                    print("[live-bridge] state=DISCONNECTED (client closed)", flush=True)
                    _close_client()
                else:
                    opcode, payload = frame
                    if opcode == 0x8:
                        print("[live-bridge] state=DISCONNECTED (ws close)", flush=True)
                        _close_client()
                    elif opcode == 0x1:
                        msg = _parse(payload.decode("utf-8", errors="replace"))
                        if msg and msg.get("op") == "ping":
                            try:
                                _ws_send_text(conn, json.dumps({"op": "pong"}))
                            except OSError:
                                print(
                                    "[live-bridge] state=DISCONNECTED (pong failed)",
                                    flush=True,
                                )
                                _close_client()

            lines: list[str] = []
            if fd >= 0 and fd in ready:
                chunk = os_read_chunk(inp)
                if chunk == "":
                    if not buf:
                        stdin_eof = True
                        print("[live-bridge] stdin EOF", flush=True)
                else:
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        lines.append(line)
            elif fd < 0 and not stdin_eof:
                line = inp.readline()
                if line == "":
                    stdin_eof = True
                else:
                    lines.append(line.rstrip("\n"))

            for line in lines:
                # forward only NDJSON objects; drop pipe noise
                stripped = line.strip().lstrip("\ufeff")
                if not stripped.startswith("{"):
                    continue
                if conn is None:
                    continue
                try:
                    _ws_send_text(conn, stripped)
                    forwarded += 1
                    if forwarded % 100 == 0:
                        print(f"[live-bridge] forwarded {forwarded} lines", flush=True)
                except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                    print(
                        f"[live-bridge] state=DISCONNECTED send failed: {exc}",
                        flush=True,
                    )
                    _close_client()

            if stdin_eof and conn is None:
                break
    except KeyboardInterrupt:
        print("\n[live-bridge] stopped", flush=True)
    finally:
        _close_client()
        try:
            srv.close()
        except OSError:
            pass


def main_live_bridge(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="GMT bridge live")
    p.add_argument(
        "--stdin",
        action="store_true",
        help="Read NDJSON lines from stdin (pipe from gf_iox_obs_tap)",
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_LIVE_PORT)
    args = p.parse_args(argv)

    if not args.stdin:
        print("usage: GMT bridge live --stdin [--host HOST] [--port PORT]", flush=True)
        return 2

    try:
        serve_live_stdin(args.host, args.port)
    except KeyboardInterrupt:
        print("\n[live-bridge] stopped", flush=True)
    except OSError as exc:
        print(f"[live-bridge] FATAL: {exc}", flush=True)
        return 1
    return 0
