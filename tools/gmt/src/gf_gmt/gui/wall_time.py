"""Session wall-clock scheme 1: one anchor + (t_ns - t0_ns).

wall(t) = wall_anchor_unix_ns + (t_ns - t0_ns)

Meta line in JSONL (optional first/control row):
  {"type":"session_meta","wall_anchor_unix_ns":...,"t0_ns":...}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def format_wall_ns(wall_unix_ns: int) -> str:
    """Human wall time, local timezone: 2026-05-30 20:01:06.220"""
    if wall_unix_ns <= 0:
        return "—"
    sec, nsec = divmod(int(wall_unix_ns), 1_000_000_000)
    ms = nsec // 1_000_000
    dt = datetime.fromtimestamp(sec, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{ms:03d}"


def format_wall_compact(wall_unix_ns: int) -> str:
    """Compact: 2026-05-30-20-01-06-220"""
    if wall_unix_ns <= 0:
        return "—"
    sec, nsec = divmod(int(wall_unix_ns), 1_000_000_000)
    ms = nsec // 1_000_000
    dt = datetime.fromtimestamp(sec, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d-%H-%M-%S") + f"-{ms:03d}"


class SessionClock:
    """Scheme-1 clock bound to a session timeline."""

    def __init__(
        self,
        *,
        wall_anchor_unix_ns: int | None = None,
        t0_ns: int = 0,
    ) -> None:
        self.wall_anchor_unix_ns = wall_anchor_unix_ns
        self.t0_ns = int(t0_ns)

    @property
    def ready(self) -> bool:
        return self.wall_anchor_unix_ns is not None and self.wall_anchor_unix_ns > 0

    def wall_unix_ns(self, t_ns: int) -> int | None:
        if not self.ready:
            return None
        assert self.wall_anchor_unix_ns is not None
        return int(self.wall_anchor_unix_ns) + (int(t_ns) - self.t0_ns)

    def format(self, t_ns: int, *, compact: bool = False) -> str:
        w = self.wall_unix_ns(t_ns)
        if w is None:
            return "—"
        return format_wall_compact(w) if compact else format_wall_ns(w)

    def to_meta(self) -> dict[str, Any]:
        return {
            "type": "session_meta",
            "schema": "gf_session_clock_v1",
            "wall_anchor_unix_ns": self.wall_anchor_unix_ns,
            "t0_ns": self.t0_ns,
        }

    @classmethod
    def from_meta(cls, obj: dict[str, Any]) -> SessionClock | None:
        if obj.get("type") != "session_meta":
            return None
        wa = obj.get("wall_anchor_unix_ns")
        if wa is None:
            return None
        return cls(wall_anchor_unix_ns=int(wa), t0_ns=int(obj.get("t0_ns") or 0))

    @classmethod
    def provisional_from_file_mtime(cls, mtime_s: float, t0_ns: int) -> SessionClock:
        """Fallback when JSONL has no session_meta: file mtime ≈ wall at t0."""
        return cls(
            wall_anchor_unix_ns=int(mtime_s * 1_000_000_000),
            t0_ns=int(t0_ns),
        )

    @classmethod
    def now_anchor(cls, t0_ns: int = 0) -> SessionClock:
        import time

        return cls(wall_anchor_unix_ns=time.time_ns(), t0_ns=int(t0_ns))
