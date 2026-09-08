#!/usr/bin/env python3
"""Heavy rain — GF_RAIN_AMOUNT, GF_RAIN_WETNESS, GF_WIPER_SPEED (0/1/2)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import main, run_session as _run_session  # noqa: E402


def run_session(carla, client, world, *, period_s, no_window, duration_s, view=None, keep_ego=False, preserve_ego=False, stop_flag=None, ensure_view=None, session=None):
    return _run_session(
        "env_heavy_rain",
        period_s,
        carla=carla,
        client=client,
        world=world,
        view=view,
        no_window=no_window,
        duration_s=duration_s,
        preset="rain",
        keep_ego=keep_ego,
        preserve_ego=preserve_ego,
        stop_flag=stop_flag,
        ensure_view=ensure_view,
        session=session,
    )


if __name__ == "__main__":
    sys.exit(main("env_heavy_rain", "rain"))
