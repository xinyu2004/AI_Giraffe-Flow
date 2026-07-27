"""Import iox_obs_tap NDJSON → session JSONL (G2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_session_line(line: str) -> dict[str, Any] | None:
    """Parse one JSONL line: session_meta control row, or a tap event, else None."""
    line = line.strip().lstrip("\ufeff")
    if not line or not line.startswith("{"):
        return None
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict):
        return None
    if row.get("type") == "session_meta":
        return dict(row)
    if row.get("type") == "tag_meta":
        return None
    return parse_tap_row_obj(row)


def parse_tap_row(line: str) -> dict[str, Any] | None:
    """Normalize one NDJSON line into a session event row, or None to skip."""
    line = line.strip().lstrip("\ufeff")
    if not line or not line.startswith("{"):
        return None
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict):
        return None
    return parse_tap_row_obj(row)


def parse_tap_row_obj(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize an already-parsed dict into a session event row."""
    if row.get("type") in {"tag_meta", "session_meta"}:
        return None
    t_ns = row.get("t_ns")
    if t_ns is None:
        t_ns = row.get("log_time_ns")
    if t_ns is None:
        return None
    topic = str(row.get("topic") or "").strip()
    if not topic:
        return None
    data = row.get("data")
    if not isinstance(data, dict):
        # allow flat payloads: everything except t/topic/meta → data
        data = {
            k: v
            for k, v in row.items()
            if k not in {"t_ns", "log_time_ns", "topic", "meta", "type"}
        }
    out: dict[str, Any] = {
        "t_ns": int(t_ns),
        "topic": topic,
        "data": dict(data),
    }
    meta = row.get("meta")
    if isinstance(meta, dict) and meta:
        out["meta"] = dict(meta)
    return out


def record_from_ndjson(inp: Path, out: Path) -> tuple[Path, int]:
    """
    Convert tap NDJSON / session-like JSONL into a canonical session.jsonl.
    Returns (out_path, event_count).
    """
    rows: list[dict[str, Any]] = []
    with inp.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            row = parse_tap_row(line)
            if row is not None:
                rows.append(row)
    rows.sort(key=lambda r: (int(r["t_ns"]), str(r.get("topic") or "")))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
    return out, len(rows)
