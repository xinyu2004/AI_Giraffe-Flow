"""Lateral L2 layouts: LKA / LDW / ELK / LCC."""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from spawn.ic import seed_speed
from spawn.pick import offset_transform, pick_curve_transform, pick_follow_transforms
from spawn.place import spawn_ego_only, spawn_named
from spawn.roles import ROLE_LEAD
from _verdict import CmdProbe, release_ego


def _seed_ego_speed(carla_mod: Any, ego: Any, mps: float) -> None:
    seed_speed(carla_mod, ego, mps)


def layout_lka_curve_entry(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    del client
    tf = pick_curve_transform(world, look_ahead_m=50.0, min_yaw_delta_deg=10.0)
    ego = spawn_ego_only(world, ego_tf=tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego)
    mps = float(os.environ.get("GF_LKA_EGO_MPS") or "9")
    _seed_ego_speed(carla_mod, ego, mps)
    print(f"[layout] LKA_CURVE_ENTRY ego={ego.id} v≈{mps}", flush=True)
    return ego, None, {
        "layout": "lka_curve_entry",
        "ego_mps": mps,
        "const_vel": True,
    }


def layout_lka_in_curve(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    del client
    tf = pick_curve_transform(world, look_ahead_m=35.0, min_yaw_delta_deg=15.0)
    ego = spawn_ego_only(world, ego_tf=tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego)
    mps = float(os.environ.get("GF_LKA_EGO_MPS") or "8")
    _seed_ego_speed(carla_mod, ego, mps)
    print(f"[layout] LKA_IN_CURVE ego={ego.id}", flush=True)
    return ego, None, {
        "layout": "lka_in_curve",
        "ego_mps": mps,
        "const_vel": True,
    }


def layout_ldw_drift(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    del client
    ego_tf, _ = pick_follow_transforms(world, lead_gap_m=20.0)
    # Bias toward lane edge as IC.
    off = float(os.environ.get("GF_LDW_OFFSET_M") or "0.6")
    ego_tf = offset_transform(ego_tf, right_m=off)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego)
    mps = float(os.environ.get("GF_LDW_EGO_MPS") or "8")
    _seed_ego_speed(carla_mod, ego, mps)
    print(f"[layout] LDW_DRIFT offset≈{off}m ego={ego.id}", flush=True)
    return ego, None, {
        "layout": "ldw_drift",
        "offset_m": off,
        "ego_mps": mps,
        "const_vel": True,
    }


def layout_elk_overshoot(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    del client
    ego_tf, neighbor_tf = pick_follow_transforms(world, lead_gap_m=18.0)
    off = float(os.environ.get("GF_ELK_OFFSET_M") or "0.9")
    ego_tf = offset_transform(ego_tf, right_m=off)
    neighbor_tf = offset_transform(neighbor_tf, right_m=-3.5)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    neighbor = spawn_named(
        world,
        role=ROLE_LEAD,
        transform=neighbor_tf,
        bp_filter="vehicle.audi.tt",
    )
    release_ego(carla_mod, ego)
    mps = float(os.environ.get("GF_ELK_EGO_MPS") or "9")
    _seed_ego_speed(carla_mod, ego, mps)
    seed_speed(carla_mod, neighbor, mps * 0.9)
    print(
        f"[layout] ELK_OVERSHOOT ego={ego.id} neighbor={neighbor.id}",
        flush=True,
    )
    return ego, neighbor, {
        "layout": "elk_overshoot",
        "offset_m": off,
        "ego_mps": mps,
        "const_vel": True,
    }


def layout_lcc_straight(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    del client
    ego_tf, _ = pick_follow_transforms(world, lead_gap_m=25.0, require_straight=True)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego)
    mps = float(os.environ.get("GF_LCC_EGO_MPS") or "10")
    _seed_ego_speed(carla_mod, ego, mps)
    print(f"[layout] LCC_STRAIGHT ego={ego.id}", flush=True)
    return ego, None, {
        "layout": "lcc_straight",
        "ego_mps": mps,
        "const_vel": True,
    }


def tick_lateral_handoff(
    elapsed: float,
    ego: Any,
    _target: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    if meta.get("handed_off") or not cmd.seen_control:
        return
    if not meta.get("const_vel"):
        return
    meta["handed_off"] = True
    try:
        ego.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    print(f"[layout] lateral handoff t={elapsed:.2f}s", flush=True)
