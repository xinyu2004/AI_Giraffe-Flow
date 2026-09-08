"""Lateral L2 layouts: LKA / LDW / ELK / LCC."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from spawn.ic import seed_speed
from spawn.pick import offset_transform, pick_curve_transform, pick_follow_transforms
from spawn.place import spawn_ego_only, spawn_named
from spawn.roles import ROLE_LEAD
from _verdict import CmdProbe, release_ego


def layout_lka_curve_entry(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 9.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    tf = pick_curve_transform(world, look_ahead_m=50.0, min_yaw_delta_deg=10.0)
    ego = spawn_ego_only(world, ego_tf=tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    print(f"[layout] LKA_CURVE_ENTRY ego={ego.id} v_target≈{mps} (Giraffe drives)", flush=True)
    return ego, None, {
        "layout": "lka_curve_entry",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def layout_lka_in_curve(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 8.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    tf = pick_curve_transform(world, look_ahead_m=35.0, min_yaw_delta_deg=15.0)
    ego = spawn_ego_only(world, ego_tf=tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    print(f"[layout] LKA_IN_CURVE ego={ego.id} (Giraffe drives)", flush=True)
    return ego, None, {
        "layout": "lka_in_curve",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def layout_ldw_drift(
    session: Any,
    *,
    keep_ego: bool = False,
    offset_m: float = 0.6,
    ego_mps: float = 8.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    ego_tf, _ = pick_follow_transforms(world, lead_gap_m=20.0)
    off = float(offset_m)
    ego_tf = offset_transform(ego_tf, right_m=off)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    print(f"[layout] LDW_DRIFT offset≈{off}m ego={ego.id} (Giraffe drives)", flush=True)
    return ego, None, {
        "layout": "ldw_drift",
        "offset_m": off,
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def layout_elk_overshoot(
    session: Any,
    *,
    keep_ego: bool = False,
    offset_m: float = 0.9,
    ego_mps: float = 9.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    ego_tf, neighbor_tf = pick_follow_transforms(world, lead_gap_m=18.0)
    off = float(offset_m)
    ego_tf = offset_transform(ego_tf, right_m=off)
    neighbor_tf = offset_transform(neighbor_tf, right_m=-3.5)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    neighbor = spawn_named(
        world,
        role=ROLE_LEAD,
        transform=neighbor_tf,
        bp_filter="vehicle.audi.tt",
    )
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    seed_speed(carla_mod, neighbor, mps * 0.9, session=session)
    print(
        f"[layout] ELK_OVERSHOOT ego={ego.id} neighbor={neighbor.id} (Giraffe drives ego)",
        flush=True,
    )
    return ego, neighbor, {
        "layout": "elk_overshoot",
        "offset_m": off,
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def layout_lcc_straight(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 10.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    ego_tf, _ = pick_follow_transforms(world, lead_gap_m=25.0, require_straight=True)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    print(f"[layout] LCC_STRAIGHT ego={ego.id} (Giraffe drives)", flush=True)
    return ego, None, {
        "layout": "lcc_straight",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def tick_lateral_handoff(
    elapsed: float,
    ego: Any,
    _target: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    del ego
    if meta.get("handed_off") or not cmd.seen_control:
        return
    meta["handed_off"] = True
    print(f"[layout] lateral Giraffe cmd at t={elapsed:.2f}s", flush=True)
