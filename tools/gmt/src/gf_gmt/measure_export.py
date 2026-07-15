"""Minimal MCAP writer (P1 stub — no Foxglove bridge).

Produces a structurally valid MCAP 0 file with Header / Schema / Channel /
Message / DataEnd / Footer. Enough for `measure export` 雏形; full Tag/bench
belongs to P2.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Iterable

MAGIC = b"\x89MCAP0\r\n"

OPCODE_HEADER = 0x01
OPCODE_FOOTER = 0x02
OPCODE_SCHEMA = 0x03
OPCODE_CHANNEL = 0x04
OPCODE_MESSAGE = 0x05
OPCODE_DATA_END = 0x0F


def _u16(n: int) -> bytes:
    return struct.pack("<H", n)


def _u32(n: int) -> bytes:
    return struct.pack("<I", n)


def _u64(n: int) -> bytes:
    return struct.pack("<Q", n)


def _str(s: str) -> bytes:
    b = s.encode("utf-8")
    return _u32(len(b)) + b


def _bytes_field(b: bytes) -> bytes:
    return _u32(len(b)) + b


def _map_str(m: dict[str, str]) -> bytes:
    body = b"".join(_str(k) + _str(v) for k, v in m.items())
    return _u32(len(body)) + body


def _record(opcode: int, data: bytes) -> bytes:
    return bytes([opcode]) + _u64(len(data)) + data


def write_mcap(
    out_path: Path,
    messages: Iterable[dict[str, Any]],
    *,
    topic: str = "/gf/stub",
    schema_name: str = "gf.StubMsg",
    library: str = "gf_gmt/0.1",
) -> Path:
    """Write messages: each {log_time_ns, data: bytes|dict}."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema_data = json.dumps(
        {"type": "object", "properties": {"seq": {"type": "integer"}, "note": {"type": "string"}}},
        separators=(",", ":"),
    ).encode("utf-8")

    chunks: list[bytes] = [MAGIC]
    chunks.append(_record(OPCODE_HEADER, _str("") + _str(library)))
    chunks.append(
        _record(
            OPCODE_SCHEMA,
            _u16(1) + _str(schema_name) + _str("jsonschema") + _bytes_field(schema_data),
        )
    )
    chunks.append(
        _record(
            OPCODE_CHANNEL,
            _u16(1)
            + _u16(1)
            + _str(topic)
            + _str("json")
            + _map_str({}),
        )
    )

    seq = 0
    for msg in messages:
        payload = msg.get("data")
        if isinstance(payload, dict):
            payload_b = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        elif isinstance(payload, (bytes, bytearray)):
            payload_b = bytes(payload)
        else:
            payload_b = str(payload).encode("utf-8")
        log_time = int(msg.get("log_time_ns") or msg.get("t_ns") or 0)
        chunks.append(
            _record(
                OPCODE_MESSAGE,
                _u16(1) + _u32(seq) + _u64(log_time) + _u64(log_time) + payload_b,
            )
        )
        seq += 1

    chunks.append(_record(OPCODE_DATA_END, _u32(0)))
    # summary_start=0, summary_offset_start=0, summary_crc=0 → no summary section
    chunks.append(_record(OPCODE_FOOTER, _u64(0) + _u64(0) + _u32(0)))
    chunks.append(MAGIC)

    out_path.write_bytes(b"".join(chunks))
    return out_path


def export_session_jsonl(session_path: Path, out_mcap: Path, *, topic: str = "/gf/stub") -> Path:
    """Read JSONL lines {t_ns|log_time_ns, data|payload} → MCAP."""
    msgs: list[dict[str, Any]] = []
    with session_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            data = row.get("data", row.get("payload", row))
            msgs.append(
                {
                    "log_time_ns": row.get("log_time_ns", row.get("t_ns", 0)),
                    "data": data,
                }
            )
    if not msgs:
        # synthetic one-shot so empty session still exports a valid file
        msgs = [{"log_time_ns": 0, "data": {"seq": 0, "note": "empty_session"}}]
    return write_mcap(out_mcap, msgs, topic=topic)
