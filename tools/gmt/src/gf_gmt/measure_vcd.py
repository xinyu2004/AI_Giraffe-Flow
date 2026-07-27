"""Export session JSONL → IEEE 1364 VCD (GTKWave host path, P2.5 C1)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _topic_short(topic: str) -> str:
    t = (topic or "").strip()
    if not t:
        return "stub"
    t = t.strip("/")
    if t.startswith("gf/"):
        t = t[3:]
    return t.rsplit("/", 1)[-1] or "stub"


def _scalar_fields(data: Any) -> dict[str, float]:
    """Keep flat int/float/bool scalars; skip nested / arrays / strings."""
    if not isinstance(data, dict):
        return {}
    out: dict[str, float] = {}
    for key, val in data.items():
        name = str(key).strip()
        if not name or not name.replace("_", "").isalnum():
            continue
        if isinstance(val, bool):
            out[name] = float(int(val))
        elif isinstance(val, int) and not isinstance(val, bool):
            out[name] = float(val)
        elif isinstance(val, float) and math.isfinite(val):
            out[name] = float(val)
    return out


def _vcd_id(index: int) -> str:
    """Map 0.. → printable VCD identifier."""
    chars = [chr(c) for c in range(33, 127) if chr(c) not in " \t\n\r"]
    if index < len(chars):
        return chars[index]
    n = len(chars)
    x = index
    out: list[str] = []
    while True:
        out.append(chars[x % n])
        x = x // n - 1
        if x < 0:
            break
    return "".join(reversed(out))


def export_session_vcd(
    session_path: Path,
    out_vcd: Path,
    *,
    module: str = "gf",
) -> tuple[Path, int, int]:
    """
    Convert session JSONL → VCD (timescale 1 ns).

    Returns (out_path, n_vars, n_events).
    Signal names: ``gf.<service_short>.<field>`` (as real for GTKWave).
    """
    events: list[tuple[int, str, dict[str, float]]] = []
    with session_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("type") in {
                "tag_meta",
                "session_meta",
            }:
                continue
            t = row.get("t_ns")
            if t is None:
                t = row.get("log_time_ns", i)
            topic = str(row.get("topic") or "")
            data = row.get("data")
            if not isinstance(data, dict):
                data = {
                    k: v
                    for k, v in row.items()
                    if k not in {"t_ns", "log_time_ns", "topic", "meta", "type"}
                }
            fields = _scalar_fields(data)
            if not fields:
                continue
            events.append((int(t), _topic_short(topic), fields))

    var_names: list[str] = []
    seen: set[str] = set()
    for _t, short, fields in events:
        for field in fields:
            name = f"{module}.{short}.{field}"
            if name not in seen:
                seen.add(name)
                var_names.append(name)

    if not var_names:
        var_names = [f"{module}.stub.seq"]
        events = [(0, "stub", {"seq": 0.0})]

    id_of = {name: _vcd_id(i) for i, name in enumerate(var_names)}

    lines: list[str] = [
        "$date GMT measure export vcd $end",
        "$version gf_gmt VCD 0.1 $end",
        "$timescale 1 ns $end",
        f"$scope module {module} $end",
    ]
    for name in var_names:
        lines.append(f"$var real 64 {id_of[name]} {name} $end")
    lines.extend(["$upscope $end", "$enddefinitions $end"])

    last: dict[str, float] = {}
    by_t: dict[int, list[tuple[str, dict[str, float]]]] = {}
    for t, short, fields in events:
        by_t.setdefault(t, []).append((short, fields))

    for t in sorted(by_t):
        lines.append(f"#{t}")
        for short, fields in by_t[t]:
            for field, val in fields.items():
                name = f"{module}.{short}.{field}"
                if name not in id_of or last.get(name) == val:
                    continue
                last[name] = val
                lines.append(f"r{val:.16g} {id_of[name]}")

    out_vcd.parent.mkdir(parents=True, exist_ok=True)
    out_vcd.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_vcd, len(var_names), len(events)
