"""ACC cut-in: lead starts adjacent, merges into ego lane mid-case."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from spawn.pick import pick_cut_in_transforms
from spawn.place import reseat_lead_relative, roll_npc, spawn_named
from spawn.roles import ROLE_EGO, ROLE_LEAD, destroy_role, find_by_role, tick_world
from _verdict import CmdProbe, release_ego


def _arm_cut_in_tm(session: Any, lead: Any) -> None:
    tm = session.tm
    session.ap_on(lead)
    try:
        tm.vehicle_percentage_speed_difference(lead, 10.0)
        tm.ignore_lights_percentage(lead, 100)
        tm.auto_lane_change(lead, True)
        tm.distance_to_leading_vehicle(lead, 5.0)
    except Exception:  # noqa: BLE001
        pass
    roll_npc(lead, 10.0)


def layout_acc_cut_in(
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 28.0,
    side: str = "left",
    ego_mps: float = 10.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    gap = float(gap_m)
    side_l = (side or "left").strip().lower()
    lat = 3.5 if side_l != "right" else -3.5

    if keep_ego:
        ego = find_by_role(world, ROLE_EGO)
        if ego is not None:
            release_ego(carla_mod, ego, session=session)
            lead = reseat_lead_relative(
                world,
                ego,
                session=session,
                forward_m=gap,
                right_m=lat,
                lead_filter="vehicle.audi.tt",
                park=False,
                clear_radius_m=4.0,
            )
            _arm_cut_in_tm(session, lead)
            print(
                f"[layout] CUT_IN keep_ego: reseat lead side={side_l} gap≈{gap}m "
                f"ego={ego.id} lead={lead.id}",
                flush=True,
            )
            return ego, lead, {
                "layout": "cut_in",
                "side": side_l,
                "gap_m": gap,
                "ic_ego_mps": float(ego_mps),
                "const_vel": False,
                "ic": "giraffe_only",
                "keep_ego": True,
            }

    ego_tf, lead_tf, _wp = pick_cut_in_transforms(
        world, lead_gap_m=gap, side=side_l
    )
    destroy_role(world, ROLE_LEAD)
    destroy_role(world, ROLE_EGO)
    tick_world(world)

    ego = spawn_named(
        world, role=ROLE_EGO, transform=ego_tf, bp_filter="vehicle.tesla.model3"
    )
    lead = spawn_named(
        world,
        role=ROLE_LEAD,
        transform=lead_tf,
        bp_filter="vehicle.audi.tt",
        clear_radius_m=4.0,
    )
    release_ego(carla_mod, ego, session=session)
    _arm_cut_in_tm(session, lead)

    print(
        f"[layout] CUT_IN side={side_l} gap≈{gap}m ego={ego.id} lead={lead.id} "
        f"(Giraffe drives ego)",
        flush=True,
    )
    return ego, lead, {
        "layout": "cut_in",
        "side": side_l,
        "gap_m": gap,
        "ic_ego_mps": float(ego_mps),
        "const_vel": False,
        "ic": "giraffe_only",
    }


def tick_cut_in_handoff(
    elapsed: float,
    ego: Any,
    lead: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    del ego, lead
    if meta.get("handed_off") or not cmd.seen_control:
        return
    meta["handed_off"] = True
    print(f"[acc_cut_in] Giraffe cmd at t={elapsed:.2f}s", flush=True)
