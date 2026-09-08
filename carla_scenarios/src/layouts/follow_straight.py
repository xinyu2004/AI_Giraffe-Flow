"""Straight-road follow layout for ACC (and similar longitudinal cases)."""

from __future__ import annotations

from typing import Any, Tuple

from spawn.ic import release_only
from spawn.place import roll_npc, spawn_ego_lead
from spawn.roles import ROLE_EGO, ROLE_LEAD


def layout_acc_follow(
    session: Any,
    *,
    lead_gap_m: float = 20.0,
    lead_speed_diff_pct: float = 15.0,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    """Spawn/place ego+lead on straight; release_only IC; lead TM cruise slower."""
    world = session.world
    carla_mod = session.carla
    ego, lead = spawn_ego_lead(
        world,
        lead_gap_m=lead_gap_m,
        reset=True,
        require_straight=True,
        keep_ego=keep_ego,
    )
    release_only(carla_mod, ego, session=session)

    tm = session.tm
    session.ap_on(lead)
    try:
        tm.vehicle_percentage_speed_difference(lead, float(lead_speed_diff_pct))
        tm.ignore_lights_percentage(lead, 100)
        tm.auto_lane_change(lead, False)
        tm.distance_to_leading_vehicle(lead, 10.0)
    except Exception:  # noqa: BLE001
        pass
    roll_npc(lead, 10.0)

    print(
        f"[layout] STRAIGHT_FOLLOW gap≈{lead_gap_m}m "
        f"ego={ROLE_EGO} id={ego.id} lead={ROLE_LEAD} id={lead.id} "
        f"(ic=release_only lead_diff={lead_speed_diff_pct:g}%)",
        flush=True,
    )
    return ego, lead, {
        "layout": "straight_follow",
        "gap_m": float(lead_gap_m),
        "ic": "release_only",
    }
