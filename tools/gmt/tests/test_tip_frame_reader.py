"""Tip YUV → CompressedImage helper."""

from __future__ import annotations

import json
from pathlib import Path

from gf_gmt.tip_frame_reader import TOPIC_TIP_CAM, TipFramePublisher


def _write_nv12_tip(tmp: Path, *, w: int = 8, h: int = 8, seq: int = 1) -> Path:
    frame = tmp / "gf_front.yuv"
    # Minimal NV12: Y=128, UV=128
    y = bytes([128] * (w * h))
    uv = bytes([128] * ((w * h) // 2))
    frame.write_bytes(y + uv)
    (tmp / "gf_front.stream.json").write_text(
        json.dumps({"format": "nv12", "w": w, "h": h}), encoding="utf-8"
    )
    (tmp / "gf_front.meta.json").write_text(
        json.dumps({"timestamp_ns": 123, "seq": seq}), encoding="utf-8"
    )
    return frame


def test_tip_frame_publisher_polls_nv12(tmp_path: Path) -> None:
    frame = _write_nv12_tip(tmp_path)
    tip = TipFramePublisher(frame)
    row = tip.poll()
    assert row is not None
    assert row["topic"] == TOPIC_TIP_CAM
    assert row["data"]["format"] == "png"
    assert tip.poll() is None  # same seq
    # New seq
    (tmp_path / "gf_front.meta.json").write_text(
        json.dumps({"timestamp_ns": 456, "seq": 2}), encoding="utf-8"
    )
    row2 = tip.poll()
    assert row2 is not None
    assert row2["t_ns"] == 456


def test_tip_frame_publisher_requires_source() -> None:
    try:
        TipFramePublisher()
        assert False, "expected ValueError"
    except ValueError:
        pass
