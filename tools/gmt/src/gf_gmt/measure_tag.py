"""Tag a session JSONL by time window; editable tag catalog (session.tags.json)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TagRecord:
    id: str
    label: str = ""
    from_ns: int | None = None
    to_ns: int | None = None
    topics: list[str] = field(default_factory=list)
    notes: str = ""
    kind: str = "marker"  # "marker" (bookmark) | "range" (clip window)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TagRecord:
        topics = d.get("topics") or []
        if not isinstance(topics, list):
            topics = []
        kind = str(d.get("kind") or "").strip().lower()
        from_ns = _opt_int(d.get("from_ns"))
        to_ns = _opt_int(d.get("to_ns"))
        if kind not in {"marker", "range"}:
            # legacy: equal/missing to → marker; else range
            if from_ns is not None and (to_ns is None or to_ns == from_ns):
                kind = "marker"
            elif from_ns is not None and to_ns is not None:
                kind = "range"
            else:
                kind = "marker"
        return cls(
            id=str(d.get("id") or uuid.uuid4()),
            label=str(d.get("label") or ""),
            from_ns=from_ns,
            to_ns=to_ns,
            topics=[str(t) for t in topics if str(t).strip()],
            notes=str(d.get("notes") or ""),
            kind=kind,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "from_ns": self.from_ns,
            "to_ns": self.to_ns,
            "topics": list(self.topics),
            "notes": self.notes,
            "kind": self.kind,
        }

    @property
    def is_marker(self) -> bool:
        return self.kind != "range"

    def at_ns(self) -> int | None:
        """Bookmark time (prefer from_ns)."""
        if self.from_ns is not None:
            return self.from_ns
        return self.to_ns


def _opt_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    return int(v)


def tags_path_for_session(session: Path) -> Path:
    """Default sidecar: session.jsonl → session.tags.json."""
    return session.parent / f"{session.stem}.tags.json"


def load_tags(path: Path) -> list[TagRecord]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        items = data.get("tags") or []
    elif isinstance(data, list):
        items = data
    else:
        return []
    out: list[TagRecord] = []
    for item in items:
        if isinstance(item, dict):
            out.append(TagRecord.from_dict(item))
    return out


def save_tags(path: Path, tags: list[TagRecord]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "tags": [t.to_dict() for t in tags],
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def new_tag(
    *,
    label: str = "",
    from_ns: int | None = None,
    to_ns: int | None = None,
    topics: list[str] | None = None,
    notes: str = "",
    kind: str = "marker",
) -> TagRecord:
    k = kind if kind in {"marker", "range"} else "marker"
    if k == "marker" and from_ns is not None and to_ns is None:
        to_ns = from_ns
    return TagRecord(
        id=str(uuid.uuid4()),
        label=label or "untagged",
        from_ns=from_ns,
        to_ns=to_ns,
        topics=list(topics or []),
        notes=notes,
        kind=k,
    )


def upsert_tag(tags: list[TagRecord], tag: TagRecord) -> list[TagRecord]:
    for i, t in enumerate(tags):
        if t.id == tag.id:
            tags[i] = tag
            return tags
    tags.append(tag)
    return tags


def delete_tag(tags: list[TagRecord], tag_id: str) -> list[TagRecord]:
    return [t for t in tags if t.id != tag_id]


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
    return clip_session(
        inp,
        out,
        from_ns=from_ns,
        to_ns=to_ns,
        label=label,
        topics=topics,
    )


def clip_session(
    inp: Path,
    out: Path,
    *,
    from_ns: int | None = None,
    to_ns: int | None = None,
    label: str = "",
    topics: list[str] | None = None,
    tag_id: str = "",
) -> tuple[Path, int, int]:
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
            if topics:
                short = topic.rsplit("/", 1)[-1] if topic else ""
                if topic not in topics and short not in topics:
                    continue
            rows.append(row)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        if label or from_ns is not None or to_ns is not None or tag_id:
            meta = {
                "type": "tag_meta",
                "id": tag_id or "",
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


def clip_by_tag(inp: Path, out: Path, tag: TagRecord) -> tuple[Path, int, int]:
    return clip_session(
        inp,
        out,
        from_ns=tag.from_ns,
        to_ns=tag.to_ns,
        label=tag.label,
        topics=tag.topics or None,
        tag_id=tag.id,
    )
