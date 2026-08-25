"""Removed: carla_truth.json file IPC is deleted.

Perception/truth for SIL is GfChannel ``fake_perc`` from giraffe_client.
HUD fields are computed in-process by scenario_client.
"""

from __future__ import annotations

raise ImportError(
    "_truth.write_truth removed — no carla_truth.json; use GfChannel fake_perc / in-process HUD"
)
