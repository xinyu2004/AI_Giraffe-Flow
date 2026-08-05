#!/usr/bin/env python3
"""Render Giraffe_Flow.gif + Giraffe_Flow.svg (reproducible).

Layout (Chinese-first):
  gf-config
       ↓
  CARLA ══▶ GIRAFFE 模块 ──▶ Foxglove
            (FuSa above SOA apps)
       ↓↑ tap / inject
      GMT

Replace icons anytime:
  ../assets/carla.png
  ../assets/foxglove.png       # portrait Studio shot OK

Usage:
  python3 render_gif.py           # ZH only → Giraffe_Flow.gif/.svg
  python3 render_gif.py --en      # also EN (later)
"""
from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent  # result_pic/Giraffe_Flow
ASSETS = ROOT / "assets"
W = 1200
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

    def pad(self, left: float, top: float, right: float, bottom: float) -> Box:
        return Box(
            self.x0 + self.w * left,
            self.y0 + self.h * top,
            self.x1 - self.w * right,
            self.y1 - self.h * bottom,
        )

    def pad_uniform(self, f: float) -> Box:
        return self.pad(f, f, f, f)

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

    def grid(
        self,
        rows: int,
        cols: int,
        gap_frac: float = 0.03,
        *,
        gap_x_frac: float | None = None,
        gap_y_frac: float | None = None,
    ) -> list[list[Box]]:
        gap_x = self.w * (gap_x_frac if gap_x_frac is not None else gap_frac)
        gap_y = self.h * (gap_y_frac if gap_y_frac is not None else gap_frac)
        cw = (self.w - gap_x * (cols - 1)) / cols
        ch = (self.h - gap_y * (rows - 1)) / rows
        cells: list[list[Box]] = []
        for r in range(rows):
            row: list[Box] = []
            for c in range(cols):
                x0 = self.x0 + c * (cw + gap_x)
                y0 = self.y0 + r * (ch + gap_y)
                row.append(Box(x0, y0, x0 + cw, y0 + ch))
            cells.append(row)
        return cells

    def as_ints(self) -> list[int]:
        return [
            int(round(self.x0)),
            int(round(self.y0)),
            int(round(self.x1)),
            int(round(self.y1)),
        ]


def font(size: int, *, weight: str = "regular") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if boldish
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if boldish
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit_text(
    d: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[float, float],
    *,
    fnt: ImageFont.ImageFont,
    fill: str,
    max_w: float,
) -> None:
    s = text
    while s and d.textlength(s, font=fnt) > max_w:
        s = s[:-1]
    if s != text and len(s) > 1:
        s = s[:-1] + "…"
    d.text(xy, s, fill=fill, font=fnt)


def center_text(
    d: ImageDraw.ImageDraw,
    text: str,
    y: float,
    *,
    fnt: ImageFont.ImageFont,
    fill: str,
    max_w: float | None = None,
    cx: float | None = None,
) -> None:
    s = text
    if max_w is not None:
        while s and d.textlength(s, font=fnt) > max_w:
            s = s[:-1]
        if s != text and len(s) > 1:
            s = s[:-1] + "…"
    tw = d.textlength(s, font=fnt)
    d.text(((cx if cx is not None else CX) - tw / 2, y), s, fill=fill, font=fnt)


def _draw_centered(
    d: ImageDraw.ImageDraw,
    box: Box,
    text: str,
    *,
    fnt: ImageFont.ImageFont,
    fill: str,
) -> None:
    cx = (box.x0 + box.x1) / 2
    nudge = 0.5 if box.h < 22 else 1.0
    cy = (box.y0 + box.y1) / 2 + nudge
    try:
        l, t, r, b = d.textbbox((0, 0), text, font=fnt)
        ink_h = b - t
        if ink_h > box.h - 2:
            cy = box.y0 + box.h / 2
        d.text((cx - (l + r) / 2, cy - (t + b) / 2), text, fill=fill, font=fnt)
    except Exception:
        tw = d.textlength(text, font=fnt)
        d.text((cx - tw / 2, cy - 6), text, fill=fill, font=fnt)


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
    mw = max_w if max_w is not None else box.w * 0.95
    while s and d.textlength(s, font=fnt) > mw:
        s = s[:-1]
    if s != text and len(s) > 1:
        s = s[:-1] + "…"
    _draw_centered(d, box, s, fnt=fnt, fill=fill)


def chip(
    d: ImageDraw.ImageDraw,
    box: Box,
    label: str,
    *,
    fill: str,
    outline: str,
    text_fill: str,
    fnt: ImageFont.ImageFont,
) -> Box:
    bi = box.as_ints()
    d.rounded_rectangle(
        bi, radius=max(3, int(min(box.w, box.h) * 0.12)), fill=fill, outline=outline, width=1
    )
    s = label
    max_w = box.w * 0.90
    while s and d.textlength(s, font=fnt) > max_w:
        s = s[:-1]
    if s != label and len(s) > 1:
        s = s[:-1] + "…"
    _draw_centered(d, box, s, fnt=fnt, fill=text_fill)
    return box


def draw_vline_flow(
    draw: ImageDraw.ImageDraw,
    x: int,
    y0: int,
    y1: int,
    color: str,
    width: int,
    phase: float,
    *,
    n_arrows: int = 3,
) -> None:
    draw.line([(x, y0), (x, y1)], fill=color, width=width)
    length = abs(y1 - y0)
    if length < 12:
        return
    step = 1 if y1 >= y0 else -1
    n = max(2, min(n_arrows, max(2, length // 14)))
    spacing = length / n
    tip_h = max(11, min(15, length // 3))
    half_w = max(8, tip_h // 2 + 2)
    for i in range(n):
        pos = (phase * spacing + i * spacing) % length
        if pos < tip_h * 0.35 or pos > length - tip_h * 0.25:
            continue
        tip_y = y0 + int(pos) * step
        base_y = tip_y - tip_h * step
        draw.polygon(
            [(x, tip_y), (x - half_w - 1, base_y), (x + half_w + 1, base_y)],
            fill="#ffffff",
        )
        draw.polygon([(x, tip_y), (x - half_w, base_y), (x + half_w, base_y)], fill=color)


def draw_taper_h_flow(
    draw: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    cy: float,
    *,
    left_half: float,
    right_half: float,
    color: str,
    phase: float,
    n_dots: int = 3,
) -> None:
    """Fat→thin body + solid arrowhead (勾). No white outline — that was the white seam."""
    if x1 - x0 < 4:
        return
    tip = min(22.0, max(14.0, (x1 - x0) * 0.45))
    hook = max(right_half + 14, left_half * 0.55)
    # One green shape only (body + head). No white underlay/outline at the tip.
    body_and_head = [
        (x0, cy - left_half),
        (x1, cy - right_half),
        (x1 - 2, cy - hook),
        (x1 + tip, cy),
        (x1 - 2, cy + hook),
        (x1, cy + right_half),
        (x0, cy + left_half),
    ]
    draw.polygon(body_and_head, fill=color)
    # Circles on top — may cover body + head.
    travel = (x1 + tip * 0.55) - x0
    n = max(2, min(n_dots, max(2, int(travel // 14))))
    spacing = travel / n
    for i in range(n):
        pos = (phase * spacing + i * spacing) % travel
        t = min(1.0, pos / max(1.0, (x1 - x0)))
        half = left_half + (right_half - left_half) * t
        r = max(3, int(half * 0.52 * 0.75))
        x = x0 + pos
        if x - r < x0 + 3:
            continue
        max_x = x1 + tip - 2
        if x + r > max_x:
            r = int(max_x - x)
            if r < 3:
                continue
        draw.ellipse([x - r, cy - r, x + r, cy + r], fill="#e8f5e9")


def draw_h_flow(
    draw: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    cy: float,
    *,
    width: int,
    color: str,
    phase: float,
    n_arrows: int = 3,
) -> None:
    """Shaft + traveling chevrons only (same idea as inject — no static end tip)."""
    draw.line([(x0, cy), (x1, cy)], fill="#ffffff", width=width + 6)
    draw.line([(x0, cy), (x1, cy)], fill=color, width=width)
    length = x1 - x0
    if length < 16:
        return
    n = max(2, min(n_arrows, max(2, int(length // 14))))
    spacing = length / n
    # Larger hooks so motion reads like tap/inject.
    tip_h = max(13, min(18, int(length // 2.2)))
    half_w = max(10, tip_h // 2 + 4)
    for i in range(n):
        pos = (phase * spacing + i * spacing) % length
        if pos < tip_h * 0.4 or pos > length - tip_h * 0.2:
            continue
        x = x0 + pos
        # White outline then fill — chevron "hook" stays visible on the shaft.
        draw.polygon(
            [(x + tip_h + 1, cy), (x - 1, cy - half_w - 1), (x - 1, cy + half_w + 1)],
            fill="#ffffff",
        )
        draw.polygon(
            [(x + tip_h, cy), (x, cy - half_w), (x, cy + half_w)],
            fill=color,
        )


def load_side_icon(
    name: str,
    max_w: int,
    max_h: int | None = None,
    *,
    cover: bool = False,
) -> Image.Image | None:
    """Load PNG into max_w×max_h. cover=True fills the box (center-crop)."""
    path = ASSETS / f"{name}.png"
    if not path.is_file():
        return None
    im = Image.open(path).convert("RGBA")
    mh = max_h if max_h is not None else max_w
    mw, mh = max(1, max_w), max(1, mh)
    if cover:
        scale = max(mw / im.width, mh / im.height)
        nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        left = max(0, (nw - mw) // 2)
        top = max(0, (nh - mh) // 2)
        return im.crop((left, top, left + mw, top + mh))
    im.thumbnail((mw, mh), Image.Resampling.LANCZOS)
    return im


def paste_icon(
    base: Image.Image,
    icon: Image.Image | None,
    box: Box,
    *,
    valign: str = "center",
) -> tuple[int, int] | None:
    """Paste icon; returns top-left on base. valign: center|top."""
    if icon is None:
        return None
    ix = int(box.x0 + (box.w - icon.width) / 2)
    if valign == "top":
        iy = int(box.y0 + 2)
    else:
        iy = int(box.y0 + (box.h - icon.height) / 2)
    base.paste(icon, (ix, iy), icon)
    return ix, iy


def draw_side_card(
    img: Image.Image,
    d: ImageDraw.ImageDraw,
    box: Box,
    *,
    title: str,
    sub: str,
    icon_name: str,
    fill: str,
    outline: str,
    title_fill: str,
    fnt_title: ImageFont.ImageFont,
    fnt_sub: ImageFont.ImageFont,
    portrait: bool = False,
) -> None:
    """Side node — CARLA / Foxglove share the same vertical + font proportions.

    portrait=True only changes how media is fitted (contain for tall screenshots).
    """
    d.rounded_rectangle(box.as_ints(), radius=10, fill=fill, outline=outline, width=2)
    inn = box.pad(0.06, 0.05, 0.06, 0.05)
    # Shared footer height (px) so title/sub proportions match on both sides.
    footer_h = min(58.0, max(48.0, inn.h * 0.28))
    media_b = Box(inn.x0, inn.y0, inn.x1, inn.y1 - footer_h)
    title_b = Box(inn.x0, inn.y1 - footer_h, inn.x1, inn.y1 - footer_h * 0.45)
    sub_b = Box(inn.x0, inn.y1 - footer_h * 0.45, inn.x1, inn.y1)
    if portrait:
        media = load_side_icon(
            icon_name,
            int(media_b.w * 0.96),
            int(media_b.h * 0.96),
            cover=False,
        )
        paste_icon(img, media, media_b, valign="center")
    else:
        side = int(min(media_b.w, media_b.h) * 0.90)
        media = load_side_icon(icon_name, side, side)
        paste_icon(img, media, media_b, valign="center")
    vcenter_text(d, title, title_b, fnt=fnt_title, fill=title_fill)
    vcenter_text(d, sub, sub_b, fnt=fnt_sub, fill="#78909c", max_w=inn.w)


def draw_frame(texts: dict, phase: float) -> Image.Image:
    content_h = 860.0
    img = Image.new("RGB", (W, int(content_h) + 40), "#fafbfc")
    d = ImageDraw.Draw(img)
    f18b = font(18, weight="bold")
    f14b = font(14, weight="bold")
    f13b, f12b = font(13, weight="bold"), font(12, weight="bold")
    f12, f11 = font(12, weight="medium"), font(11, weight="medium")
    f11b = font(11, weight="bold")
    f10 = font(10, weight="medium")

    def glyph_bottom(fnt: ImageFont.ImageFont, sample: str) -> int:
        bb = fnt.getbbox(sample)
        return int(bb[3]) if bb else 14

    def glyph_top(fnt: ImageFont.ImageFont, sample: str) -> int:
        bb = fnt.getbbox(sample)
        return int(bb[1]) if bb else 0

    page = Box(0, 0, W, content_h)
    # side | arrow gutter | board | arrow gutter | side
    # Foxglove ~3/4 of prior width; left gutter kept wide enough for CARLA funnel.
    left_col, gap_l, mid_col, gap_r, right_col = page.pad(0.01, 0.01, 0.01, 0.01).split_h(
        0.10, 0.07, 0.639, 0.05, 0.141
    )

    cfg_b, _g1, board_slot, _g2, link_b, _gmt_slot = mid_col.split_v(
        0.11, 0.03, 0.58, 0.012, 0.045, 0.223
    )
    # Short discrete pins (gaps between pads = the “grooves”).
    pin_w = 12.0
    board_b = Box(
        board_slot.x0 + pin_w + 4,
        board_slot.y0,
        board_slot.x1 - pin_w - 4,
        board_slot.y1,
    )
    board_cx = (board_b.x0 + board_b.x1) / 2

    # --- 1. gf-config (over board column) ---
    d.rounded_rectangle(cfg_b.as_ints(), radius=8, fill="#fff8e1", outline="#f9a825", width=2)
    cfg_in = cfg_b.pad(0.03, 0.06, 0.03, 0.06)
    head, tabs = cfg_in.split_v(0.36, 0.64)
    h_name, h_tag = head.split_v(0.55, 0.45)
    vcenter_text(d, texts["cfg_name"], h_name, fnt=f18b, fill="#5d4037")
    vcenter_text(d, texts["cfg_tag"], h_tag, fnt=f12, fill="#6d4c41", max_w=cfg_in.w * 0.95)
    t1, _sp, t2 = tabs.split_h(0.48, 0.04, 0.48)
    for tab, title, sub in (
        (t1, texts["tab1_title"], texts["tab1_l1"]),
        (t2, texts["tab2_title"], texts["tab2_l1"]),
    ):
        d.rounded_rectangle(tab.as_ints(), radius=6, fill="#fffde7", outline="#ffb300", width=1)
        tin = tab.pad(0.04, 0.10, 0.04, 0.10)
        t_title, t_sub = tin.split_v(0.52, 0.48)
        vcenter_text(d, title, t_title, fnt=f14b, fill="#e65100", max_w=tin.w)
        vcenter_text(d, sub, t_sub, fnt=f11, fill="#5d4037", max_w=tin.w)

    ax = int(board_cx)
    y0, y1 = int(cfg_b.y1), int(board_b.y0)
    d.line([(ax, y0), (ax, y1 - 6)], fill="#f9a825", width=2)
    d.polygon([(ax, y1), (ax - 7, y1 - 12), (ax + 7, y1 - 12)], fill="#f9a825")
    fit_text(
        d,
        texts["flash"],
        (ax + 14, (y0 + y1) / 2 - 6),
        fnt=f11,
        fill="#8d6e63",
        max_w=mid_col.w * 0.35,
    )

    # --- side cards first (same height / type scale; widths stay from columns) ---
    side_h = board_b.h * 0.58
    side_y0 = board_b.y0 + (board_b.h - side_h) / 2
    carla_b = Box(left_col.x0, side_y0, left_col.x1, side_y0 + side_h)
    fox_b = Box(right_col.x0, side_y0, right_col.x1, side_y0 + side_h)

    def paint_side_cards() -> None:
        # Shared title/sub fonts so both sides match.
        draw_side_card(
            img,
            d,
            carla_b,
            title=texts["carla_name"],
            sub=texts["carla_sub"],
            icon_name="carla",
            fill="#e8f5e9",
            outline="#2e7d32",
            title_fill="#1b5e20",
            fnt_title=f14b,
            fnt_sub=f12,
        )
        draw_side_card(
            img,
            d,
            fox_b,
            title=texts["fox_name"],
            sub=texts["fox_sub"],
            icon_name="foxglove",
            fill="#e3f2fd",
            outline="#1565c0",
            title_fill="#0d47a1",
            fnt_title=f14b,
            fnt_sub=f12,
            portrait=True,
        )

    paint_side_cards()

    # --- 2. Giraffe board (pins drawn after side arrows so they stay continuous) ---
    d.rounded_rectangle(board_b.as_ints(), radius=12, fill="#12241e", outline="#c9a227", width=3)
    pin_h = board_b.h * 0.028
    n_pins = 14

    def draw_gold_fingers() -> None:
        # Discrete pads only — no continuous rail (that looked like a wall).
        for i in range(n_pins):
            fy = 0.05 + (0.90 * i / (n_pins - 1))
            py = board_b.y0 + board_b.h * fy - pin_h / 2
            d.rounded_rectangle(
                [int(board_b.x0 - pin_w), int(py), int(board_b.x0), int(py + pin_h)],
                radius=2,
                fill="#c9a227",
            )
            d.rounded_rectangle(
                [int(board_b.x1), int(py), int(board_b.x1 + pin_w), int(py + pin_h)],
                radius=2,
                fill="#c9a227",
            )

    draw_gold_fingers()

    bin_ = board_b.pad(0.025, 0.02, 0.025, 0.02)
    # Order: header → SoC → FuSa → SOA apps (themes get more vertical share)
    hdr, _s1, soc_b, _s2, fusa_b, _s3, apps_b = bin_.split_v(
        0.145, 0.012, 0.285, 0.012, 0.140, 0.012, 0.394
    )

    h_title, h_bar, h_arch, h_sub = hdr.split_v(0.22, 0.26, 0.32, 0.20)
    vcenter_text(d, texts["giraffe_brand"], h_title, fnt=f18b, fill="#ffe082")
    bar = h_bar.pad(0.08, 0.08, 0.08, 0.08)
    d.rounded_rectangle(bar.as_ints(), radius=6, fill="#0d1f1a", outline="#78909c", width=1)
    vcenter_text(d, texts["board_title"], bar, fnt=f12, fill="#cfd8dc")
    arch = h_arch.pad(0.0, 0.10, 0.0, 0.10)
    labels = texts["arch_chips"]
    band_w = arch.w * 0.58
    chip_row = Box(
        arch.x0 + (arch.w - band_w) / 2,
        arch.y0,
        arch.x0 + (arch.w + band_w) / 2,
        arch.y1,
    )
    cells = chip_row.grid(1, len(labels), gap_frac=0.04)[0]
    for cell, label in zip(cells, labels):
        chip(d, cell, label, fill="#0d47a1", outline="#4fc3f7", text_fill="#e1f5fe", fnt=f11b)
    vcenter_text(d, texts["board_sub"], h_sub, fnt=f11, fill="#a5d6a7")

    # SoC
    d.rounded_rectangle(soc_b.as_ints(), radius=8, fill="#0f3d36", outline="#26a69a", width=2)
    soc_in = soc_b.pad(0.03, 0.06, 0.03, 0.06)
    soc_txt, soc_grid = soc_in.split_v(0.30, 0.70)
    fit_text(d, texts["soc1"], (soc_txt.x0, soc_txt.y0), fnt=f13b, fill="#80cbc4", max_w=soc_txt.w)
    fit_text(
        d,
        texts["soc2"],
        (soc_txt.x0, soc_txt.y0 + soc_txt.h * 0.55),
        fnt=f11,
        fill="#b2dfdb",
        max_w=soc_txt.w,
    )
    chips = texts["chips"]
    strip_h = min(soc_grid.h * 0.82, 64)
    strip = Box(
        soc_grid.x0,
        soc_grid.y0 + (soc_grid.h - strip_h) / 2,
        soc_grid.x1,
        soc_grid.y0 + (soc_grid.h + strip_h) / 2,
    )
    grid = strip.grid(2, 6, gap_x_frac=0.004, gap_y_frac=0.035)
    for i, label in enumerate(chips[:12]):
        r, c = divmod(i, 6)
        chip(d, grid[r][c], label, fill="#134e48", outline="#4db6ac", text_fill="#e0f2f1", fnt=f11)

    # FuSa (above SOA apps)
    d.rounded_rectangle(fusa_b.as_ints(), radius=8, fill="#1b3328", outline="#66bb6a", width=2)
    fin = fusa_b.pad(0.03, 0.10, 0.03, 0.10)
    f_lab, f_chips = fin.split_h(0.20, 0.80)
    fit_text(
        d, texts["fusa_title"], (f_lab.x0, f_lab.y0 + f_lab.h * 0.1), fnt=f12b, fill="#a5d6a7", max_w=f_lab.w
    )
    fit_text(
        d, texts["fusa_sub"], (f_lab.x0, f_lab.y0 + f_lab.h * 0.55), fnt=f11, fill="#81c784", max_w=f_lab.w
    )
    fcells = f_chips.grid(1, len(texts["fusa_chips"]), gap_frac=0.04)[0]
    for cell, label in zip(fcells, texts["fusa_chips"]):
        chip(d, cell.pad_uniform(0.06), label, fill="#243d32", outline="#81c784", text_fill="#e8f5e9", fnt=f11)

    # SOA apps
    d.rounded_rectangle(apps_b.as_ints(), radius=8, fill="#3e2723", outline="#ff8a65", width=2)
    apps_in = apps_b.pad(0.03, 0.04, 0.03, 0.04)
    apps_txt, apps_flow = apps_in.split_v(0.26, 0.74)
    a1, a2 = apps_txt.split_v(0.48, 0.52)
    fit_text(d, texts["apps1"], (a1.x0, a1.y0 + a1.h * 0.15), fnt=f13b, fill="#ffab91", max_w=apps_txt.w)
    fit_text(
        d, texts["apps_principle"], (a2.x0, a2.y0 + a2.h * 0.15), fnt=f11, fill="#ffccbc", max_w=apps_txt.w
    )
    row1, _gap_r, row2 = apps_flow.split_v(0.38, 0.08, 0.54)
    # No trailing “区划/目标/Ego” note — just the app chain.
    c1, _a1, c2, _a2, c3 = row1.split_h(0.28, 0.08, 0.28, 0.08, 0.28)
    g = chip(
        d, c1.pad(0.0, 0.02, 0.0, 0.02), "gateway", fill="#4e342e", outline="#ffab91", text_fill="#fff3e0", fnt=f10
    )
    s = chip(
        d, c2.pad(0.0, 0.02, 0.0, 0.02), "sensing", fill="#4e342e", outline="#ffab91", text_fill="#fff3e0", fnt=f10
    )
    p = chip(
        d,
        c3.pad(0.0, 0.02, 0.0, 0.02),
        "perception",
        fill="#4e342e",
        outline="#ffab91",
        text_fill="#fff3e0",
        fnt=f10,
    )

    def link_h(a: Box, b: Box) -> None:
        y = (a.y0 + a.y1) / 2
        sx, ex = a.x1 + 2, b.x0 - 2
        if ex - sx < 8:
            return
        d.line([(sx, y), (ex - 6, y)], fill="#ffab91", width=2)
        d.polygon([(ex, y), (ex - 7, y - 4), (ex - 7, y + 4)], fill="#ffab91")

    link_h(g, s)
    link_h(s, p)

    plan_band = Box(row2.x0, row2.y0, c3.x1, row2.y1)
    left_p, _mid, right_p = plan_band.split_h(0.46, 0.08, 0.46)
    pd = chip(
        d,
        left_p.pad(0.02, 0.04, 0.02, 0.04),
        "planning.driving",
        fill="#4e342e",
        outline="#ffab91",
        text_fill="#fff3e0",
        fnt=f10,
    )
    pp = chip(
        d,
        right_p.pad(0.02, 0.04, 0.02, 0.04),
        "planning.parking",
        fill="#4e342e",
        outline="#ffab91",
        text_fill="#fff3e0",
        fnt=f10,
    )
    px = (p.x0 + p.x1) / 2
    mid_y = (row1.y1 + row2.y0) / 2
    d.line([(px, p.y1), (px, mid_y)], fill="#ffab91", width=2)
    d.line([(pd.x0 + pd.w / 2, mid_y), (pp.x0 + pp.w / 2, mid_y)], fill="#ffab91", width=2)
    d.line([(pd.x0 + pd.w / 2, mid_y), (pd.x0 + pd.w / 2, pd.y0)], fill="#ffab91", width=2)
    d.line([(pp.x0 + pp.w / 2, mid_y), (pp.x0 + pp.w / 2, pp.y0)], fill="#ffab91", width=2)

    # tap / inject
    board_bot = int(board_b.y1)
    board_outline = 3
    lx0 = int(board_b.x0 + board_b.w * 0.22)
    lx1 = int(board_b.x0 + board_b.w * 0.72)
    ly0 = board_bot + board_outline + 2
    ly1 = int(link_b.y1)
    draw_vline_flow(d, lx0, ly0, ly1, "#2e7d32", 3, phase, n_arrows=3)
    d.text((lx0 + 12, (ly0 + ly1) / 2 - 6), texts["tap"], fill="#2e7d32", font=f11)
    draw_vline_flow(d, lx1, ly1, ly0, "#c62828", 3, phase, n_arrows=3)
    d.text((lx1 + 12, (ly0 + ly1) / 2 - 6), texts["inject"], fill="#c62828", font=f11)
    d.rounded_rectangle(board_b.as_ints(), radius=12, outline="#c9a227", width=board_outline)

    # Side arrows last — tip stops before pin tips; phase matches tap/inject.
    cy_side = (carla_b.y0 + carla_b.y1) / 2
    pin_tip_l = board_b.x0 - pin_w
    pin_tip_r = board_b.x1 + pin_w
    # Gap after CARLA; body end leaves room for tip (~20px) before pin tips.
    tip_budget = 22.0
    arrow_l0 = carla_b.x1 + 8
    arrow_l1 = pin_tip_l - tip_budget - 2
    arrow_r0 = pin_tip_r + 10
    arrow_r1 = fox_b.x0 - 8
    if arrow_l1 > arrow_l0 + 12:
        span = arrow_l1 - arrow_l0
        lh = min(36.0, max(18.0, span * 0.55))
        rh = min(14.0, max(7.0, lh * 0.40))
        draw_taper_h_flow(
            d,
            arrow_l0,
            arrow_l1,
            cy_side,
            left_half=lh,
            right_half=rh,
            color="#2e7d32",
            phase=phase,
            n_dots=3,
        )
    if arrow_r1 - arrow_r0 >= 20:
        draw_h_flow(
            d,
            arrow_r0,
            arrow_r1,
            cy_side,
            width=6,
            color="#1565c0",
            phase=phase,
            n_arrows=3,
        )
    # Cover spill onto side cards. Redraw fingers, then tip zone stays clear of pins.
    paint_side_cards()
    draw_gold_fingers()
    d.rounded_rectangle(board_b.as_ints(), radius=12, outline="#c9a227", width=3)
    # Redraw CARLA funnel last so the 勾 is never buried under gold fingers.
    if arrow_l1 > arrow_l0 + 12:
        span = arrow_l1 - arrow_l0
        lh = min(36.0, max(18.0, span * 0.55))
        rh = min(14.0, max(7.0, lh * 0.40))
        draw_taper_h_flow(
            d,
            arrow_l0,
            arrow_l1,
            cy_side,
            left_half=lh,
            right_half=rh,
            color="#2e7d32",
            phase=phase,
            n_dots=3,
        )

    # --- 3. GMT ---
    gmt_top = int(link_b.y1 + content_h * 0.004)
    pad = 12
    gap_title_sub = 3
    gap_sub_rows = 6
    row_h = 17
    n_rows = len(texts["gmt_left"])
    y_name = gmt_top + pad - glyph_top(f18b, texts["gmt_name"])
    y_sub = y_name + glyph_bottom(f18b, texts["gmt_name"]) + gap_title_sub - glyph_top(
        f12, texts["gmt_sub"]
    )
    y_rows = y_sub + glyph_bottom(f12, texts["gmt_sub"]) + gap_sub_rows - glyph_top(
        f12, texts["gmt_left"][-1]
    )
    last_ink = y_rows + (n_rows - 1) * row_h + glyph_bottom(f12, texts["gmt_left"][-1])
    gmt_bot = last_ink + pad
    gmt_box = Box(mid_col.x0, gmt_top, mid_col.x1, gmt_bot)
    d.rounded_rectangle(gmt_box.as_ints(), radius=8, fill="#e3f2fd", outline="#1565c0", width=2)
    center_text(d, texts["gmt_name"], y_name, fnt=f18b, fill="#0d47a1", cx=board_cx)
    center_text(
        d, texts["gmt_sub"], y_sub, fnt=f12, fill="#1565c0", max_w=gmt_box.w * 0.92, cx=board_cx
    )
    col_l = gmt_box.x0 + gmt_box.w * 0.06
    col_r = gmt_box.x0 + gmt_box.w * 0.52
    max_lw = gmt_box.w * 0.4
    for i, (left, right) in enumerate(zip(texts["gmt_left"], texts["gmt_right"])):
        ry = y_rows + i * row_h
        fit_text(d, left, (col_l, ry), fnt=f12, fill="#37474f", max_w=max_lw)
        fit_text(d, right, (col_r, ry), fnt=f12, fill="#37474f", max_w=max_lw)

    return img.crop((0, 0, W, int(gmt_bot + 8)))


ZH = {
    "cfg_name": "gf-config",
    "cfg_tag": "配置车型契约 — 连线、裁剪、中间件清单",
    "tab1_title": "连线：信号与应用",
    "tab1_l1": "wiring 画布 · SKU / live_tap",
    "tab2_title": "配置：中间件与平台",
    "tab2_l1": "勾选模块 · 填 exec / EM / PHM …",
    "flash": "compose → 烧录 / 编进",
    "giraffe_brand": "GIRAFFE 模块",
    "board_title": "运行于  ·  SIL / HIL · 板端  ·  产品主体",
    "arch_chips": ["ARM", "MIPS", "RISC-V", "…"],
    "board_sub": "真正跑在车端 / SIL — EM 按拓扑 OSAL Spawn Apps",
    "soc1": "SoC · middleware / gf_ara（SKU 可裁剪）",
    "soc2": "com → iceoryx | SOME/IP | DDS · OSAL process · 下方为平台服务",
    "chips": ["com", "EM", "exec", "phm", "sm", "collector", "OSAL", "diag", "ucm", "log", "per", "tsync"],
    "apps1": "SOA apps · 由 EM 按拓扑拉起",
    "apps_principle": "App 只发布/订阅服务名，不硬绑进程；换 OEM 包，契约不变",
    "fusa_title": "FuSa",
    "fusa_sub": "→ Safety Case",
    "fusa_chips": ["POLICY", "cases", "metrics", "safety-case", "packs"],
    "carla_name": "CARLA",
    "carla_sub": "仿真 · 视频/传感入",
    "fox_name": "Foxglove",
    "fox_sub": "可视化 · Studio",
    "tap": "tap / 观测",
    "inject": "inject / 回灌",
    "gmt_name": "GMT",
    "gmt_sub": "主机工具 · 观测 / 回灌（debug-path · 不作板级 ASIL 证据）",
    "gmt_left": [
        "· Live ws (8766)",
        "· 动画 DAG",
        "· Tag / clip",
        "· Studio 桥接",
        "· OTA",
    ],
    "gmt_right": [
        "· Order / 先后",
        "· Graphics 图形",
        "· MCAP · VCD 导出",
        "· playhead 回灌 (8767)",
        "· DoIP",
    ],
}

EN = {
    **ZH,
    "cfg_tag": "configure the vehicle contract — wiring, trim, middleware tables",
    "tab1_title": "Connect signals & apps",
    "tab1_l1": "wiring canvas · SKU / live_tap",
    "tab2_title": "Configure middleware",
    "tab2_l1": "trim modules · fill exec / EM / PHM …",
    "flash": "compose → flash / build",
    "giraffe_brand": "GIRAFFE MODULES",
    "board_title": "runs on  ·  SIL / HIL · BOARD  ·  product core",
    "board_sub": "what actually runs — EM topo-spawns apps via OSAL",
    "soc1": "SoC · middleware / gf_ara  (SKU-trimmable)",
    "soc2": "com → iceoryx | SOME/IP | DDS · OSAL process · platform below",
    "apps1": "SOA apps · launched by EM (topo order)",
    "apps_principle": "Apps pub/sub service names only — OEM swap keeps the contract",
    "fusa_sub": "→ Safety Case",
    "carla_sub": "sim · video / sensors in",
    "fox_sub": "viz · Studio",
    "tap": "tap / observe",
    "inject": "inject / drive",
    "gmt_sub": "host tool · observe / inject  (debug-path · not board ASIL evidence)",
    "gmt_left": [
        "· Live ws (8766)",
        "· Animated DAG",
        "· Tag / clip",
        "· Studio bridge",
        "· OTA",
    ],
    "gmt_right": [
        "· Order / race",
        "· Graphics",
        "· MCAP · VCD export",
        "· playhead inject (8767)",
        "· DoIP",
    ],
}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def write_svg(texts: dict, out: Path, *, aria: str) -> None:
    """Static SVG snapshot (same story as GIF; icons referenced relatively)."""
    chips = " · ".join(texts["chips"])
    fusa = " · ".join(texts["fusa_chips"])
    gmt_l, gmt_r = texts["gmt_left"], texts["gmt_right"]
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 1200 820" width="1200" height="820"
     role="img" aria-label="{_esc(aria)}">
  <defs>
    <style><![CDATA[
      .box {{ fill:#fff8e1; stroke:#f9a825; stroke-width:2; }}
      .brand {{ font:700 18px ui-sans-serif,system-ui,sans-serif; fill:#5d4037; }}
      .tag {{ font:500 12px ui-sans-serif,system-ui,sans-serif; fill:#6d4c41; }}
      .muted {{ font:500 11px ui-sans-serif,system-ui,sans-serif; fill:#6d4c41; }}
      .small {{ font:500 11px ui-monospace,Menlo,monospace; fill:#37474f; }}
      .tab {{ fill:#fffde7; stroke:#ffb300; stroke-width:1; }}
      .tab-t {{ font:700 13px ui-sans-serif,system-ui,sans-serif; fill:#e65100; }}
      .board {{ fill:#1b2a24; stroke:#c9a227; stroke-width:2.5; }}
      .board-title {{ font:700 16px ui-sans-serif,system-ui,sans-serif; fill:#ffe082; }}
      .board-text {{ font:500 11px ui-sans-serif,system-ui,sans-serif; fill:#c8e6c9; }}
      .inner {{ fill:#0f3d36; stroke:#26a69a; stroke-width:1.5; }}
      .inner-t {{ font:500 11px ui-monospace,Menlo,monospace; fill:#b2dfdb; }}
      .inner-apps {{ fill:#3e2723; stroke:#ff8a65; stroke-width:1.5; }}
      .inner-apps-t {{ font:500 11px ui-monospace,Menlo,monospace; fill:#ffccbc; }}
      .fusa {{ fill:#1b3328; stroke:#66bb6a; stroke-width:1.5; }}
      .fusa-t {{ font:700 12px ui-sans-serif,system-ui,sans-serif; fill:#a5d6a7; }}
      .fusa-s {{ font:500 11px ui-monospace,Menlo,monospace; fill:#c8e6c9; }}
      .side {{ fill:#e8f5e9; stroke:#2e7d32; stroke-width:2; }}
      .side-fox {{ fill:#e3f2fd; stroke:#1565c0; stroke-width:2; }}
      .side-t {{ font:700 14px ui-sans-serif,system-ui,sans-serif; }}
      .side-s {{ font:500 10px ui-sans-serif,system-ui,sans-serif; fill:#78909c; }}
      .gmt {{ fill:#e3f2fd; stroke:#1565c0; stroke-width:2.5; }}
      .gmt-brand {{ font:700 18px ui-sans-serif,system-ui,sans-serif; fill:#0d47a1; }}
      .gmt-sub {{ font:500 12px ui-sans-serif,system-ui,sans-serif; fill:#1565c0; }}
      .pin {{ fill:#c9a227; }}
    ]]></style>
  </defs>

  <!-- gf-config -->
  <rect class="box" x="200" y="12" width="800" height="88" rx="8"/>
  <text class="brand" x="600" y="36" text-anchor="middle">{_esc(texts["cfg_name"])}</text>
  <text class="tag" x="600" y="54" text-anchor="middle">{_esc(texts["cfg_tag"])}</text>
  <rect class="tab" x="220" y="62" width="350" height="28" rx="5"/>
  <text class="tab-t" x="232" y="74">{_esc(texts["tab1_title"])}</text>
  <text class="muted" x="232" y="86">{_esc(texts["tab1_l1"])}</text>
  <rect class="tab" x="600" y="62" width="350" height="28" rx="5"/>
  <text class="tab-t" x="612" y="74">{_esc(texts["tab2_title"])}</text>
  <text class="muted" x="612" y="86">{_esc(texts["tab2_l1"])}</text>
  <line x1="600" y1="100" x2="600" y2="120" stroke="#f9a825" stroke-width="2"/>
  <text class="muted" x="616" y="114">{_esc(texts["flash"])}</text>

  <!-- CARLA · ~68px gutter · wide board · Foxglove -->
  <rect class="side" x="16" y="220" width="110" height="260" rx="10"/>
  <image href="assets/carla.png" x="32" y="238" width="78" height="78"
         preserveAspectRatio="xMidYMid meet"/>
  <text class="side-t" x="71" y="340" text-anchor="middle" fill="#1b5e20">{_esc(texts["carla_name"])}</text>
  <text class="side-s" x="71" y="362" text-anchor="middle">{_esc(texts["carla_sub"])}</text>
  <!-- fat→thin funnel; mouth stays wide so data circles remain -->
  <polygon points="134,328 188,348 188,372 134,392" fill="#ffffff"/>
  <polygon points="140,332 184,348 184,372 140,388" fill="#2e7d32"/>
  <circle cx="156" cy="360" r="7" fill="#e8f5e9"/>
  <circle cx="172" cy="360" r="5" fill="#e8f5e9"/>
  <polygon points="202,360 182,338 182,382" fill="#ffffff"/>
  <polygon points="200,360 183,340 183,380" fill="#2e7d32"/>

  <!-- board + continuous gold fingers -->
  <rect class="board" x="214" y="130" width="772" height="440" rx="12"/>
  <g class="pin">
    <rect x="202" y="168" width="12" height="12" rx="2"/><rect x="986" y="168" width="12" height="12" rx="2"/>
    <rect x="202" y="206" width="12" height="12" rx="2"/><rect x="986" y="206" width="12" height="12" rx="2"/>
    <rect x="202" y="244" width="12" height="12" rx="2"/><rect x="986" y="244" width="12" height="12" rx="2"/>
    <rect x="202" y="282" width="12" height="12" rx="2"/><rect x="986" y="282" width="12" height="12" rx="2"/>
    <rect x="202" y="320" width="12" height="12" rx="2"/><rect x="986" y="320" width="12" height="12" rx="2"/>
    <rect x="202" y="358" width="12" height="12" rx="2"/><rect x="986" y="358" width="12" height="12" rx="2"/>
    <rect x="202" y="396" width="12" height="12" rx="2"/><rect x="986" y="396" width="12" height="12" rx="2"/>
    <rect x="202" y="434" width="12" height="12" rx="2"/><rect x="986" y="434" width="12" height="12" rx="2"/>
    <rect x="202" y="472" width="12" height="12" rx="2"/><rect x="986" y="472" width="12" height="12" rx="2"/>
    <rect x="202" y="510" width="12" height="12" rx="2"/><rect x="986" y="510" width="12" height="12" rx="2"/>
    <rect x="202" y="540" width="12" height="12" rx="2"/><rect x="986" y="540" width="12" height="12" rx="2"/>
  </g>
  <text class="board-title" x="600" y="158" text-anchor="middle">{_esc(texts["giraffe_brand"])}</text>
  <text class="board-text" x="600" y="178" text-anchor="middle">{_esc(texts["board_title"])}</text>
  <text class="board-text" x="600" y="196" text-anchor="middle">{_esc(texts["board_sub"])}</text>

  <rect class="inner" x="234" y="210" width="732" height="90" rx="6"/>
  <text class="inner-t" x="250" y="234" fill="#80cbc4">{_esc(texts["soc1"])}</text>
  <text class="inner-t" x="250" y="256">{_esc(chips)}</text>
  <text class="inner-t" x="250" y="278">{_esc(texts["soc2"])}</text>

  <rect class="fusa" x="234" y="312" width="732" height="60" rx="6"/>
  <text class="fusa-t" x="250" y="336">{_esc(texts["fusa_title"])}  {_esc(texts["fusa_sub"])}</text>
  <text class="fusa-s" x="250" y="358">{_esc(fusa)}</text>

  <rect class="inner-apps" x="234" y="384" width="732" height="100" rx="6"/>
  <text class="inner-apps-t" x="250" y="408" fill="#ffab91">{_esc(texts["apps1"])}</text>
  <text class="inner-apps-t" x="250" y="430">gateway · sensing · perception · planning</text>
  <text class="inner-apps-t" x="250" y="452">{_esc(texts["apps_principle"])}</text>

  <!-- Foxglove -->
  <rect class="side-fox" x="1020" y="210" width="164" height="280" rx="10"/>
  <image href="assets/foxglove.png" x="1030" y="218" width="144" height="230"
         preserveAspectRatio="xMidYMid meet"/>
  <text class="side-t" x="1102" y="462" text-anchor="middle" fill="#0d47a1">{_esc(texts["fox_name"])}</text>
  <text class="side-s" x="1102" y="476" text-anchor="middle">{_esc(texts["fox_sub"])}</text>
  <!-- Foxglove: shaft + traveling chevrons only (no static end tip), like inject -->
  <line x1="1000" y1="360" x2="1064" y2="360" stroke="#ffffff" stroke-width="12"/>
  <line x1="1000" y1="360" x2="1064" y2="360" stroke="#1565c0" stroke-width="6"/>
  <polygon points="1028,360 1014,348 1014,372" fill="#ffffff"/>
  <polygon points="1027,360 1015,350 1015,370" fill="#1565c0"/>
  <polygon points="1052,360 1038,348 1038,372" fill="#ffffff"/>
  <polygon points="1051,360 1039,350 1039,370" fill="#1565c0"/>

  <line x1="380" y1="570" x2="380" y2="598" stroke="#2e7d32" stroke-width="2.5"/>
  <text class="small" x="392" y="588" fill="#2e7d32">{_esc(texts["tap"])}</text>
  <line x1="820" y1="598" x2="820" y2="570" stroke="#c62828" stroke-width="2.5"/>
  <text class="small" x="832" y="588" fill="#c62828">{_esc(texts["inject"])}</text>

  <rect class="gmt" x="214" y="608" width="772" height="140" rx="8"/>
  <text class="gmt-brand" x="600" y="634" text-anchor="middle">{_esc(texts["gmt_name"])}</text>
  <text class="gmt-sub" x="600" y="654" text-anchor="middle">{_esc(texts["gmt_sub"])}</text>
  <text class="small" x="244" y="678">{_esc(gmt_l[0])}</text>
  <text class="small" x="620" y="678">{_esc(gmt_r[0])}</text>
  <text class="small" x="244" y="696">{_esc(gmt_l[1])}</text>
  <text class="small" x="620" y="696">{_esc(gmt_r[1])}</text>
  <text class="small" x="244" y="714">{_esc(gmt_l[2])}</text>
  <text class="small" x="620" y="714">{_esc(gmt_r[2])}</text>
  <text class="small" x="244" y="732">{_esc(gmt_l[3])}</text>
  <text class="small" x="620" y="732">{_esc(gmt_r[3])}</text>
</svg>
"""
    out.write_text(body, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KiB)")


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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--en",
        action="store_true",
        help="also write Giraffe_Flow.en.gif/.svg (after ZH is approved)",
    )
    args = ap.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    save_gif(ZH, ROOT / "Giraffe_Flow.gif")
    write_svg(
        ZH,
        ROOT / "Giraffe_Flow.svg",
        aria="Giraffe Flow：CARLA → gf-config / GIRAFFE 模块 → Foxglove · GMT",
    )
    if args.en:
        save_gif(EN, ROOT / "Giraffe_Flow.en.gif")
        write_svg(
            EN,
            ROOT / "Giraffe_Flow.en.svg",
            aria="Giraffe Flow: CARLA → gf-config / GIRAFFE modules → Foxglove · GMT",
        )


if __name__ == "__main__":
    main()
