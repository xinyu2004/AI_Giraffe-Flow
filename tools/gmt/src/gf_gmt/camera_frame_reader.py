"""Poll camera frames (GfChannel shm or file bypass) → foxglove.CompressedImage."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from gf_gmt.adas_scenarios import TOPIC_DRIVING_CAM, _png_rgb, compressed_image_msg

DEFAULT_CAMERA_SLOT = "gf.channel.front"


def _stream_path(frame: Path) -> Path:
    return frame.with_name(frame.stem + ".stream.json")


def _meta_path(frame: Path) -> Path:
    return frame.with_name(frame.stem + ".meta.json")


def _nv12_to_rgb(yuv: bytes, w: int, h: int, *, swap_uv: bool = False) -> bytes:
    """Full-resolution NV12→RGB (tests / small frames). Prefer _nv12_preview_rgb for bridge."""
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


def _nv12_preview_rgb(
    yuv: bytes, w: int, h: int, *, max_w: int = 320, swap_uv: bool = False
) -> tuple[bytes, int, int]:
    """Subsample then convert — Foxglove preview must stay real-time (pure Python)."""
    y_sz = w * h
    need = y_sz + y_sz // 2
    if len(yuv) < need:
        raise ValueError("nv12 short")
    y_plane = yuv[:y_sz]
    uv = yuv[y_sz:need]
    step = max(1, (w + max_w - 1) // max_w)
    nw = max(1, w // step)
    nh = max(1, h // step)
    out = bytearray(nw * nh * 3)

    def clamp(v: int) -> int:
        return 0 if v < 0 else 255 if v > 255 else v

    for oy in range(nh):
        sy = min(h - 1, oy * step)
        for ox in range(nw):
            sx = min(w - 1, ox * step)
            yv = y_plane[sy * w + sx]
            ui = (sy // 2) * w + (sx & ~1)
            if swap_uv:
                v = uv[ui]
                u = uv[ui + 1]
            else:
                u = uv[ui]
                v = uv[ui + 1]
            c = yv - 16
            d = u - 128
            e = v - 128
            i = (oy * nw + ox) * 3
            out[i] = clamp((298 * c + 409 * e + 128) >> 8)
            out[i + 1] = clamp((298 * c - 100 * d - 208 * e + 128) >> 8)
            out[i + 2] = clamp((298 * c + 516 * d + 128) >> 8)
    return bytes(out), nw, nh


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


def _encode_camera_row(fmt: str, plane: bytes, w: int, h: int, t_ns: int) -> dict[str, Any] | None:
    try:
        f = (fmt or "nv12").lower()
        if f in ("nv12", "nv21") and w * h > 160 * 120:
            rgb, pw, ph = _nv12_preview_rgb(
                plane, w, h, max_w=320, swap_uv=(f == "nv21")
            )
        else:
            rgb = _plane_to_rgb(fmt, plane, w, h)
            max_w = 640
            if w > max_w:
                rgb, pw, ph = _downscale_rgb(rgb, w, h, max_w)
            else:
                pw, ph = w, h
        png = _png_rgb(pw, ph, rgb)
    except Exception as exc:  # noqa: BLE001
        print(f"[bridge-ws] camera decode error: {exc}", file=sys.stderr, flush=True)
        return None
    # Foxglove Image panels often ignore / pile up at t=0 — use wall clock if writer has no ts.
    if t_ns <= 0:
        import time

        t_ns = time.time_ns()
    return {
        "topic": TOPIC_DRIVING_CAM,
        "t_ns": t_ns,
        "data": compressed_image_msg(t_ns, png, frame_id="driving_front"),
    }


class CameraFramePublisher:
    """GfChannel shm (preferred) or filesystem camera → CompressedImage for Foxglove."""

    def __init__(
        self,
        frame_path: str | Path | None = None,
        *,
        camera_slot: str | None = None,
    ) -> None:
        self.camera_slot = (camera_slot or "").strip() or None
        self.frame_path = Path(frame_path) if frame_path else None
        if not self.camera_slot and self.frame_path is None:
            raise ValueError("CameraFramePublisher needs camera_slot or frame_path")
        self._fmt = "nv12"
        self._w = 0
        self._h = 0
        self._negotiated = False
        self._last_seq = -1
        self._last_mtime = -1.0
        self._shm = None
        self._shm_fail_logged = False
        self._shm_ok_logged = False
        self._shm_next_try = 0.0  # monotonic; backoff while writer not ready
        self._wait_logged_at = 0.0
        self._wait_open_logged = False  # "open but no seq" — once only
        self._frames_ok = 0
        self._last_frame_mono = 0.0
        self.last_seq_pub = -1
        self.last_digest = 0  # cheap content fingerprint for heartbeats

    def request_resend(self) -> None:
        """Allow re-reading the current shm frame (e.g. after Studio subscribe)."""
        self._last_seq = -1
        if self._shm is not None:
            self._shm.reset_seq_cursor()

    def _ensure_shm(self) -> bool:
        if self._shm is not None:
            return True
        assert self.camera_slot
        import time

        now = time.monotonic()
        if now < self._shm_next_try:
            return False
        try:
            from gf_gmt.gf_channel_client import GfChannelReader

            self._shm = GfChannelReader(self.camera_slot)
        except Exception as exc:  # noqa: BLE001
            # Channel may appear after ingest starts — retry with backoff (not every poll).
            self._shm_next_try = now + 1.0
            if not self._shm_fail_logged:
                print(
                    f"[bridge-ws] camera shm open pending ({self.camera_slot}): {exc} "
                    f"(retry ≤1 Hz until ready)",
                    file=sys.stderr,
                    flush=True,
                )
                self._shm_fail_logged = True
            return False
        self._fmt = self._shm.format
        self._w = self._shm.width
        self._h = self._shm.height
        self._negotiated = True
        self._shm_next_try = 0.0
        if not self._shm_ok_logged:
            print(
                f"[bridge-ws] camera stream format={self._fmt} {self._w}x{self._h} "
                f"camera_slot={self.camera_slot} (GfChannel)",
                file=sys.stderr,
                flush=True,
            )
            self._shm_ok_logged = True
        return True

    def _ensure_stream_file(self) -> bool:
        if self._negotiated:
            return True
        assert self.frame_path is not None
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
            f"[bridge-ws] camera stream format={self._fmt} {self._w}x{self._h} "
            f"path={self.frame_path} (file bypass)",
            file=sys.stderr,
            flush=True,
        )
        return True

    def poll(self) -> dict[str, Any] | None:
        if self.camera_slot:
            return self._poll_shm()
        return self._poll_file()

    def _poll_shm(self) -> dict[str, Any] | None:
        if not self._ensure_shm():
            return None
        assert self._shm is not None
        got = self._shm.latest()
        if got is None:
            import time

            now = time.monotonic()
            if self._frames_ok == 0 and not self._wait_open_logged:
                self._wait_open_logged = True
                self._wait_logged_at = now
                print(
                    f"[bridge-ws] camera waiting: slot={self.camera_slot} open but no seq yet "
                    f"(no writer publish yet — if GF_FRAME_SOURCE=carla, bridge may still be "
                    f"connecting / waiting for role_name=hero in UE)",
                    file=sys.stderr,
                    flush=True,
                )
            elif (
                self._frames_ok > 0
                and self._last_frame_mono > 0
                and now - self._last_frame_mono >= 3.0
                and now - self._wait_logged_at >= 3.0
            ):
                self._wait_logged_at = now
                print(
                    f"[bridge-ws] camera stalled ~{now - self._last_frame_mono:.0f}s "
                    f"(had frames; often scenario hero/camera re-attach — check carla_bridge "
                    f"for ego_lost / waiting for scenario hero)",
                    file=sys.stderr,
                    flush=True,
                )
            return None
        plane, t_ns, seq = got
        if seq == self._last_seq:
            return None
        row = _encode_camera_row(self._shm.format, plane, self._shm.width, self._shm.height, t_ns)
        if row is None:
            return None
        self._last_seq = seq
        self._frames_ok += 1
        self.last_seq_pub = int(seq)
        # Pixel-only fingerprint (do NOT fold seq in — seq always moves).
        n = len(plane)
        if n >= 3:
            self.last_digest = plane[0] | (plane[n // 2] << 8) | (plane[n - 1] << 16)
        else:
            self.last_digest = plane[0] if n else 0
        import time

        self._last_frame_mono = time.monotonic()
        return row

    def _poll_file(self) -> dict[str, Any] | None:
        if not self._ensure_stream_file():
            return None
        assert self.frame_path is not None
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
        row = _encode_camera_row(self._fmt, plane, self._w, self._h, t_ns)
        if row is None:
            return None
        self._last_seq = seq
        self._last_mtime = mtime
        return row
