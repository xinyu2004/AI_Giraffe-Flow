"""Session JSONL record helpers (host-side, P2 O-1)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TextIO


def append_event(
    out: TextIO | Path,
    *,
    t_ns: int,
    topic: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {"t_ns": int(t_ns), "topic": topic, "data": data}
    if meta:
        row["meta"] = meta
    line = json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"
    if isinstance(out, Path):
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            f.write(line)
    else:
        out.write(line)


_TRAJ_RE = re.compile(
    r"Trajectory#(?P<seq>\d+)\s+points=(?P<points>\d+)\s+ts_ns=(?P<ts>\d+)"
)
_EGO_HINT = re.compile(r"speed_mps|EgoMotion|nearest_cm=(?P<cm>\d+)")
_USS_RE = re.compile(r"UssZones#(?P<seq>\d+).*nearest_cm=(?P<cm>\d+).*speed=(?P<spd>[0-9.]+)")
_FCM_RE = re.compile(r"out#(?P<seq>\d+)\s+dyn=(?P<dyn>\d+).*frame=(?P<frame>\d+)")
_PLAN_RE = re.compile(
    r"Trajectory#(?P<seq>\d+).*dyn=(?P<dyn>\d+).*nearest_cm=(?P<cm>\d+)"
)


def events_from_sil_logs(log_dir: Path) -> list[dict[str, Any]]:
    """Parse multiproc SIL logs into session events (best-effort)."""
    events: list[dict[str, Any]] = []
    gw = log_dir / "gateway.log"
    if gw.is_file():
        for line in gw.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _TRAJ_RE.search(line)
            if m:
                events.append(
                    {
                        "t_ns": int(m.group("ts")),
                        "topic": "/gf/Trajectory",
                        "data": {
                            "seq": int(m.group("seq")),
                            "point_count": int(m.group("points")),
                            "source": "gateway",
                        },
                    }
                )
    plan = log_dir / "planning.log"
    if plan.is_file():
        # planning lines often lack absolute ts — use seq * 100ms synthetic if needed
        for line in plan.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _PLAN_RE.search(line)
            if m:
                seq = int(m.group("seq"))
                events.append(
                    {
                        "t_ns": seq * 100_000_000,
                        "topic": "/gf/planning/Trajectory",
                        "data": {
                            "seq": seq,
                            "dyn_obj_count": int(m.group("dyn")),
                            "nearest_cm": int(m.group("cm")),
                            "source": "planning",
                        },
                    }
                )
    uss = log_dir / "uss.log"
    if uss.is_file():
        for line in uss.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _USS_RE.search(line)
            if m:
                seq = int(m.group("seq"))
                events.append(
                    {
                        "t_ns": seq * 100_000_000,
                        "topic": "/gf/UssZones",
                        "data": {
                            "seq": seq,
                            "nearest_cm": int(m.group("cm")),
                            "speed_mps": float(m.group("spd")),
                            "source": "uss",
                        },
                    }
                )
    fcm = log_dir / "fcm.log"
    if fcm.is_file():
        for line in fcm.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _FCM_RE.search(line)
            if m:
                seq = int(m.group("seq"))
                events.append(
                    {
                        "t_ns": seq * 100_000_000,
                        "topic": "/gf/Perception_MESSAGE_Out_St",
                        "data": {
                            "seq": seq,
                            "dyn_obj_count": int(m.group("dyn")),
                            "frame": int(m.group("frame")),
                            "source": "fcm",
                        },
                    }
                )
    events.sort(key=lambda e: (int(e["t_ns"]), e["topic"]))
    return events


def _short_from_topic(topic: str) -> str:
    return str(topic).rsplit("/", 1)[-1]


def filter_events_by_services(
    events: list[dict[str, Any]],
    services: list[str] | None,
) -> list[dict[str, Any]]:
    """Keep only events whose topic short name is in the record whitelist.

    Empty / None whitelist → no events (record requires allowlist).
    """
    if not services:
        return []
    allow = {str(s).strip() for s in services if str(s).strip()}
    # also accept bare names without services.semantic. prefix
    allow |= {s.split(".")[-1] for s in list(allow)}
    out: list[dict[str, Any]] = []
    for e in events:
        short = _short_from_topic(str(e.get("topic") or ""))
        if short in allow:
            out.append(e)
    return out


def write_session_jsonl(events: list[dict[str, Any]], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, separators=(",", ":"), ensure_ascii=False) + "\n")
    return out


def load_record_services_from_obs(path: Path | None) -> list[str] | None:
    """Read record.services from generated/observability.json; None if missing."""
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rec = data.get("record") if isinstance(data, dict) else None
    if not isinstance(rec, dict):
        return None
    if str(rec.get("mode") or "") == "off":
        return []
    return [str(x) for x in (rec.get("services") or []) if str(x).strip()]


def record_from_sil_logs(
    log_dir: Path,
    out: Path,
    *,
    services: list[str] | None = None,
    observability_json: Path | None = None,
) -> tuple[Path, int]:
    events = events_from_sil_logs(log_dir)
    allow = services
    if allow is None and observability_json is not None:
        allow = load_record_services_from_obs(observability_json)
    if allow is None:
        # no whitelist provided → keep legacy full parse for fixtures/tests
        filtered = events
    else:
        filtered = filter_events_by_services(events, allow)
    write_session_jsonl(filtered, out)
    return out, len(filtered)
