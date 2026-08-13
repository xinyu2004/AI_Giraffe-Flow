"""Fallback template: no feature-specific slots (suite unknown / new case)."""

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
    del pygame, display, fonts, colors, st, band_y, band_h, main_y
    # Skeleton only — chrome drawn by _instrument.draw_cluster.
