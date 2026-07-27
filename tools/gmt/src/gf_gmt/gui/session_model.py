"""Session timeline model for GMT GUI (replay / order / animated DAG)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gf_gmt.gui.wall_time import SessionClock


@dataclass
class SessionEvent:
    index: int
    t_ns: int
    topic: str
    data: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    dt_ns: int = 0  # delta from previous event (0 for first)
    # optional topology hint after bind_sor
    from_proc: str = ""
    to_proc: str = ""
    service_short: str = ""


@dataclass
class SessionModel:
    events: list[SessionEvent] = field(default_factory=list)
    path: Path | None = None
    t_min: int = 0
    t_max: int = 0
    clock: SessionClock = field(default_factory=SessionClock)

    @property
    def empty(self) -> bool:
        return not self.events

    def wall_str(self, t_ns: int, *, compact: bool = False) -> str:
        return self.clock.format(t_ns, compact=compact)

    def load_jsonl(self, path: Path) -> None:
        rows: list[SessionEvent] = []
        clock: SessionClock | None = None
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                if obj.get("type") == "session_meta":
                    clock = SessionClock.from_meta(obj) or clock
                    continue
                if obj.get("type") == "tag_meta":
                    continue
                t = int(obj.get("t_ns") or obj.get("log_time_ns") or 0)
                data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
                if isinstance(data, dict) and data.get("timestamp_ns"):
                    try:
                        t = int(data["timestamp_ns"]) or t
                    except (TypeError, ValueError):
                        pass
                topic = str(obj.get("topic") or "")
                if not topic and "data" not in obj:
                    continue
                meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
                rows.append(
                    SessionEvent(
                        index=len(rows),
                        t_ns=t,
                        topic=topic,
                        data=dict(data) if isinstance(data, dict) else {},
                        meta=dict(meta),
                    )
                )
        rows.sort(key=lambda e: (e.t_ns, e.index))
        for i, ev in enumerate(rows):
            ev.index = i
            ev.dt_ns = 0 if i == 0 else max(0, ev.t_ns - rows[i - 1].t_ns)
        self.events = rows
        self.path = path
        if rows:
            self.t_min = rows[0].t_ns
            self.t_max = rows[-1].t_ns
            t0 = rows[0].t_ns
            if clock is None:
                try:
                    clock = SessionClock.provisional_from_file_mtime(
                        path.stat().st_mtime, t0
                    )
                except OSError:
                    clock = SessionClock.now_anchor(t0)
            elif clock.t0_ns == 0 and t0:
                clock.t0_ns = t0
            self.clock = clock
        else:
            self.t_min = self.t_max = 0
            self.clock = clock or SessionClock()

    def bind_sor(self, sor: dict[str, Any] | None) -> None:
        """Attach from/to process using dataflows when topic matches service short name."""
        if not sor:
            return
        by_short: dict[str, tuple[str, str, str]] = {}
        for flow in sor.get("dataflows") or []:
            if not isinstance(flow, dict):
                continue
            svc = str(flow.get("service") or "")
            short = svc.rsplit(".", 1)[-1] if svc else ""
            frm, to = str(flow.get("from") or ""), str(flow.get("to") or "")
            if short and frm and to and short not in by_short:
                by_short[short] = (frm, to, short)
        for ev in self.events:
            short = _topic_short(ev.topic)
            if short in by_short:
                frm, to, s = by_short[short]
                ev.from_proc, ev.to_proc, ev.service_short = frm, to, s
            else:
                ev.service_short = short

    def events_upto(self, t_ns: int) -> list[SessionEvent]:
        return [e for e in self.events if e.t_ns <= t_ns]

    def nearest_index(self, t_ns: int) -> int:
        if not self.events:
            return 0
        best = 0
        for i, e in enumerate(self.events):
            if e.t_ns <= t_ns:
                best = i
            else:
                break
        return best

    def ensure_clock_for_live(self) -> None:
        """On first live event, fix scheme-1 anchor if missing."""
        if self.clock.ready or not self.events:
            return
        self.clock = SessionClock.now_anchor(self.events[0].t_ns)

    def append_rows(
        self, rows: list[dict[str, Any]], *, sor: dict[str, Any] | None = None
    ) -> int:
        """Append already-normalized event dicts; returns count added."""
        added = 0
        for row in rows:
            if row.get("type") == "session_meta":
                c = SessionClock.from_meta(row)
                if c is not None:
                    self.clock = c
                continue
            prev_t = self.events[-1].t_ns if self.events else None
            ev = row_to_event(row, len(self.events), prev_t)
            if ev is None:
                continue
            self.events.append(ev)
            added += 1
        if added and self.events:
            self.t_min = self.events[0].t_ns
            self.t_max = self.events[-1].t_ns
            self.ensure_clock_for_live()
            if sor:
                self.bind_sor(sor)
        return added

    def clear_events(self) -> None:
        self.events.clear()
        self.t_min = self.t_max = 0


def _topic_short(topic: str) -> str:
    t = topic.strip("/")
    if not t:
        return ""
    return t.rsplit("/", 1)[-1]


def load_session(
    path: Path, *, sor: dict[str, Any] | None = None
) -> SessionModel:
    m = SessionModel()
    m.load_jsonl(path)
    m.bind_sor(sor)
    return m


@dataclass
class SessionFileTail:
    """Incremental JSONL reader for live tee'd session files."""

    path: Path | None = None
    offset: int = 0
    partial: str = ""

    def reset(self, path: Path | None = None) -> None:
        if path is not None:
            self.path = path
        self.offset = 0
        self.partial = ""

    def poll_lines(self) -> list[str]:
        """Return newly completed lines since last poll. Handles truncation."""
        if self.path is None or not self.path.is_file():
            return []
        size = self.path.stat().st_size
        if size < self.offset:
            self.offset = 0
            self.partial = ""
        if size == self.offset:
            return []
        with self.path.open("rb") as f:
            f.seek(self.offset)
            chunk = f.read()
            self.offset = f.tell()
        text = self.partial + chunk.decode("utf-8", errors="replace")
        parts = text.split("\n")
        self.partial = parts.pop()  # incomplete trailing line
        return [p for p in parts if p.strip()]


def row_to_event(row: dict[str, Any], index: int, prev_t: int | None) -> SessionEvent | None:
    if row.get("type") in {"tag_meta", "session_meta"}:
        return None
    t = int(row.get("t_ns") or row.get("log_time_ns") or 0)
    topic = str(row.get("topic") or "")
    if not topic and "data" not in row:
        return None
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    if isinstance(data, dict) and data.get("timestamp_ns"):
        try:
            t = int(data["timestamp_ns"]) or t
        except (TypeError, ValueError):
            pass
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    dt = 0 if prev_t is None else max(0, t - prev_t)
    return SessionEvent(
        index=index,
        t_ns=t,
        topic=topic,
        data=dict(data) if isinstance(data, dict) else {},
        meta=dict(meta),
        dt_ns=dt,
    )


def write_session_meta_line(fp: Any, clock: SessionClock) -> None:
    """Write scheme-1 anchor as first line of a live session file."""
    fp.write(json.dumps(clock.to_meta(), ensure_ascii=False) + "\n")
    fp.flush()
