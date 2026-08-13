"""TSR / ISA: speed limit."""

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
    del pygame, band_y, band_h
    font = fonts["md"]
    white = colors["white"]
    mute = colors["mute"]
    if st.limit_kph is None:
        lim, col = "--", mute
    else:
        lim, col = str(int(round(st.limit_kph))), white
    display.blit(font.render(f"LIMIT {lim}", True, col), (420, main_y - 10))
