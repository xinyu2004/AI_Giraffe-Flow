"""Poll tip YUV/RGB files → foxglove.CompressedImage (same WS pipe as BEV)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from gf_gmt.adas_scenarios import _png_rgb, compressed_image_msg

TOPIC_TIP_CAM = "/gf/camera/front/tip/compressed"


def _stream_path(frame: Path) -> Path:
    return frame.with_name(frame.stem + ".stream.json")


def _meta_path(frame: Path) -> Path:
    return frame.with_name(frame.stem + ".meta.json")


def _nv12_to_rgb(yuv: bytes, w: int, h: int, *, swap_uv: bool = False) -> bytes:
    y_sz = w * h
    need = y_sz + y_sz // 2
    if len(yuv) < need:
        raise ValueError("nv12 short")
    y_plane = yuv[:y_sz]
    uv = yuv[y_sz:need]
    out = bytearray(w * h * 3)

    def clamp(v: int) -> int:
        return 0 if v < 0 else 255 if v > 255 else v

    for y in range(h):
        for x in range(w):
            yv = y_plane[y * w + x]
            ui = (y // 2) * w + (x & ~1)
            if swap_uv:
                v = uv[ui]
                u = uv[ui + 1]
            else:
                u = uv[ui]
                v = uv[ui + 1]
            c = yv - 16
            d = u - 128
            e = v - 128
            i = (y * w + x) * 3
            out[i] = clamp((298 * c + 409 * e + 128) >> 8)
            out[i + 1] = clamp((298 * c - 100 * d - 208 * e + 128) >> 8)
            out[i + 2] = clamp((298 * c + 516 * d + 128) >> 8)
    return bytes(out)


def _plane_to_rgb(fmt: str, plane: bytes, w: int, h: int) -> bytes:
    f = (fmt or "nv12").lower()
    if f == "rgb8":
        need = w * h * 3
        if len(plane) < need:
            raise ValueError("rgb short")
        return plane[:need]
    if f == "nv12":
        return _nv12_to_rgb(plane, w, h, swap_uv=False)
    if f == "nv21":
        return _nv12_to_rgb(plane, w, h, swap_uv=True)
    # yuv422/444: grayscale from Y
    n = w * h
    if len(plane) < n:
        raise ValueError("plane short")
    out = bytearray(n * 3)
    for i in range(n):
        yv = plane[i]
        out[i * 3] = yv
        out[i * 3 + 1] = yv
        out[i * 3 + 2] = yv
    return bytes(out)


def _plane_bytes(fmt: str, w: int, h: int) -> int:
    f = (fmt or "nv12").lower()
    if f in ("nv12", "nv21"):
        return w * h + (w * h) // 2
    if f == "yuv422":
        return w * h * 2
    return w * h * 3


class TipFramePublisher:
    """Filesystem tip → CompressedImage rows for Foxglove live bridge."""

    def __init__(self, frame_path: str | Path) -> None:
        self.frame_path = Path(frame_path)
        self._fmt = "nv12"
        self._w = 0
        self._h = 0
        self._negotiated = False
        self._last_seq = -1
        self._last_mtime = -1.0

    def _ensure_stream(self) -> bool:
        if self._negotiated:
            return True
        sp = _stream_path(self.frame_path)
        if not sp.is_file():
            return False
        try:
            meta = json.loads(sp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        self._fmt = str(meta.get("format") or "nv12").lower()
        self._w = int(meta.get("w") or 0)
        self._h = int(meta.get("h") or 0)
        if self._w <= 0 or self._h <= 0:
            return False
        self._negotiated = True
        print(
            f"[bridge-ws] tip stream format={self._fmt} {self._w}x{self._h} "
            f"path={self.frame_path}",
            file=sys.stderr,
            flush=True,
        )
        return True

    def poll(self) -> dict[str, Any] | None:
        if not self._ensure_stream():
            return None
        mp = _meta_path(self.frame_path)
        if not mp.is_file() or not self.frame_path.is_file():
            return None
        try:
            mtime = mp.stat().st_mtime
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        seq = int(meta.get("seq") or 0)
        if seq == self._last_seq and mtime == self._last_mtime:
            return None
        t_ns = int(meta.get("timestamp_ns") or 0)
        need = _plane_bytes(self._fmt, self._w, self._h)
        try:
            plane = self.frame_path.read_bytes()[:need]
        except OSError:
            return None
        if len(plane) < need:
            return None
        try:
            rgb = _plane_to_rgb(self._fmt, plane, self._w, self._h)
            # Downscale for Studio bandwidth if large.
            max_w = 640
            if self._w > max_w:
                rgb, pw, ph = _downscale_rgb(rgb, self._w, self._h, max_w)
            else:
                pw, ph = self._w, self._h
            png = _png_rgb(pw, ph, rgb)
        except Exception as exc:  # noqa: BLE001
            print(f"[bridge-ws] tip decode error: {exc}", file=sys.stderr, flush=True)
            return None
        self._last_seq = seq
        self._last_mtime = mtime
        return {
            "topic": TOPIC_TIP_CAM,
            "t_ns": t_ns if t_ns > 0 else 0,
            "data": compressed_image_msg(t_ns, png, frame_id="front_tip"),
        }


def _downscale_rgb(rgb: bytes, w: int, h: int, max_w: int) -> tuple[bytes, int, int]:
    scale = max_w / float(w)
    nw = max_w
    nh = max(1, int(h * scale))
    out = bytearray(nw * nh * 3)
    for y in range(nh):
        sy = min(h - 1, int(y / scale))
        for x in range(nw):
            sx = min(w - 1, int(x / scale))
            si = (sy * w + sx) * 3
            di = (y * nw + x) * 3
            out[di : di + 3] = rgb[si : si + 3]
    return bytes(out), nw, nh
