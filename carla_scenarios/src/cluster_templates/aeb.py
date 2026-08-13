"""AEB / FCW: TTC + gap."""

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
    warn = colors["warn"]
    white = colors["white"]
    x, y = 420, main_y - 10
    bits: list[str] = []
    if st.ttc_s is not None:
        bits.append(f"TTC {st.ttc_s:0.1f}s")
    if st.gap_m is not None:
        bits.append(f"gap {st.gap_m:0.0f}m")
    if bits:
        display.blit(font.render("   ".join(bits), True, warn if st.ttc_s else white), (x, y))
