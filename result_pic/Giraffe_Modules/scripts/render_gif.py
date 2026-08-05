#!/usr/bin/env python3
"""Render Giraffe_Modules.gif + .svg (middleware collaboration).

Focus: on-board sm / phm / exec / com / collector / diag / ucm …
NOT Giraffe_Flow (CARLA / Foxglove / GMT).

Usage:
  python3 render_gif.py           # ZH → Giraffe_Modules.gif/.svg
  python3 render_gif.py --en      # also EN
"""
from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
W = 1100
FRAMES = 16
CX = W // 2


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    def pad(self, l: float, t: float, r: float, b: float) -> Box:
        return Box(
            self.x0 + self.w * l,
            self.y0 + self.h * t,
            self.x1 - self.w * r,
            self.y1 - self.h * b,
        )

    def split_v(self, *weights: float) -> list[Box]:
        total = sum(weights) or 1.0
        y = self.y0
        out: list[Box] = []
        for i, wt in enumerate(weights):
            nh = self.h * (wt / total)
            y1 = self.y1 if i == len(weights) - 1 else y + nh
            out.append(Box(self.x0, y, self.x1, y1))
            y = y1
        return out

    def split_h(self, *weights: float) -> list[Box]:
        total = sum(weights) or 1.0
        x = self.x0
        out: list[Box] = []
        for i, wt in enumerate(weights):
            nw = self.w * (wt / total)
            x1 = self.x1 if i == len(weights) - 1 else x + nw
            out.append(Box(x, self.y0, x1, self.y1))
            x = x1
        return out

    def as_ints(self) -> list[int]:
        return [int(round(self.x0)), int(round(self.y0)), int(round(self.x1)), int(round(self.y1))]


def font(size: int, *, weight: str = "regular") -> ImageFont.ImageFont:
    cjk = {
        "bold": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "medium": "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "regular": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    }.get(weight, "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    try:
        return ImageFont.truetype(cjk, size, index=2)
    except OSError:
        pass
    boldish = weight in ("bold", "medium")
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if boldish else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def vcenter_text(
    d: ImageDraw.ImageDraw,
    text: str,
    box: Box,
    *,
    fnt: ImageFont.ImageFont,
    fill: str,
    max_w: float | None = None,
) -> None:
    s = text
    mw = max_w if max_w is not None else box.w * 0.92
    while s and d.textlength(s, font=fnt) > mw:
        s = s[:-1]
    if s != text and len(s) > 1:
        s = s[:-1] + "…"
    cx, cy = box.cx, box.cy
    try:
        l, t, r, b = d.textbbox((0, 0), s, font=fnt)
        d.text((cx - (l + r) / 2, cy - (t + b) / 2), s, fill=fill, font=fnt)
    except Exception:
        tw = d.textlength(s, font=fnt)
        d.text((cx - tw / 2, cy - 6), s, fill=fill, font=fnt)


def chip_size(
    d: ImageDraw.ImageDraw,
    title: str,
    sub: str,
    *,
    fnt_t: ImageFont.ImageFont,
    fnt_s: ImageFont.ImageFont,
    height: float,
    min_w: float,
    max_w: float,
    pad_x: float = 28.0,
) -> tuple[float, float]:
    tw = d.textlength(title, font=fnt_t)
    if sub:
        tw = max(tw, d.textlength(sub, font=fnt_s))
    return min(max_w, max(min_w, tw + pad_x)), height


def place_row(
    band: Box,
    widths: list[float],
    *,
    height: float,
    gap: float = 14.0,
) -> list[Box]:
    """Center a row of fixed-size chips in band."""
    total = sum(widths) + gap * max(0, len(widths) - 1)
    x = band.cx - total / 2
    cy = band.cy
    half = height / 2
    out: list[Box] = []
    for w in widths:
        out.append(Box(x, cy - half, x + w, cy + half))
        x += w + gap
    return out


def chip(
    d: ImageDraw.ImageDraw,
    box: Box,
    title: str,
    sub: str,
    *,
    fill: str,
    outline: str,
    title_fill: str,
    fnt_t: ImageFont.ImageFont,
    fnt_s: ImageFont.ImageFont,
    sub_fill: str = "#90a4ae",
) -> Box:
    d.rounded_rectangle(box.as_ints(), radius=7, fill=fill, outline=outline, width=2)
    cx, cy = box.cx, box.cy
    if sub:
        # Pixel stack — keeps title/sub visually filling the chip.
        try:
            _, tt, _, tb = d.textbbox((0, 0), title, font=fnt_t)
            _, st, _, sb = d.textbbox((0, 0), sub, font=fnt_s)
        except Exception:
            tt = st = 0
            tb, sb = 18, 14
        th, sh = tb - tt, sb - st
        gap = 2.0
        block = th + gap + sh
        y0 = cy - block / 2
        tw = d.textlength(title, font=fnt_t)
        sw = d.textlength(sub, font=fnt_s)
        d.text((cx - tw / 2, y0 - tt), title, fill=title_fill, font=fnt_t)
        d.text((cx - sw / 2, y0 + th + gap - st), sub, fill=sub_fill, font=fnt_s)
    else:
        vcenter_text(d, title, box, fnt=fnt_t, fill=title_fill)
    return box


def draw_vline_flow(
    d: ImageDraw.ImageDraw,
    x: float,
    y0: float,
    y1: float,
    color: str,
    phase: float,
    *,
    width: int = 3,
    n_arrows: int = 3,
    pad: float = 2.0,
) -> None:
    """Vertical flow on the open segment (y0, y1); chevrons stay strictly inside."""
    if abs(y1 - y0) < 12:
        return
    step = 1 if y1 >= y0 else -1
    a = y0 + pad * step
    b = y1 - pad * step
    if (b - a) * step <= 0:
        return
    d.line([(x, a), (x, b)], fill=color, width=width)
    length = abs(b - a)
    tip_h = max(8, min(11, int(length // 5)))
    half_w = max(5, tip_h // 2 + 1)
    lo, hi = (a, b) if a <= b else (b, a)

    def chevron(tip_y: float) -> None:
        base_y = tip_y - tip_h * step
        if not (lo <= tip_y <= hi and lo <= base_y <= hi):
            return
        d.polygon([(x, tip_y), (x - half_w, base_y), (x + half_w, base_y)], fill=color)

    # Traveling chevrons only (no static tip).
    n = max(2, min(n_arrows, max(2, int(length // 18))))
    spacing = length / n
    for i in range(n):
        pos = (phase * spacing + i * spacing) % length
        chevron(a + pos * step)


def draw_h_flow(
    d: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    cy: float,
    color: str,
    phase: float,
    *,
    width: int = 3,
    n_arrows: int = 3,
    pad: float = 2.0,
) -> None:
    """Horizontal flow on the open segment (x0, x1); chevrons stay strictly inside."""
    if x1 - x0 < 14:
        return
    a = x0 + pad
    b = x1 - pad
    if b <= a:
        return
    d.line([(a, cy), (b, cy)], fill=color, width=width)
    length = b - a
    tip_h = max(8, min(11, int(length // 4)))
    half_w = max(5, tip_h // 2 + 1)

    def chevron(x: float) -> None:
        # Tip at x+tip_h, base at x — whole triangle must stay in [a, b]
        if x < a or x + tip_h > b:
            return
        d.polygon([(x + tip_h, cy), (x, cy - half_w), (x, cy + half_w)], fill=color)

    # Traveling chevrons only (no static tip).
    n = max(2, min(n_arrows, max(2, int(length // 18))))
    spacing = length / n
    for i in range(n):
        pos = (phase * spacing + i * spacing) % length
        chevron(a + pos)


ZH = {
    "title": "Giraffe Modules",
    "subtitle": "中间件如何起来、如何协作（板内 · sm / phm / exec / com …）",
    "init": "systemd/init",
    "init_sub": "系统侧 · 非 Giraffe",
    "host": "HOST",
    "dlt": "dlt-daemon",
    "dlt_sub": "按需 · log.yaml sinks",
    "roudi": "RouDi",
    "roudi_sub": "iceoryx",
    "em": "EM",
    "em_sub": "gf_em_daemon",
    "spawn": "OSAL Spawn",
    "apps": "SOA apps",
    "apps_sub": "gateway · sensing · …",
    "bringup": "runtime bring-up",
    "ring_title": "进程内中间件环",
    "exec": "exec",
    "exec_sub": "Client",
    "phm": "phm",
    "phm_sub": "Alive / Deadline",
    "sm": "sm",
    "sm_sub": "Off / Running / Updating",
    "collector": "collector",
    "collector_sub": "DEM-lite",
    "per": "per",
    "per_sub": "persist",
    "com": "com",
    "com_sub": "Proxy / Skeleton",
    "bindings": "bindings",
    "bindings_sub": "iceoryx · SOME/IP · DDS",
    "diag": "diag",
    "diag_sub": "DoIP / UDS",
    "ucm": "ucm",
    "ucm_sub": "OTA",
    "log_dlt": "log → DLT",
    "tsync": "tsync",
    "osal": "OSAL",
    "alive": "Offer / Alive",
    "fault": "NotifyFault",
    "ensure": "EnsureGroup",
    "persist": "persist",
    "updating": "Updating",
    "fusa": "FuSa 证据挂在 exec / phm / sm / collector 的真实行为上",
}

EN = {
    **ZH,
    "subtitle": "How middleware boots & collaborates (on-board · sm / phm / exec / com …)",
    "init": "systemd/init",
    "init_sub": "OS · not Giraffe",
    "host": "HOST",
    "dlt_sub": "on demand · log.yaml sinks",
    "apps": "SOA apps",
    "apps_sub": "gateway · sensing · …",
    "bringup": "runtime bring-up",
    "ring_title": "In-process middleware ring",
    "phm_sub": "Alive / Deadline",
    "sm_sub": "Off / Running / Updating",
    "collector_sub": "DEM-lite",
    "per_sub": "persist",
    "com_sub": "Proxy / Skeleton",
    "bindings_sub": "iceoryx · SOME/IP · DDS",
    "diag_sub": "DoIP / UDS",
    "ucm_sub": "OTA",
    "log_dlt": "log → DLT",
    "alive": "Offer / Alive",
    "fault": "NotifyFault",
    "ensure": "EnsureGroup",
    "persist": "persist",
    "updating": "Updating",
    "fusa": "FuSa evidence attaches to real exec / phm / sm / collector behavior",
}


def label_between_h(
    d: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    cy: float,
    text: str,
    *,
    fnt: ImageFont.ImageFont,
    fill: str,
    dy: float = -22,
) -> None:
    """Put edge label in the middle of a horizontal gap, above the flow line."""
    tw = d.textlength(text, font=fnt)
    d.text(((x0 + x1) / 2 - tw / 2, cy + dy), text, fill=fill, font=fnt)


def label_beside_v(
    d: ImageDraw.ImageDraw,
    x: float,
    y0: float,
    y1: float,
    text: str,
    *,
    fnt: ImageFont.ImageFont,
    fill: str,
    side: str = "right",
) -> None:
    tw = d.textlength(text, font=fnt)
    mid = (y0 + y1) / 2 - 8
    if side == "right":
        d.text((x + 8, mid), text, fill=fill, font=fnt)
    else:
        d.text((x - 8 - tw, mid), text, fill=fill, font=fnt)


def draw_frame(texts: dict, phase: float) -> Image.Image:
    # Probe fonts on a throwaway image, then size canvas to fit the stack.
    probe = Image.new("RGB", (8, 8), "#000000")
    d0 = ImageDraw.Draw(probe)
    f22b = font(22, weight="bold")
    f20b = font(20, weight="bold")
    f16 = font(16, weight="medium")
    f15 = font(15, weight="medium")
    f15b = font(15, weight="bold")

    CHIP_H = 52
    def gap_for(label: str, *, floor: float = 72.0) -> float:
        return max(floor, d0.textlength(label, font=f15) + 40)

    g_alive = gap_for(texts["alive"], floor=130)
    g_persist = gap_for(texts["persist"], floor=88)
    g_com = gap_for("Proxy", floor=72)
    g_diag = gap_for("DoIP", floor=80)
    g_base = 48.0
    ROW_GAP = 52.0

    def sized(title: str, sub: str, *, pad_x: float = 30.0) -> float:
        w, _ = chip_size(
            d0, title, sub, fnt_t=f20b, fnt_s=f15, height=CHIP_H,
            min_w=0, max_w=560, pad_x=pad_x,
        )
        return w

    w_exec = sized(texts["exec"], texts["exec_sub"])
    w_phm = sized(texts["phm"], texts["phm_sub"])
    w_sm = sized(texts["sm"], texts["sm_sub"], pad_x=36)
    w_col = sized(texts["collector"], texts["collector_sub"])
    w_per = sized(texts["per"], texts["per_sub"])
    w_com = sized(texts["com"], texts["com_sub"])
    w_bind = sized(texts["bindings"], texts["bindings_sub"], pad_x=34)
    w_diag = sized(texts["diag"], texts["diag_sub"])
    w_ucm = sized(texts["ucm"], texts["ucm_sub"])
    # Ring base: single-line chips, same visual weight
    w_log = sized(texts["log_dlt"], "", pad_x=30)
    w_tsync = sized(texts["tsync"], "", pad_x=28)
    w_osal = sized(texts["osal"], "", pad_x=30)

    w_sm_span = max(w_sm, w_exec + g_alive + w_phm)
    upd_tw = d0.textlength(texts["updating"], font=f15)
    side_pad = upd_tw + 56

    row_ws = [
        w_sm_span,
        w_col + g_persist + w_per,
        w_com + g_com + w_bind,
        w_diag + g_diag + w_ucm,
        w_log + g_base + w_tsync + g_base + w_osal,
    ]
    content_w = max(row_ws)
    fusa_w = d0.textlength(texts["fusa"], font=f15) + 32
    ring_title_w = d0.textlength(texts["ring_title"], font=f20b) + 40
    ring_w = min(W * 0.94, max(content_w + side_pad, fusa_w, ring_title_w) + 48)

    bh = 50.0
    vgap_boot = 48.0
    bw = max(
        sized(texts["dlt"], texts["dlt_sub"], pad_x=34),
        sized(texts["roudi"], texts["roudi_sub"]),
        sized(texts["em"], texts["em_sub"]),
        sized(texts["apps"], texts["apps_sub"], pad_x=34),
    )
    # HOST: dlt + RouDi + EM; then SOA apps
    boot_h = bh * 4 + vgap_boot * 3
    link_h = 28.0
    ring_hdr = 34.0
    ring_foot = 26.0
    n_rows = 6
    ring_body_h = 16 + CHIP_H * n_rows + ROW_GAP * (n_rows - 1)
    ring_h = ring_hdr + ring_body_h + ring_foot + 12
    hdr_h = 72.0
    bottom_pad = 28.0
    H = int(hdr_h + boot_h + link_h + ring_h + bottom_pad + 24)
    img = Image.new("RGB", (W, H), "#fafbfc")
    d = ImageDraw.Draw(img)

    page = Box(0, 0, W, H).pad(0.02, 0.012, 0.02, 0.014)
    hdr = Box(page.x0, page.y0, page.x1, page.y0 + hdr_h)
    body = Box(page.x0, hdr.y1, page.x1, page.y1)
    ht, hs = hdr.split_v(0.55, 0.45)
    vcenter_text(d, texts["title"], ht, fnt=f22b, fill="#1b5e20")
    vcenter_text(d, texts["subtitle"], hs, fnt=f16, fill="#546e7a")

    y = body.y0 + 8
    # Room for OS init chip (same guardian language) + HOST frame on the left.
    cx = body.cx + 72

    def boot_box(yy: float) -> Box:
        return Box(cx - bw / 2, yy, cx + bw / 2, yy + bh)

    dlt = chip(
        d, boot_box(y), texts["dlt"], texts["dlt_sub"],
        fill="#e8f5e9", outline="#2e7d32", title_fill="#1b5e20",
        fnt_t=f20b, fnt_s=f15, sub_fill="#558b2f",
    )
    y_roudi = y + bh + vgap_boot
    roudi = chip(
        d, boot_box(y_roudi), texts["roudi"], texts["roudi_sub"],
        fill="#e3f2fd", outline="#1565c0", title_fill="#0d47a1",
        fnt_t=f20b, fnt_s=f15, sub_fill="#546e7a",
    )
    y_em = y_roudi + bh + vgap_boot
    em = chip(
        d, boot_box(y_em), texts["em"], texts["em_sub"],
        fill="#fff3e0", outline="#ef6c00", title_fill="#e65100",
        fnt_t=f20b, fnt_s=f15, sub_fill="#6d4c41",
    )
    y_apps = y_em + bh + vgap_boot
    apps = chip(
        d, boot_box(y_apps), texts["apps"], texts["apps_sub"],
        fill="#fce4ec", outline="#c2185b", title_fill="#880e4f",
        fnt_t=f20b, fnt_s=f15, sub_fill="#6d4c41",
    )

    # HOST frame around dlt-daemon · RouDi · EM (Giraffe platform daemons)
    host_pad_x, host_pad_y = 14.0, 8.0
    host_frame = Box(
        dlt.x0 - host_pad_x, dlt.y0 - host_pad_y,
        dlt.x1 + host_pad_x, em.y1 + host_pad_y,
    )
    d.rounded_rectangle(
        host_frame.as_ints(), radius=10, outline="#607d8b", width=2,
    )

    # HOST brace left of frame; label on the *right* of the brace (toward chips).
    mid_y = (host_frame.y0 + host_frame.y1) / 2
    hw = d.textlength(texts["host"], font=f15b)
    host_label_gap = 6.0
    # Need room between brace and frame for "HOST"
    host_brace_x = host_frame.x0 - 18 - hw - host_label_gap
    d.line(
        [(host_brace_x, host_frame.y0), (host_brace_x, host_frame.y1)],
        fill="#546e7a", width=2,
    )
    d.line(
        [(host_brace_x, host_frame.y0), (host_brace_x + 10, host_frame.y0)],
        fill="#546e7a", width=2,
    )
    d.line(
        [(host_brace_x, host_frame.y1), (host_brace_x + 10, host_frame.y1)],
        fill="#546e7a", width=2,
    )
    host_label_x = host_brace_x + 12
    d.text((host_label_x, mid_y - 8), texts["host"], fill="#37474f", font=f15b)

    # systemd/init left of brace → HOST
    init_w = max(
        sized(texts["init"], texts["init_sub"], pad_x=28),
        118.0,
    )
    init_gap = 14.0
    init_h = host_frame.h * 0.5
    init_box = Box(
        host_brace_x - init_gap - init_w,
        mid_y - init_h / 2,
        host_brace_x - init_gap,
        mid_y + init_h / 2,
    )
    if init_box.x0 < page.x0 + 2:
        init_box = Box(page.x0 + 2, init_box.y0, init_box.x1, init_box.y1)
    chip(
        d, init_box, texts["init"], texts["init_sub"],
        fill="#eceff1", outline="#455a64", title_fill="#263238",
        fnt_t=f16, fnt_s=f15, sub_fill="#78909c",
    )

    def _dash_rect(b: Box, color: str, *, dash: int = 5, gap: int = 4) -> None:
        x0, y0, x1, y1 = b.as_ints()
        segs: list[tuple[tuple[int, int], tuple[int, int]]] = []
        x = x0
        while x < x1:
            segs.append(((x, y0), (min(x + dash, x1), y0)))
            x += dash + gap
        x = x0
        while x < x1:
            segs.append(((x, y1), (min(x + dash, x1), y1)))
            x += dash + gap
        y = y0
        while y < y1:
            segs.append(((x0, y), (x0, min(y + dash, y1))))
            y += dash + gap
        y = y0
        while y < y1:
            segs.append(((x1, y), (x1, min(y + dash, y1))))
            y += dash + gap
        for a, b2 in segs:
            d.line([a, b2], fill=color, width=2)

    outer = Box(init_box.x0 - 4, init_box.y0 - 4, init_box.x1 + 4, init_box.y1 + 4)
    _dash_rect(outer, "#90a4ae", dash=6, gap=4)

    ax0 = init_box.x1 + 4
    ax1 = host_brace_x - 4
    if ax1 > ax0 + 8:
        d.line([(ax0, mid_y), (ax1, mid_y)], fill="#607d8b", width=2)
        d.polygon(
            [(ax1, mid_y), (ax1 - 7, mid_y - 4), (ax1 - 7, mid_y + 4)],
            fill="#607d8b",
        )

    # Target outline colors — neighbors use distant hues (not same family).
    # exec=cyan · phm=amber · sm=green · collector=coral · per=indigo
    # com=sky · bindings=lime-teal · diag=magenta · ucm=violet
    C_DLT, C_EM, C_APPS = "#2e7d32", "#ef6c00", "#c2185b"
    C_EXEC, C_PHM, C_SM = "#26c6da", "#ffb300", "#66bb6a"
    C_COL, C_PER = "#ff7043", "#7986cb"
    C_COM, C_BIND = "#29b6f6", "#26a69a"
    C_DIAG, C_UCM = "#f06292", "#7e57c2"
    C_RING = "#c9a227"

    draw_vline_flow(d, dlt.cx, dlt.y1, roudi.y0, C_DLT, phase, width=3, n_arrows=2)
    draw_vline_flow(d, roudi.cx, roudi.y1, em.y0, C_EM, phase, width=3, n_arrows=2)
    draw_vline_flow(d, em.cx, em.y1, apps.y0, C_APPS, phase, width=3, n_arrows=2)
    d.text((em.cx + 14, (em.y1 + apps.y0) / 2 - 9), texts["spawn"], fill=C_APPS, font=f15b)

    y = apps.y1 + link_h
    ring_box = Box(cx - ring_w / 2, y, cx + ring_w / 2, y + ring_h)
    d.rounded_rectangle(ring_box.as_ints(), radius=12, fill="#12241e", outline="#c9a227", width=3)

    title_b = Box(ring_box.x0 + 14, ring_box.y0 + 6, ring_box.x1 - 14, ring_box.y0 + 6 + ring_hdr)
    vcenter_text(d, texts["ring_title"], title_b, fnt=f20b, fill="#ffe082")
    d.text((title_b.x0, title_b.cy - 9), texts["bringup"], fill="#a5d6a7", font=f15)

    # All geometry (including Updating rail + label) stays inside ring_box
    inner = Box(
        ring_box.x0 + 20,
        title_b.y1 + 14,
        ring_box.x1 - 20,
        ring_box.y1 - ring_foot,
    )
    # Rail well inside the gold border; label sits left of rail (still in inner)
    rail_x = inner.x1 - 22
    content = Box(inner.x0, inner.y0, rail_x - upd_tw - 20, inner.y1)

    row_y = content.y0
    bands: list[Box] = []
    for _ in range(n_rows):
        bands.append(Box(content.x0, row_y, content.x1, row_y + CHIP_H))
        row_y += CHIP_H + ROW_GAP
    r_ep, r_sm, r_cp, r_com, r_ota, r_base = bands

    # --- Row: exec | phm ---
    exec_c, phm_c = place_row(r_ep, [w_exec, w_phm], height=CHIP_H, gap=g_alive)
    exec_c = chip(
        d, exec_c, texts["exec"], texts["exec_sub"],
        fill="#004d40", outline=C_EXEC, title_fill="#e0f7fa",
        fnt_t=f20b, fnt_s=f15, sub_fill="#80deea",
    )
    phm_c = chip(
        d, phm_c, texts["phm"], texts["phm_sub"],
        fill="#3e2723", outline=C_PHM, title_fill="#fff8e1",
        fnt_t=f20b, fnt_s=f15, sub_fill="#ffe082",
    )
    draw_h_flow(d, exec_c.x1, phm_c.x0, exec_c.cy, C_PHM, phase, width=3, n_arrows=2)
    label_between_h(
        d, exec_c.x1, phm_c.x0, exec_c.cy, texts["alive"], fnt=f15, fill=C_PHM,
    )

    # --- Row: sm spans under exec|phm (edges land on top border) ---
    sm_box = Box(
        min(exec_c.x0, phm_c.x0),
        r_sm.cy - CHIP_H / 2,
        max(exec_c.x1, phm_c.x1),
        r_sm.cy + CHIP_H / 2,
    )
    sm_c = chip(
        d, sm_box, texts["sm"], texts["sm_sub"],
        fill="#1b5e20", outline=C_SM, title_fill="#e8f5e9",
        fnt_t=f20b, fnt_s=f15, sub_fill="#a5d6a7",
    )
    draw_vline_flow(d, exec_c.cx, exec_c.y1, sm_c.y0, C_SM, phase, width=3, n_arrows=2)
    label_beside_v(
        d, exec_c.cx, exec_c.y1, sm_c.y0, texts["ensure"], fnt=f15, fill=C_SM, side="left",
    )
    draw_vline_flow(d, phm_c.cx, phm_c.y1, sm_c.y0, C_SM, phase, width=3, n_arrows=2)
    label_beside_v(
        d, phm_c.cx, phm_c.y1, sm_c.y0, texts["fault"], fnt=f15, fill=C_SM, side="right",
    )

    # --- Row: collector centered under sm (true vertical join), per to the right ---
    half = CHIP_H / 2
    pair_w = w_col + g_persist + w_per
    col_x0 = sm_c.cx - w_col / 2
    # Keep the pair inside the content band
    if col_x0 < content.x0:
        col_x0 = content.x0
    if col_x0 + pair_w > content.x1:
        col_x0 = content.x1 - pair_w
    collector_c = chip(
        d,
        Box(col_x0, r_cp.cy - half, col_x0 + w_col, r_cp.cy + half),
        texts["collector"], texts["collector_sub"],
        fill="#bf360c", outline=C_COL, title_fill="#fbe9e7",
        fnt_t=f20b, fnt_s=f15, sub_fill="#ffab91",
    )
    per_c = chip(
        d,
        Box(collector_c.x1 + g_persist, r_cp.cy - half, collector_c.x1 + g_persist + w_per, r_cp.cy + half),
        texts["per"], texts["per_sub"],
        fill="#1a237e", outline=C_PER, title_fill="#e8eaf6",
        fnt_t=f20b, fnt_s=f15, sub_fill="#c5cae9",
    )
    # True join: vertical into collector top (centers aligned when space allows)
    if abs(sm_c.cx - collector_c.cx) < 0.5:
        draw_vline_flow(d, sm_c.cx, sm_c.y1, collector_c.y0, C_COL, phase, width=3, n_arrows=2)
    else:
        mid_y = (sm_c.y1 + collector_c.y0) / 2
        d.line([(sm_c.cx, sm_c.y1), (sm_c.cx, mid_y)], fill=C_COL, width=3)
        d.line([(sm_c.cx, mid_y), (collector_c.cx, mid_y)], fill=C_COL, width=3)
        draw_vline_flow(d, collector_c.cx, mid_y, collector_c.y0, C_COL, phase, width=3, n_arrows=2)
    draw_h_flow(d, collector_c.x1, per_c.x0, collector_c.cy, C_PER, phase, width=3, n_arrows=2)
    label_between_h(
        d, collector_c.x1, per_c.x0, collector_c.cy, texts["persist"], fnt=f15, fill=C_PER,
    )

    # --- Row: com | bindings ---
    com_b, bind_b = place_row(r_com, [w_com, w_bind], height=CHIP_H, gap=g_com)
    com_c = chip(
        d, com_b, texts["com"], texts["com_sub"],
        fill="#01579b", outline=C_COM, title_fill="#e1f5fe",
        fnt_t=f20b, fnt_s=f15, sub_fill="#81d4fa",
    )
    bind_c = chip(
        d, bind_b, texts["bindings"], texts["bindings_sub"],
        fill="#004d40", outline=C_BIND, title_fill="#e0f2f1",
        fnt_t=f20b, fnt_s=f15, sub_fill="#80cbc4",
    )
    draw_h_flow(d, com_c.x1, bind_c.x0, com_c.cy, C_BIND, phase, width=3, n_arrows=2)

    # --- Row: diag | ucm ---
    diag_b, ucm_b = place_row(r_ota, [w_diag, w_ucm], height=CHIP_H, gap=g_diag)
    diag_c = chip(
        d, diag_b, texts["diag"], texts["diag_sub"],
        fill="#880e4f", outline=C_DIAG, title_fill="#fce4ec",
        fnt_t=f20b, fnt_s=f15, sub_fill="#f8bbd0",
    )
    ucm_c = chip(
        d, ucm_b, texts["ucm"], texts["ucm_sub"],
        fill="#4527a0", outline=C_UCM, title_fill="#ede7f6",
        fnt_t=f20b, fnt_s=f15, sub_fill="#d1c4e9",
    )
    draw_h_flow(d, diag_c.x1, ucm_c.x0, diag_c.cy, C_UCM, phase, width=3, n_arrows=2)

    # ucm → sm Updating (target = sm) — inside ring
    d.line([(ucm_c.x1, ucm_c.cy), (rail_x, ucm_c.cy)], fill=C_SM, width=2)
    draw_vline_flow(d, rail_x, ucm_c.cy, sm_c.cy, C_SM, phase, width=2, n_arrows=4)
    d.line([(rail_x, sm_c.cy), (sm_c.x1, sm_c.cy)], fill=C_SM, width=2)
    label_beside_v(
        d, rail_x, sm_c.cy, ucm_c.cy, texts["updating"], fnt=f15, fill=C_SM, side="left",
    )

    # --- Row: log → DLT · tsync · OSAL (single-line, aligned) ---
    log_b, tsync_b, os_b = place_row(
        r_base, [w_log, w_tsync, w_osal], height=CHIP_H, gap=g_base,
    )
    chip(
        d, log_b, texts["log_dlt"], "",
        fill="#263238", outline="#81c784", title_fill="#eceff1", fnt_t=f20b, fnt_s=f15,
    )
    chip(
        d, tsync_b, texts["tsync"], "",
        fill="#263238", outline="#90a4ae", title_fill="#eceff1", fnt_t=f20b, fnt_s=f15,
    )
    chip(
        d, os_b, texts["osal"], "",
        fill="#37474f", outline="#b0bec5", title_fill="#eceff1", fnt_t=f20b, fnt_s=f15,
    )

    d.text((ring_box.x0 + 14, ring_box.y1 - 22), texts["fusa"], fill="#a5d6a7", font=f15)
    draw_vline_flow(d, apps.cx, apps.y1, ring_box.y0, C_RING, phase, width=3, n_arrows=2)

    return img


def save_gif(texts: dict, out: Path) -> None:
    frames = [draw_frame(texts, i / FRAMES) for i in range(FRAMES)]
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        optimize=True,
    )
    print(f"wrote {out} ({out.stat().st_size // 1024} KiB)")


def write_svg(texts: dict, out: Path, *, aria: str) -> None:
    # Lightweight placeholder; GIF is the source of truth for layout.
    frame = draw_frame(texts, 0.0)
    h = frame.size[1]
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 {h}" width="1100" height="{h}"
     role="img" aria-label="{html.escape(aria, quote=True)}">
  <rect width="1100" height="{h}" fill="#fafbfc"/>
  <text x="550" y="36" text-anchor="middle" font="700 22px sans-serif" fill="#1b5e20">{html.escape(texts["title"])}</text>
  <text x="550" y="60" text-anchor="middle" font="500 16px sans-serif" fill="#546e7a">{html.escape(texts["subtitle"])}</text>
  <text x="550" y="120" text-anchor="middle" font="500 14px sans-serif" fill="#546e7a">See Giraffe_Modules.gif for the animated layout.</text>
  <text x="550" y="150" text-anchor="middle" font="500 13px sans-serif" fill="#78909c">systemd/init → HOST(dlt-daemon? · RouDi · EM) → SOA apps · in-process ring</text>
</svg>
"""
    out.write_text(body, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KiB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--en", action="store_true", help="also write EN gif/svg")
    args = ap.parse_args()
    save_gif(ZH, ROOT / "Giraffe_Modules.gif")
    write_svg(ZH, ROOT / "Giraffe_Modules.svg", aria="Giraffe Modules：中间件协作")
    if args.en:
        save_gif(EN, ROOT / "Giraffe_Modules.en.gif")
        write_svg(EN, ROOT / "Giraffe_Modules.en.svg", aria="Giraffe Modules: middleware collaboration")


if __name__ == "__main__":
    main()
