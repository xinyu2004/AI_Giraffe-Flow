"""ACC cut-in: lead starts adjacent, merges into ego lane mid-case."""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from spawn.ic import seed_speed
from spawn.pick import pick_cut_in_transforms
from spawn.place import spawn_named
from spawn.roles import ROLE_EGO, ROLE_LEAD, destroy_role, find_by_role
from _verdict import CmdProbe, release_ego


def layout_acc_cut_in(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    gap = float(os.environ.get("GF_CUTIN_GAP_M") or "28")
    side = (os.environ.get("GF_CUTIN_SIDE") or "left").strip().lower()
    ego_tf, lead_tf, _wp = pick_cut_in_transforms(
        world, lead_gap_m=gap, side=side
    )

    destroy_role(world, ROLE_LEAD)
    if not keep_ego:
        destroy_role(world, ROLE_EGO)
    try:
        world.tick()
    except Exception:  # noqa: BLE001
        world.wait_for_tick(1.0)

    ego = find_by_role(world, ROLE_EGO)
    if ego is None:
        ego = spawn_named(
            world, role=ROLE_EGO, transform=ego_tf, bp_filter="vehicle.tesla.model3"
        )
    else:
        ego.set_transform(ego_tf)

    lead = spawn_named(
        world, role=ROLE_LEAD, transform=lead_tf, bp_filter="vehicle.audi.tt"
    )
    release_ego(carla_mod, ego)

    tm = client.get_trafficmanager()
    lead.set_autopilot(True, tm.get_port())
    try:
        tm.vehicle_percentage_speed_difference(lead, 10.0)
        tm.ignore_lights_percentage(lead, 100)
        tm.auto_lane_change(lead, True)
        tm.distance_to_leading_vehicle(lead, 5.0)
    except Exception:  # noqa: BLE001
        pass

    # Seed ego forward so ACC has something to regulate after IC.
    ego_mps = float(os.environ.get("GF_CUTIN_EGO_MPS") or "10")
    seed_speed(carla_mod, ego, ego_mps)

    print(
        f"[layout] CUT_IN side={side} gap≈{gap}m ego={ego.id} lead={lead.id}",
        flush=True,
    )
    return ego, lead, {
        "layout": "cut_in",
        "side": side,
        "gap_m": gap,
        "ic_ego_mps": ego_mps,
        "const_vel": True,
    }


def tick_cut_in_handoff(
    elapsed: float,
    ego: Any,
    lead: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    """Release constant_velocity once Giraffe commands; nudge lead lane change."""
    del lead
    if meta.get("handed_off"):
        return
    if not cmd.seen_control:
        return
    meta["handed_off"] = True
    try:
        ego.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    print(
        f"[acc_cut_in] Giraffe cmd at t={elapsed:.2f}s → release IC const_vel",
        flush=True,
    )
