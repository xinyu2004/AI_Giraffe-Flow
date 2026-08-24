"""ctypes client for libgf_channel.so (Open/latest only — Foxglove camera reader)."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Optional

_LIB: ctypes.CDLL | None = None


def _find_lib() -> Path:
    candidates: list[Path] = []
    rt = (os.environ.get("GF_RUNTIME_DIR") or "").strip()
    if rt:
        candidates.append(Path(rt) / "lib" / "libgf_channel.so")
    build = (os.environ.get("GF_BUILD_DIR") or "").strip()
    if build:
        candidates.append(Path(build) / "runtime" / "lib" / "libgf_channel.so")
        candidates.append(Path(build) / "lib" / "libgf_channel.so")
    for part in (os.environ.get("LD_LIBRARY_PATH") or "").split(":"):
        if part:
            candidates.append(Path(part) / "libgf_channel.so")
    here = Path(__file__).resolve()
    # tools/gmt/src/gf_gmt → repo root ≈ parents[3]
    try:
        repo = here.parents[3]
        candidates.append(
            repo / "middleware" / "bindings" / "gf_channel" / "libgf_channel.so"
        )
        candidates.append(
            repo
            / "projects"
            / "afc"
            / "build-sil"
            / "runtime"
            / "lib"
            / "libgf_channel.so"
        )
    except IndexError:
        pass
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "libgf_channel.so not found (set GF_RUNTIME_DIR / LD_LIBRARY_PATH after stage)"
    )


def _load_lib() -> ctypes.CDLL:
    """Process-wide CDLL cache — never CDLL() per open attempt (FD leak → EMFILE)."""
    global _LIB
    if _LIB is not None:
        return _LIB
    lib = ctypes.CDLL(str(_find_lib()))
    lib.gf_channel_open.argtypes = [ctypes.c_char_p]
    lib.gf_channel_open.restype = ctypes.c_void_p
    lib.gf_channel_close.argtypes = [ctypes.c_void_p]
    lib.gf_channel_close.restype = None
    lib.gf_channel_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    lib.gf_channel_info.restype = ctypes.c_int
    lib.gf_channel_format_name.argtypes = [ctypes.c_uint16]
    lib.gf_channel_format_name.restype = ctypes.c_char_p
    lib.gf_channel_latest.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint16),
    ]
    lib.gf_channel_latest.restype = ctypes.c_int
    _LIB = lib
    return lib


class GfChannelReader:
    """Read-only Open + latest for a camera/channel slot."""

    def __init__(self, slot: str) -> None:
        self.slot = slot
        self._lib = _load_lib()
        self._h = ctypes.c_void_p()
        hnd = self._lib.gf_channel_open(slot.encode())
        if not hnd:
            raise OSError(f"gf_channel_open failed for {slot}")
        self._h = ctypes.c_void_p(hnd)
        self._plane = bytearray()
        self._last_seq = ctypes.c_uint64(0)
        self._fmt = "nv12"
        self._w = 0
        self._h_dim = 0
        try:
            self._refresh_info()
        except Exception:
            self.close()
            raise

    def _refresh_info(self) -> None:
        w = ctypes.c_uint32()
        h = ctypes.c_uint32()
        fmt = ctypes.c_uint16()
        plane_bytes = ctypes.c_uint32()
        buffers = ctypes.c_uint32()
        if self._lib.gf_channel_info(
            self._h, ctypes.byref(w), ctypes.byref(h), ctypes.byref(fmt),
            ctypes.byref(plane_bytes), ctypes.byref(buffers),
        ) != 0:
            raise OSError(f"gf_channel_info failed for {self.slot}")
        self._w = int(w.value)
        self._h_dim = int(h.value)
        name = self._lib.gf_channel_format_name(fmt.value)
        self._fmt = (name.decode() if name else "nv12").lower()
        need = int(plane_bytes.value) or (self._w * self._h_dim * 3)
        if len(self._plane) < need:
            self._plane = bytearray(need)

    @property
    def format(self) -> str:
        return self._fmt

    @property
    def width(self) -> int:
        return self._w

    @property
    def height(self) -> int:
        return self._h_dim

    def latest(self) -> Optional[tuple[bytes, int, int]]:
        """Return (plane, timestamp_ns, seq) if a newer frame is available."""
        if not self._h:
            return None
        plane_out = ctypes.c_uint32()
        ts = ctypes.c_uint64()
        w = ctypes.c_uint32()
        h = ctypes.c_uint32()
        fmt = ctypes.c_uint16()
        buf = (ctypes.c_ubyte * len(self._plane)).from_buffer(self._plane)
        got = self._lib.gf_channel_latest(
            self._h,
            buf,
            len(self._plane),
            ctypes.byref(plane_out),
            ctypes.byref(self._last_seq),
            ctypes.byref(ts),
            ctypes.byref(w),
            ctypes.byref(h),
            ctypes.byref(fmt),
        )
        if got != 1:
            return None
        self._w = int(w.value) or self._w
        self._h_dim = int(h.value) or self._h_dim
        name = self._lib.gf_channel_format_name(fmt.value)
        if name:
            self._fmt = name.decode().lower()
        n = int(plane_out.value)
        return (bytes(self._plane[:n]), int(ts.value), int(self._last_seq.value))

    def reset_seq_cursor(self) -> None:
        """Re-deliver the current shm frame on next latest() (subscribe catch-up)."""
        self._last_seq = ctypes.c_uint64(0)

    def close(self) -> None:
        if self._h:
            self._lib.gf_channel_close(self._h)
            self._h = ctypes.c_void_p()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # noqa: BLE001
            pass
