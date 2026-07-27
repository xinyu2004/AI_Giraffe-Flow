"""Colored connection-status lines for SIL bridges (stderr)."""

from __future__ import annotations

import os
import sys

# ANSI: listen=yellow, connected=green, disconnected=cyan, error=red
_KIND = {
    "listen": "33",
    "ok": "32",
    "bye": "36",
    "err": "31",
}


def _use_color() -> bool:
    # Bridges under process-sub / pipes: stderr may not be a TTY.
    force = os.environ.get("GF_STATUS_COLOR") or os.environ.get("FORCE_COLOR")
    if os.environ.get("NO_COLOR"):
        return False
    if force is not None and force != "":
        return force != "0"
    if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
        return True
    try:
        return os.path.exists("/dev/tty") and os.access("/dev/tty", os.W_OK)
    except OSError:
        return False


def conn_status(tag: str, kind: str, msg: str) -> None:
    """Print ``[tag] msg`` to stderr; color by kind when stderr is a TTY."""
    line = f"[{tag}] {msg}"
    code = _KIND.get(kind)
    if code and _use_color():
        line = f"\033[{code}m{line}\033[0m"
    print(line, file=sys.stderr, flush=True)
