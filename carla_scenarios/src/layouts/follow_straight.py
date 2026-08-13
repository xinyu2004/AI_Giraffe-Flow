"""Straight-road follow layout for ACC (and similar longitudinal cases).

Compose: pick+place via spawn.place.spawn_ego_lead, then ic.release_only.
Does not import closing IC. Batch residue is owned by spawn.boundary.
"""

from __future__ import annotations

from typing import Any, Tuple

from spawn.ic import release_only
from spawn.place import spawn_ego_lead
from spawn.roles import ROLE_EGO, ROLE_LEAD


def layout_acc_follow(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    lead_gap_m: float = 32.0,
    lead_speed_diff_pct: float = 25.0,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    """Spawn/place ego+lead on straight; release_only IC; lead TM cruise slower."""
    ego, lead = spawn_ego_lead(
        world,
        lead_gap_m=lead_gap_m,
        reset=True,
        require_straight=True,
        keep_ego=keep_ego,
    )
    release_only(carla_mod, ego)

    tm = client.get_trafficmanager()
    lead.set_autopilot(True, tm.get_port())
    try:
        tm.vehicle_percentage_speed_difference(lead, float(lead_speed_diff_pct))
        tm.ignore_lights_percentage(lead, 100)
        tm.auto_lane_change(lead, False)
    except Exception:  # noqa: BLE001
        pass

    print(
        f"[layout] STRAIGHT_FOLLOW gap≈{lead_gap_m}m "
        f"ego={ROLE_EGO} id={ego.id} lead={ROLE_LEAD} id={lead.id} "
        f"(ic=release_only)",
        flush=True,
    )
    return ego, lead, {
        "layout": "straight_follow",
        "gap_m": float(lead_gap_m),
        "ic": "release_only",
    }
