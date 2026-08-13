"""ACC / follow: time-headway + gap (+ band marker)."""

from __future__ import annotations

from typing import Any


def draw_feature(
    pygame: Any,
    display: Any,
    fonts: dict[str, Any],
    colors: dict[str, Any],
    st: Any,
    *,
    band_y: int,
    band_h: int,
    main_y: int,
) -> None:
    del band_y, band_h
    font = fonts["md"]
    font_sm = fonts["sm"]
    white = colors["white"]
    mute = colors["mute"]
    accent = colors["accent"]
    warn = colors["warn"]

    # Right side of main row (after speed / SET / TGT).
    x = 420
    y = main_y
    if st.th_s is not None:
        display.blit(font.render(f"th {st.th_s:0.1f}s", True, white), (x, y - 10))
        bar_x, bar_w, bar_h = x, 160, 5
        bar_y = y + 18
        pygame.draw.rect(
            display, (50, 56, 64, 180), (bar_x, bar_y, bar_w, bar_h), border_radius=2
        )
        lo, hi = float(st.th_lo), float(st.th_hi)
        span = max(0.1, hi - lo)
        tmin, tmax = lo - 0.5 * span, hi + 0.5 * span
        ratio = max(0.0, min(1.0, (st.th_s - tmin) / max(0.1, tmax - tmin)))
        in_band = lo <= st.th_s <= hi
        mx = int(bar_x + ratio * bar_w)
        pygame.draw.circle(
            display, accent if in_band else warn, (mx, bar_y + bar_h // 2), 4
        )
        display.blit(
            font_sm.render(f"[{lo:g}…{hi:g}]", True, mute),
            (bar_x + bar_w + 8, bar_y - 4),
        )
        x2 = x + 280
    else:
        x2 = x
    if st.gap_m is not None:
        display.blit(font.render(f"gap {st.gap_m:0.0f}m", True, white), (x2, y - 10))
