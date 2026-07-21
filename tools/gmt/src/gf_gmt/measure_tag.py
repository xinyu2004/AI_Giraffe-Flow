"""Tag a session JSONL by time window (P2 O-2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def tag_session(
    inp: Path,
    out: Path,
    *,
    from_ns: int | None = None,
    to_ns: int | None = None,
    label: str = "",
    topics: list[str] | None = None,
) -> tuple[Path, int, int]:
    """
    Clip session to [from_ns, to_ns] (inclusive) and optional topic filter.
    Writes a leading meta line when label is set.
    Returns (out, kept, total).
    """
    rows: list[dict[str, Any]] = []
    total = 0
    with inp.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            row = json.loads(line)
            if row.get("type") == "tag_meta":
                continue
            t = int(row.get("t_ns") or row.get("log_time_ns") or 0)
            if from_ns is not None and t < from_ns:
                continue
            if to_ns is not None and t > to_ns:
                continue
            topic = str(row.get("topic") or "")
            if topics and topic and topic not in topics:
                continue
            rows.append(row)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        if label or from_ns is not None or to_ns is not None:
            meta = {
                "type": "tag_meta",
                "label": label or "untagged",
                "from_ns": from_ns,
                "to_ns": to_ns,
                "topics": topics or [],
                "kept": len(rows),
                "source_total": total,
            }
            f.write(json.dumps(meta, separators=(",", ":"), ensure_ascii=False) + "\n")
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
    return out, len(rows), total
