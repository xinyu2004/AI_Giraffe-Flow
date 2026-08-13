"""RGB ↔ configurable YUV planar helpers for CARLA tip bridge (stdlib only)."""

from __future__ import annotations


def plane_size(fmt: str, w: int, h: int) -> int:
    f = (fmt or "nv12").lower()
    if f in ("nv12", "nv21"):
        return w * h + (w * h) // 2
    if f == "yuv422":
        return w * h * 2
    if f == "yuv444":
        return w * h * 3
    if f == "rgb8":
        return w * h * 3
    raise ValueError(f"unsupported pixel_format={fmt}")


def rgb_to_yuv(fmt: str, rgb: bytes, w: int, h: int) -> bytes:
    f = (fmt or "nv12").lower()
    if f == "rgb8":
        need = w * h * 3
        if len(rgb) < need:
            raise ValueError("rgb too short")
        return rgb[:need]
    if f in ("nv12", "nv21"):
        return rgb_to_nv12(rgb, w, h, swap_uv=(f == "nv21"))
    if f == "yuv422":
        return rgb_to_yuv422(rgb, w, h)
    if f == "yuv444":
        return rgb_to_yuv444(rgb, w, h)
    raise ValueError(f"unsupported pixel_format={fmt}")


def yuv_to_rgb(fmt: str, yuv: bytes, w: int, h: int) -> bytes:
    f = (fmt or "nv12").lower()
    if f == "rgb8":
        need = w * h * 3
        if len(yuv) < need:
            raise ValueError("rgb too short")
        return yuv[:need]
    if f in ("nv12", "nv21"):
        return nv12_to_rgb(yuv, w, h, swap_uv=(f == "nv21"))
    if f == "yuv422":
        return yuv422_to_rgb(yuv, w, h)
    if f == "yuv444":
        return yuv444_to_rgb(yuv, w, h)
    raise ValueError(f"unsupported pixel_format={fmt}")


def _clamp(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def rgb_to_nv12(rgb: bytes, w: int, h: int, *, swap_uv: bool = False) -> bytes:
    need = w * h * 3
    if len(rgb) < need:
        raise ValueError(f"rgb too short: {len(rgb)} < {need}")
    y_plane = bytearray(w * h)
    uv = bytearray((w * h) // 2)
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 3
            r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
            yv = ((66 * r + 129 * g + 25 * b + 128) >> 8) + 16
            y_plane[y * w + x] = _clamp(yv)
            if (y & 1) == 0 and (x & 1) == 0:
                u = ((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128
                v = ((112 * r - 94 * g - 18 * b + 128) >> 8) + 128
                ui = (y // 2) * w + x
                if swap_uv:
                    uv[ui] = _clamp(v)
                    uv[ui + 1] = _clamp(u)
                else:
                    uv[ui] = _clamp(u)
                    uv[ui + 1] = _clamp(v)
    return bytes(y_plane) + bytes(uv)


def nv12_to_rgb(yuv: bytes, w: int, h: int, *, swap_uv: bool = False) -> bytes:
    y_sz = w * h
    need = y_sz + y_sz // 2
    if len(yuv) < need:
        raise ValueError(f"nv12 too short: {len(yuv)} < {need}")
    out = bytearray(w * h * 3)
    y_plane = yuv[:y_sz]
    uv = yuv[y_sz:need]
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
            r = _clamp((298 * c + 409 * e + 128) >> 8)
            g = _clamp((298 * c - 100 * d - 208 * e + 128) >> 8)
            b = _clamp((298 * c + 516 * d + 128) >> 8)
            i = (y * w + x) * 3
            out[i] = r
            out[i + 1] = g
            out[i + 2] = b
    return bytes(out)


def rgb_to_yuv422(rgb: bytes, w: int, h: int) -> bytes:
    need = w * h * 3
    if len(rgb) < need:
        raise ValueError("rgb too short")
    out = bytearray(w * h * 2)
    for y in range(h):
        for x in range(0, w, 2):
            i0 = (y * w + x) * 3
            i1 = (y * w + min(x + 1, w - 1)) * 3
            r0, g0, b0 = rgb[i0], rgb[i0 + 1], rgb[i0 + 2]
            r1, g1, b1 = rgb[i1], rgb[i1 + 1], rgb[i1 + 2]
            y0 = _clamp(((66 * r0 + 129 * g0 + 25 * b0 + 128) >> 8) + 16)
            y1 = _clamp(((66 * r1 + 129 * g1 + 25 * b1 + 128) >> 8) + 16)
            u = _clamp(((-38 * r0 - 74 * g0 + 112 * b0 + 128) >> 8) + 128)
            v = _clamp(((112 * r0 - 94 * g0 - 18 * b0 + 128) >> 8) + 128)
            o = (y * w + x) * 2
            out[o] = y0
            out[o + 1] = u
            out[o + 2] = y1
            out[o + 3] = v
    return bytes(out)


def yuv422_to_rgb(yuv: bytes, w: int, h: int) -> bytes:
    need = w * h * 2
    if len(yuv) < need:
        raise ValueError("yuv422 too short")
    out = bytearray(w * h * 3)
    for y in range(h):
        for x in range(0, w, 2):
            o = (y * w + x) * 2
            y0, u, y1, v = yuv[o], yuv[o + 1], yuv[o + 2], yuv[o + 3]
            for xi, yv in ((x, y0), (min(x + 1, w - 1), y1)):
                c = yv - 16
                d = u - 128
                e = v - 128
                r = _clamp((298 * c + 409 * e + 128) >> 8)
                g = _clamp((298 * c - 100 * d - 208 * e + 128) >> 8)
                b = _clamp((298 * c + 516 * d + 128) >> 8)
                i = (y * w + xi) * 3
                out[i] = r
                out[i + 1] = g
                out[i + 2] = b
    return bytes(out)


def rgb_to_yuv444(rgb: bytes, w: int, h: int) -> bytes:
    need = w * h * 3
    if len(rgb) < need:
        raise ValueError("rgb too short")
    y = bytearray(w * h)
    u = bytearray(w * h)
    v = bytearray(w * h)
    for i in range(w * h):
        r, g, b = rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]
        y[i] = _clamp(((66 * r + 129 * g + 25 * b + 128) >> 8) + 16)
        u[i] = _clamp(((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128)
        v[i] = _clamp(((112 * r - 94 * g - 18 * b + 128) >> 8) + 128)
    return bytes(y) + bytes(u) + bytes(v)


def yuv444_to_rgb(yuv: bytes, w: int, h: int) -> bytes:
    n = w * h
    if len(yuv) < n * 3:
        raise ValueError("yuv444 too short")
    y, u, v = yuv[:n], yuv[n : 2 * n], yuv[2 * n : 3 * n]
    out = bytearray(n * 3)
    for i in range(n):
        c = y[i] - 16
        d = u[i] - 128
        e = v[i] - 128
        out[i * 3] = _clamp((298 * c + 409 * e + 128) >> 8)
        out[i * 3 + 1] = _clamp((298 * c - 100 * d - 208 * e + 128) >> 8)
        out[i * 3 + 2] = _clamp((298 * c + 516 * d + 128) >> 8)
    return bytes(out)


def synth_rgb(w: int, h: int, seq: int) -> bytes:
    out = bytearray(w * h * 3)
    phase = seq & 0xFF
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 3
            out[i] = (x + phase) & 0xFF
            out[i + 1] = (y + phase // 2) & 0xFF
            out[i + 2] = (x + y + phase) & 0xFF
    return bytes(out)
