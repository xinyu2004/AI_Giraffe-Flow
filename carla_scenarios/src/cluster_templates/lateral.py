"""LKA / LDW / ELK / LCC: yaw (+ optional later lat offset)."""

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
    x, y = 420, main_y - 10
    parts: list[str] = []
    if st.yaw_rate_degps is not None:
        parts.append(f"yaw {st.yaw_rate_degps:0.1f}°/s")
    if parts:
        display.blit(font.render("   ".join(parts), True, white), (x, y))
