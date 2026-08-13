"""HLB: beam state placeholder."""

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
    beam = st.beam or "--"
    col = white if st.beam else mute
    display.blit(font.render(f"Beam {beam}", True, col), (420, main_y - 10))
