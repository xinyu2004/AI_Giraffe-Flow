"""ctypes wrapper for libgf_channel.so (middleware/bindings/gf_channel).

Looks under runtime/lib (product path). No GF_CHANNEL_LIB contract.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional


def _find_lib() -> Path:
    candidates: list[Path] = []
    # Product: GF_RUNTIME_DIR/lib or LD_LIBRARY_PATH entries
    rt = (os.environ.get("GF_RUNTIME_DIR") or "").strip()
    if rt:
        candidates.append(Path(rt) / "lib" / "libgf_channel.so")
    build = (os.environ.get("GF_BUILD_DIR") or os.environ.get("BUILD_SIL") or "").strip()
    if build:
        candidates.append(Path(build) / "runtime" / "lib" / "libgf_channel.so")
        candidates.append(
            Path(build) / "middleware" / "bindings" / "gf_channel" / "libgf_channel.so"
        )
    # Adjacent to this script when staged: share/frame_ingest → ../lib
    here = Path(__file__).resolve().parent
    candidates.append(here.parent.parent / "lib" / "libgf_channel.so")  # runtime/share→lib
    candidates.append(here.parent / "lib" / "libgf_channel.so")
    # LD_LIBRARY_PATH
    for part in (os.environ.get("LD_LIBRARY_PATH") or "").split(":"):
        if part:
            candidates.append(Path(part) / "libgf_channel.so")
    # Dev fallback: build tree next to repo layout
    try:
        repo = here.parents[5]
        candidates.append(
            repo / "middleware" / "bindings" / "gf_channel" / "libgf_channel.so"
        )
    except IndexError:
        pass
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "libgf_channel.so not found under runtime/lib "
        "(run compile_sil / stage_sil_runtime; ensure GF_RUNTIME_DIR or LD_LIBRARY_PATH)"
    )


class GfChannel:
    def __init__(self, lib: ctypes.CDLL, handle: ctypes.c_void_p, *, owner: bool):
        self._lib = lib
        self._h = handle
        self._owner = owner

    @classmethod
    def load_lib(cls) -> ctypes.CDLL:
        lib = ctypes.CDLL(str(_find_lib()))
        lib.gf_channel_plane_bytes.argtypes = [ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint32]
        lib.gf_channel_plane_bytes.restype = ctypes.c_uint32
        lib.gf_channel_format_from_name.argtypes = [ctypes.c_char_p]
        lib.gf_channel_format_from_name.restype = ctypes.c_uint16
        lib.gf_channel_create.argtypes = [
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint16,
            ctypes.c_uint32,
        ]
        lib.gf_channel_create.restype = ctypes.c_void_p
        lib.gf_channel_open.argtypes = [ctypes.c_char_p]
        lib.gf_channel_open.restype = ctypes.c_void_p
        lib.gf_channel_close.argtypes = [ctypes.c_void_p]
        lib.gf_channel_close.restype = None
        lib.gf_channel_publish.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint64,
            ctypes.c_uint64,
        ]
        lib.gf_channel_publish.restype = ctypes.c_int
        return lib

    @classmethod
    def create(
        cls,
        slot: str,
        w: int,
        h: int,
        pixel_format: str = "nv12",
        buffers: int = 2,
        *,
        lib: Optional[ctypes.CDLL] = None,
    ) -> "GfChannel":
        lib = lib or cls.load_lib()
        fmt = lib.gf_channel_format_from_name(pixel_format.encode())
        hnd = lib.gf_channel_create(slot.encode(), w, h, fmt, buffers)
        if not hnd:
            raise OSError(f"gf_channel_create failed for {slot}")
        return cls(lib, ctypes.c_void_p(hnd), owner=True)

    @classmethod
    def open(cls, slot: str, *, lib: Optional[ctypes.CDLL] = None) -> "GfChannel":
        lib = lib or cls.load_lib()
        hnd = lib.gf_channel_open(slot.encode())
        if not hnd:
            raise OSError(f"gf_channel_open failed for {slot}")
        return cls(lib, ctypes.c_void_p(hnd), owner=False)

    def close(self) -> None:
        if self._h:
            self._lib.gf_channel_close(self._h)
            self._h = ctypes.c_void_p()

    def publish(self, plane: bytes, timestamp_ns: int, seq: int = 0) -> None:
        buf = (ctypes.c_ubyte * len(plane)).from_buffer_copy(plane)
        rc = self._lib.gf_channel_publish(
            self._h, buf, len(plane), int(timestamp_ns), int(seq)
        )
        if rc != 0:
            raise OSError("gf_channel_publish failed")

    def __enter__(self) -> "GfChannel":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
