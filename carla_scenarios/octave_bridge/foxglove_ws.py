"""Minimal Foxglove WebSocket hub for host BEV (reuses gf_gmt.bridge_foxglove subset).

Studio: Open connection → ws://127.0.0.1:<port> → Image panel → /gf/driving/bev/compressed
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Any, Optional

from .bev_feed import ensure_gf_gmt_on_path

TOPIC_BEV = "/gf/driving/bev/compressed"


class FoxgloveBevHub:
    """Accept Studio clients; publish one CompressedImage topic from bev_feed rows."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        if ensure_gf_gmt_on_path() is None:
            raise ModuleNotFoundError(
                "gf_gmt required for Foxglove WS — set GF_GMT_SRC to …/gmt/src"
            )
        from gf_gmt.bridge_foxglove import (  # noqa: WPS433
            SessionState,
            _listen,
            _send_json,
            _ws_handshake,
            server_info_payload,
        )

        self._SessionState = SessionState
        self._send_json = _send_json
        self._ws_handshake = _ws_handshake
        self._server_info_payload = server_info_payload
        self.host = host
        self.port = port
        self._srv = _listen(host, port)
        self._srv.settimeout(0.5)
        self._clients: list[tuple[socket.socket, Any]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pub_n = 0
        self._sub_logged = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._accept_loop, name="fg-bev-ws", daemon=True)
        self._thread.start()
        print(
            f"[octave_bridge] Foxglove WS ws://127.0.0.1:{self.port} "
            f"topic={TOPIC_BEV}",
            flush=True,
        )

    def stop(self) -> None:
        self._stop.set()
        try:
            self._srv.close()
        except OSError:
            pass
        with self._lock:
            for conn, _ in self._clients:
                try:
                    conn.close()
                except OSError:
                    pass
            self._clients.clear()

    def publish_row(self, row: dict[str, Any]) -> int:
        """Publish bev_feed camera row (topic + data). Returns # binary frames sent."""
        topic = str(row.get("topic") or TOPIC_BEV)
        t_ns = int(row.get("t_ns") or time.time_ns())
        data = row.get("data") if isinstance(row.get("data"), dict) else row
        sent_total = 0
        dead: list[tuple[socket.socket, Any]] = []
        with self._lock:
            clients = list(self._clients)
        for conn, session in clients:
            try:
                if not session.poll_client(conn):
                    dead.append((conn, session))
                    continue
                if session.subscribed_topics_this_poll and not self._sub_logged:
                    self._sub_logged = True
                    print(
                        f"[octave_bridge] Foxglove subscribed {session.subscribed_topics_this_poll}",
                        flush=True,
                    )
                n = session.publish(conn, topic, t_ns, data)
                sent_total += n
            except OSError:
                dead.append((conn, session))
        if dead:
            with self._lock:
                for item in dead:
                    if item in self._clients:
                        self._clients.remove(item)
                    try:
                        item[0].close()
                    except OSError:
                        pass
        self._pub_n += 1
        if self._pub_n == 1:
            print("[octave_bridge] first BEV frame composed (subscribe Image in Studio)", flush=True)
        return sent_total

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, addr = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._client_setup, args=(conn, addr), daemon=True
            ).start()

    def _client_setup(self, conn: socket.socket, addr: Any) -> None:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            if not self._ws_handshake(conn):
                conn.close()
                return
            session = self._SessionState()
            self._send_json(conn, self._server_info_payload(name="octave_bridge-bev"))
            session.advertise_topics(conn, [TOPIC_BEV])
            with self._lock:
                self._clients.append((conn, session))
            print(f"[octave_bridge] Foxglove client {addr}", flush=True)
            # Keep draining subscribe until removed by publish path / stop
            while not self._stop.is_set():
                with self._lock:
                    alive = any(c is conn for c, _ in self._clients)
                if not alive:
                    break
                if not session.poll_client(conn):
                    break
                time.sleep(0.02)
        except OSError:
            pass
        finally:
            with self._lock:
                self._clients = [(c, s) for c, s in self._clients if c is not conn]
            try:
                conn.close()
            except OSError:
                pass
            print(f"[octave_bridge] Foxglove client gone {addr}", flush=True)
