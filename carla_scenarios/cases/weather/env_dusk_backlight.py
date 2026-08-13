#!/usr/bin/env python3
"""Low sun / backlight — GF_SUN_ALTITUDE_DEG / GF_SUN_AZIMUTH_DEG."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import main, run_session as _run_session  # noqa: E402


def run_session(carla, client, world, *, period_s, no_window, duration_s, view=None, keep_ego=False, stop_flag=None, ensure_view=None):
    return _run_session(
        "env_dusk_backlight",
        period_s,
        carla=carla,
        client=client,
        world=world,
        view=view,
        no_window=no_window,
        duration_s=duration_s,
        preset="dusk",
        keep_ego=keep_ego,
        stop_flag=stop_flag,
        ensure_view=ensure_view,
    )


if __name__ == "__main__":
    sys.exit(main("env_dusk_backlight", "dusk"))
