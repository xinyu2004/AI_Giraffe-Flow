"""Foxglove bridge (P2 F-1 + P2.5 live).

Modes:
  1) validate/open helper — list topics in MCAP, print Studio steps
  2) --serve — tiny HTTP server that serves the .mcap for download
  3) --ws --jsonl — WebSocket replay of finished JSONL
  4) --ws --stdin — live NDJSON from stdin (iox_obs_tap | GMT …)

Implements Foxglove WebSocket protocol subset (stdlib only):
  - JSON: serverInfo, advertise, status
  - Binary Message Data (opcode 0x01, little-endian) after client subscribe

This is NOT the ROS package foxglove_bridge.
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
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, TextIO

from gf_gmt.measure_export import list_mcap_topics

# JSON Schema string for free-form object payloads (encoding=json)
_JSON_SCHEMA = json.dumps({"type": "object", "additionalProperties": True})


def describe_mcap(mcap: Path) -> dict[str, Any]:
    topics = list_mcap_topics(mcap)
    size = mcap.stat().st_size if mcap.is_file() else 0
    return {
        "path": str(mcap.resolve()),
        "size_bytes": size,
        "topics": topics,
        "ok": mcap.is_file() and mcap.read_bytes()[:8] == b"\x89MCAP0\r\n" and bool(topics),
    }


def print_studio_steps(info: dict[str, Any]) -> None:
    print("Foxglove Studio (recommended for P2):")
    print("  1. Open Foxglove Studio")
    print(f"  2. Open local file → {info['path']}")
    print(f"  3. Topics ({len(info['topics'])}):")
    for t in info["topics"] or ["(none detected)"]:
        print(f"       - {t}")


def serve_mcap_http(mcap: Path, host: str, port: int) -> None:
    directory = str(mcap.parent.resolve())
    name = mcap.name

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, fmt: str, *args: Any) -> None:
            print("[bridge-http]", fmt % args)

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving {directory} at http://{host}:{port}/{name}")
    print("Download MCAP then open in Foxglove Studio (File → Open local file).")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbridge stopped")


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


def _ws_send_binary(conn: socket.socket, payload: bytes) -> None:
    conn.sendall(_ws_frame(0x2, payload))


def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _ws_recv_frame(conn: socket.socket) -> tuple[int, bytes] | None:
    """Read one WebSocket frame from client (masked). Returns (opcode, payload)."""
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


def server_info_payload(name: str = "gf_gmt-bridge") -> dict[str, Any]:
    # Do not advertise "time" unless we send binary Time frames.
    return {
        "op": "serverInfo",
        "name": name,
        "capabilities": [],
        "supportedEncodings": ["json"],
    }


def channel_desc(channel_id: int, topic: str) -> dict[str, Any]:
    return {
        "id": channel_id,
        "topic": topic,
        "encoding": "json",
        "schemaName": "gf.JsonMsg",
        "schema": _JSON_SCHEMA,
        "schemaEncoding": "jsonschema",
    }


def advertise_payload(topics: list[str], *, start_id: int = 1) -> dict[str, Any]:
    channels = [channel_desc(start_id + i, t) for i, t in enumerate(topics)]
    return {"op": "advertise", "channels": channels}


def pack_message_data(subscription_id: int, t_ns: int, data: Any) -> bytes:
    """Foxglove binary Message Data (opcode 0x01), little-endian ints."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return struct.pack("<BIQ", 0x01, int(subscription_id), int(t_ns)) + payload


def parse_ndjson_row(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    row = json.loads(line)
    if row.get("type") == "tag_meta":
        return None
    return row


def rows_from_jsonl(jsonl: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with jsonl.open(encoding="utf-8") as f:
        for line in f:
            row = parse_ndjson_row(line)
            if row is not None:
                rows.append(row)
    return rows


def encode_ws_session_frames(
    rows: Iterable[dict[str, Any]],
    *,
    topics: list[str] | None = None,
) -> list[Any]:
    """Test helper: JSON control frames + binary Message Data (sub_id==channel_id)."""
    row_list = list(rows)
    topic_list = topics or sorted({str(r.get("topic") or "/gf/stub") for r in row_list}) or [
        "/gf/stub"
    ]
    frames: list[Any] = [
        json.dumps(server_info_payload()),
        json.dumps(advertise_payload(topic_list)),
    ]
    topic_id = {t: i + 1 for i, t in enumerate(topic_list)}
    for row in row_list:
        tid = topic_id.get(str(row.get("topic") or "/gf/stub"), 1)
        t_ns = int(row.get("t_ns") or 0)
        data = row.get("data", row)
        frames.append(pack_message_data(tid, t_ns, data))
    return frames


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
        "Sec-WebSocket-Protocol: foxglove.websocket.v1\r\n"
        "\r\n"
    )
    conn.sendall(resp.encode("ascii"))
    return True


def _send_json(conn: socket.socket, obj: dict[str, Any]) -> None:
    _ws_send_text(conn, json.dumps(obj, ensure_ascii=False))


class SessionState:
    """Per-connection channel advertise + client subscriptions."""

    def __init__(self) -> None:
        self.topic_to_channel: dict[str, int] = {}
        self.next_channel_id = 1
        # subscription_id (client) -> channel_id
        self.subscriptions: dict[int, int] = {}
        # channel_id -> list of subscription_ids
        self.channel_subs: dict[int, list[int]] = {}

    def ensure_channel(self, conn: socket.socket, topic: str) -> int:
        if topic in self.topic_to_channel:
            return self.topic_to_channel[topic]
        cid = self.next_channel_id
        self.next_channel_id += 1
        self.topic_to_channel[topic] = cid
        _send_json(conn, {"op": "advertise", "channels": [channel_desc(cid, topic)]})
        return cid

    def advertise_topics(self, conn: socket.socket, topics: list[str]) -> None:
        new_chs = []
        for t in topics:
            if t in self.topic_to_channel:
                continue
            cid = self.next_channel_id
            self.next_channel_id += 1
            self.topic_to_channel[t] = cid
            new_chs.append(channel_desc(cid, t))
        if new_chs:
            _send_json(conn, {"op": "advertise", "channels": new_chs})

    def handle_client_text(self, text: str) -> None:
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            return
        op = msg.get("op")
        if op == "subscribe":
            for sub in msg.get("subscriptions") or []:
                sid = int(sub["id"])
                cid = int(sub["channelId"])
                self.subscriptions[sid] = cid
                self.channel_subs.setdefault(cid, []).append(sid)
                print(f"[bridge-ws] subscribe sub={sid} channel={cid}", flush=True)
        elif op == "unsubscribe":
            for sid in msg.get("subscriptionIds") or []:
                sid = int(sid)
                cid = self.subscriptions.pop(sid, None)
                if cid is not None and cid in self.channel_subs:
                    self.channel_subs[cid] = [x for x in self.channel_subs[cid] if x != sid]
                print(f"[bridge-ws] unsubscribe sub={sid}", flush=True)

    def publish(self, conn: socket.socket, topic: str, t_ns: int, data: Any) -> int:
        """Send binary Message Data to all subscriptions of topic. Returns #sent."""
        cid = self.ensure_channel(conn, topic)
        subs = self.channel_subs.get(cid) or []
        if not subs:
            return 0
        sent = 0
        for sid in list(subs):
            _ws_send_binary(conn, pack_message_data(sid, t_ns, data))
            sent += 1
        return sent

    def poll_client(self, conn: socket.socket) -> bool:
        """Process pending client frames. False if connection closed."""
        conn.settimeout(0.0)
        try:
            while True:
                r, _, _ = select.select([conn], [], [], 0)
                if not r:
                    break
                frame = _ws_recv_frame(conn)
                if frame is None:
                    return False
                opcode, payload = frame
                if opcode == 0x8:  # close
                    return False
                if opcode == 0x9:  # ping → pong
                    conn.sendall(_ws_frame(0xA, payload))
                    continue
                if opcode == 0x1:  # text
                    self.handle_client_text(payload.decode("utf-8", errors="replace"))
                # binary client frames ignored in MVP
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            return False
        finally:
            try:
                conn.settimeout(0.05)
            except OSError:
                pass
        return True


def _listen(host: str, port: int) -> socket.socket:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    return srv


def replay_jsonl_ws(jsonl: Path, host: str, port: int, *, speed: float = 1.0) -> None:
    rows = rows_from_jsonl(jsonl)
    topics = sorted({str(r.get("topic") or "/gf/stub") for r in rows}) or ["/gf/stub"]

    srv = _listen(host, port)
    print(f"Foxglove WS (replay) ws://{host}:{port}", flush=True)
    print(f"  topics: {', '.join(topics)}", flush=True)
    print("  Studio → Open connection → Foxglove WebSocket", flush=True)

    while True:
        conn, addr = srv.accept()
        print(f"[bridge-ws] client {addr}", flush=True)
        state = SessionState()
        try:
            if not _ws_handshake(conn):
                conn.close()
                continue
            _send_json(conn, server_info_payload())
            state.advertise_topics(conn, topics)

            # Wait until Studio subscribes (or timeout)
            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline and not state.subscriptions:
                if not state.poll_client(conn):
                    break
                time.sleep(0.05)

            t0 = int(rows[0].get("t_ns") or 0) if rows else 0
            wall0 = time.monotonic()
            for row in rows:
                if not state.poll_client(conn):
                    break
                t_ns = int(row.get("t_ns") or 0)
                delay = max(0.0, ((t_ns - t0) / 1e9) / max(speed, 0.01) - (time.monotonic() - wall0))
                if delay > 0:
                    time.sleep(min(delay, 0.5))
                topic = str(row.get("topic") or "/gf/stub")
                data = row.get("data", row)
                state.publish(conn, topic, t_ns, data)
            print("[bridge-ws] replay done; connection stays open (Ctrl+C to stop)", flush=True)
            while state.poll_client(conn):
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            print(f"[bridge-ws] client gone: {exc}", flush=True)
        finally:
            try:
                conn.close()
            except OSError:
                pass


def live_stdin_ws(
    host: str,
    port: int,
    *,
    stream: TextIO | None = None,
) -> None:
    """Live: wait for Studio subscribe, stream NDJSON from stdin as binary Message Data."""
    inp = stream if stream is not None else sys.stdin
    srv = _listen(host, port)
    print(f"Foxglove WS (live stdin) ws://{host}:{port}", flush=True)
    print("  Studio → Open connection → Foxglove WebSocket", flush=True)
    print("  Waiting for client; messages flow after Studio subscribes …", flush=True)

    while True:
        conn, addr = srv.accept()
        print(f"[bridge-ws-live] client {addr}", flush=True)
        state = SessionState()
        try:
            if not _ws_handshake(conn):
                conn.close()
                continue
            _send_json(conn, server_info_payload("gf_gmt-bridge-live"))
            state.advertise_topics(conn, ["/gf/EgoMotion", "/gf/Trajectory"])

            fd = -1
            if hasattr(inp, "fileno"):
                try:
                    fd = inp.fileno()
                except (OSError, io.UnsupportedOperation):
                    fd = -1

            buf = ""
            published = 0
            while True:
                if not state.poll_client(conn):
                    print("[bridge-ws-live] client closed", flush=True)
                    break

                lines: list[str] = []
                if fd >= 0:
                    r, _, _ = select.select([fd], [], [], 0.05)
                    if r:
                        chunk = os_read_chunk(inp)
                        if chunk == "" and not buf:
                            print("[bridge-ws-live] stdin EOF", flush=True)
                            break
                        buf += chunk
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            lines.append(line)
                else:
                    line = inp.readline()
                    if line == "":
                        break
                    lines.append(line.rstrip("\n"))
                    time.sleep(0.01)

                for line in lines:
                    try:
                        row = parse_ndjson_row(line)
                    except json.JSONDecodeError as exc:
                        print(f"[bridge-ws-live] bad json: {exc}", flush=True)
                        continue
                    if row is None:
                        continue
                    topic = str(row.get("topic") or "/gf/stub")
                    t_ns = int(row.get("t_ns") or 0)
                    data = row.get("data", row)
                    n = state.publish(conn, topic, t_ns, data)
                    published += n
                    if published and published % 50 == 0:
                        print(f"[bridge-ws-live] published {published} msgs", flush=True)
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            print(f"[bridge-ws-live] client gone: {exc}", flush=True)
        finally:
            try:
                conn.close()
            except OSError:
                pass


def os_read_chunk(stream: TextIO, size: int = 4096) -> str:
    try:
        raw = os.read(stream.fileno(), size)
    except OSError:
        return ""
    if not raw:
        return ""
    return raw.decode("utf-8", errors="replace")


def main_bridge(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="GMT bridge foxglove")
    p.add_argument("--mcap", type=Path, default=None)
    p.add_argument("--jsonl", type=Path, default=None, help="For --ws replay")
    p.add_argument("--serve", action="store_true", help="HTTP-serve MCAP directory")
    p.add_argument("--ws", action="store_true", help="WebSocket (replay or live)")
    p.add_argument(
        "--stdin",
        action="store_true",
        help="With --ws: live NDJSON from stdin (iox_obs_tap pipe)",
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args(argv)

    if args.mcap:
        info = describe_mcap(args.mcap)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        if not info["ok"]:
            print("MCAP invalid or no topics detected", flush=True)
            return 1
        print_studio_steps(info)
        if args.serve:
            serve_mcap_http(args.mcap, args.host, args.port)
            return 0
        if not args.ws:
            return 0

    if args.ws:
        if args.stdin:
            live_stdin_ws(args.host, args.port)
            return 0
        src = args.jsonl
        if src is None and args.mcap is not None:
            print("--ws needs --jsonl or --stdin (MCAP live decode not supported)", flush=True)
            return 2
        if src is None or not src.is_file():
            print("need --jsonl FILE or --stdin with --ws", flush=True)
            return 2
        replay_jsonl_ws(src, args.host, args.port, speed=args.speed)
        return 0

    print(
        "usage: GMT bridge foxglove --mcap FILE [--serve] "
        "| --ws --jsonl FILE | --ws --stdin",
        flush=True,
    )
    return 2
