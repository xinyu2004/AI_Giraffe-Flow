"""Perception atoms (TSR). Ego motion is Giraffe-only."""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from spawn.pick import offset_transform, pick_follow_transforms
from spawn.place import spawn_ego_only
from _verdict import CmdProbe, release_ego


def layout_tsr_speed_limit(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    """Place ego on straight; optional static prop as speed-sign stand-in."""
    del client
    ego_tf, ahead = pick_follow_transforms(world, lead_gap_m=35.0, require_straight=True)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego)
    limit = float(os.environ.get("GF_TSR_LIMIT_KPH") or "60")
    prop = None
    try:
        lib = world.get_blueprint_library()
        cands = lib.filter("*speed*") or lib.filter("static.prop.*")
        if cands:
            bp = cands[0]
            sign_tf = offset_transform(ahead, right_m=3.0)
            prop = world.try_spawn_actor(bp, sign_tf)
    except Exception:  # noqa: BLE001
        prop = None
    mps = float(os.environ.get("GF_TSR_EGO_MPS") or "12")
    print(
        f"[layout] TSR_SPEED_LIMIT ego={ego.id} limit_kph={limit} "
        f"prop={getattr(prop, 'id', None)} (Giraffe drives)",
        flush=True,
    )
    return ego, None, {
        "layout": "tsr_speed_limit",
        "speed_limit_kph": limit,
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
        "prop_id": getattr(prop, "id", None),
    }


def tick_perception_handoff(
    elapsed: float,
    ego: Any,
    _t: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    del ego
    if meta.get("handed_off") or not cmd.seen_control:
        return
    meta["handed_off"] = True
    print(f"[layout] perception Giraffe cmd at t={elapsed:.2f}s", flush=True)
