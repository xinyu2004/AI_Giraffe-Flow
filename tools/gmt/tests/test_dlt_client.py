"""Unit tests for DLT v1 frame parse (no daemon required)."""

from __future__ import annotations

import struct

from gf_gmt.dlt_client import iter_dlt_frames, parse_dlt_message


def _build_verbose_string_frame(app: bytes, ctx: bytes, text: str) -> bytes:
    """Minimal DLT v1: UEH+WEID+WSID+WTMS, one STRING arg (little payload endian)."""
    assert len(app) == 4 and len(ctx) == 4
    payload = struct.pack("<I", 0x00000200)  # DLT_TYPE_INFO_STRG
    raw = text.encode("utf-8") + b"\x00"
    payload += struct.pack("<H", len(raw)) + raw
    ext = bytes([0x41, 0x01]) + app + ctx  # msin log/info, noar=1
    body = b"ECU1" + struct.pack(">I", 1) + struct.pack(">I", 0) + ext + payload
    htyp = 0x3D  # UEH|WEID|WSID|WTMS|VERS1
    length = 4 + len(body)
    return bytes([htyp, 0]) + struct.pack(">H", length) + body


def test_parse_offer_running() -> None:
    frame = _build_verbose_string_frame(b"TEST", b"RUNT", "Offer→Running dlt-smoke")
    msg = parse_dlt_message(frame)
    assert msg is not None
    assert msg.app_id == "TEST"
    assert msg.ctx_id == "RUNT"
    assert "Offer" in msg.text
    assert "dlt-smoke" in msg.text


def test_iter_frames_splits() -> None:
    a = _build_verbose_string_frame(b"AAAA", b"CTX1", "one")
    b = _build_verbose_string_frame(b"BBBB", b"CTX2", "two")
    buf = bytearray(a + b)
    frames = iter_dlt_frames(buf)
    assert len(frames) == 2
    assert buf == b""
    assert parse_dlt_message(frames[0]).text == "one"
    assert parse_dlt_message(frames[1]).text == "two"
