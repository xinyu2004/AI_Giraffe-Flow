"""VRU (pedestrian / bicycle) AEB layouts.

Ego may use AEB-only closing seed (``aeb_ego_seed``); then Giraffe takes over.
Walker motion is refreshed every tick via ``tick_vru_handoff``.
"""

from __future__ import annotations

import math
import os
from typing import Any, Optional, Tuple

from spawn.ic import aeb_ego_seed, closing_along_heading
from spawn.pick import offset_transform
from spawn.place import spawn_ego_lead, spawn_named, spawn_walker_at
from spawn.roles import ROLE_LEAD, destroy_role, safe_destroy, tick_world
from _verdict import CmdProbe, release_ego


def _apply_walker_cross(carla_mod: Any, walker: Any, meta: dict[str, Any]) -> None:
    dx = float(meta.get("vru_dir_x") or 0.0)
    dy = float(meta.get("vru_dir_y") or 0.0)
    speed = float(meta.get("vru_speed") or 1.4)
    mag = math.hypot(dx, dy)
    if mag < 1e-6:
        return
    direction = carla_mod.Vector3D(dx / mag, dy / mag, 0.0)
    try:
        walker.apply_control(
            carla_mod.WalkerControl(direction=direction, speed=speed)
        )
    except Exception:  # noqa: BLE001
        pass


def layout_aeb_pedestrian(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    """Ego straight; pedestrian starts on the right and walks into the lane."""
    del client
    gap_m = float(os.environ.get("GF_AEB_PED_GAP_M") or "28")
    ego_mps = float(os.environ.get("GF_AEB_PED_EGO_MPS") or "8")
    lat_m = float(os.environ.get("GF_AEB_PED_LAT_M") or "5")
    ped_speed = float(os.environ.get("GF_AEB_PED_MPS") or "1.4")

    ego, lead_dummy = spawn_ego_lead(
        world,
        lead_gap_m=gap_m,
        reset=True,
        require_straight=True,
        keep_ego=keep_ego,
    )
    safe_destroy(lead_dummy)
    destroy_role(world, ROLE_LEAD)
    release_ego(carla_mod, ego)

    ego_tf = ego.get_transform()
    ped_tf = offset_transform(ego_tf, forward_m=gap_m * 0.7, right_m=lat_m)
    right = ego_tf.get_right_vector()
    into_road_x, into_road_y = -float(right.x), -float(right.y)
    ped_tf.rotation.yaw = math.degrees(math.atan2(into_road_y, into_road_x))

    is_walker = True
    try:
        target = spawn_walker_at(world, ped_tf, role="vru")
    except RuntimeError:
        is_walker = False
        target = spawn_named(
            world,
            role=ROLE_LEAD,
            transform=ped_tf,
            bp_filter="vehicle.bh.crossbike",
        )

    meta: dict[str, Any] = {
        "layout": "aeb_pedestrian",
        "gap_m": gap_m,
        "ego_mps": ego_mps,
        "ic": "aeb_ego_seed",
        "vru_kind": "walker" if is_walker else "bike_fallback",
        "vru_dir_x": into_road_x,
        "vru_dir_y": into_road_y,
        "vru_speed": ped_speed,
    }

    if is_walker:
        _apply_walker_cross(carla_mod, target, meta)
    else:
        try:
            target.set_transform(ped_tf)
        except Exception:  # noqa: BLE001
            pass
        closing_along_heading(carla_mod, target, max(ped_speed, 1.2))

    aeb_ego_seed(True)
    try:
        const_on = closing_along_heading(carla_mod, ego, ego_mps)
    finally:
        aeb_ego_seed(False)
    meta["const_vel"] = const_on
    tick_world(world)
    if is_walker:
        _apply_walker_cross(carla_mod, target, meta)

    print(
        f"[layout] PED_CROSS gap≈{gap_m} lat≈{lat_m} "
        f"ego={ego.id} vru={target.id} kind={meta['vru_kind']} "
        f"ic_ego=aeb_ego_seed",
        flush=True,
    )
    return ego, target, meta


def layout_aeb_bicycle(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    """Ego straight; bicycle ahead on-path (slow same-direction)."""
    del client
    gap_m = float(os.environ.get("GF_AEB_BIKE_GAP_M") or "30")
    ego_mps = float(os.environ.get("GF_AEB_BIKE_EGO_MPS") or "10")
    bike_mps = float(os.environ.get("GF_AEB_BIKE_MPS") or "4")

    ego, _ = spawn_ego_lead(
        world,
        lead_gap_m=gap_m,
        reset=True,
        require_straight=True,
        keep_ego=keep_ego,
    )
    destroy_role(world, ROLE_LEAD)
    release_ego(carla_mod, ego)

    ego_tf = ego.get_transform()
    bike_tf = offset_transform(ego_tf, forward_m=gap_m, right_m=0.8)
    bike_tf.rotation.yaw = ego_tf.rotation.yaw
    bike = spawn_named(
        world,
        role=ROLE_LEAD,
        transform=bike_tf,
        bp_filter="vehicle.bh.crossbike",
    )
    try:
        bike.set_autopilot(False)
    except Exception:  # noqa: BLE001
        pass

    closing_along_heading(carla_mod, bike, bike_mps)
    aeb_ego_seed(True)
    try:
        const_on = closing_along_heading(carla_mod, ego, ego_mps)
    finally:
        aeb_ego_seed(False)

    print(
        f"[layout] BICYCLE gap≈{gap_m} ego={ego.id} bike={bike.id} "
        f"bike_v≈{bike_mps} ic_ego=aeb_ego_seed",
        flush=True,
    )
    return ego, bike, {
        "layout": "aeb_bicycle",
        "gap_m": gap_m,
        "ego_mps": ego_mps,
        "bike_mps": bike_mps,
        "const_vel": const_on,
        "ic": "aeb_ego_seed",
        "vru_kind": "bicycle",
    }


def tick_vru_handoff(
    elapsed: float,
    ego: Any,
    target: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    """Keep VRU moving; release AEB ego seed once Giraffe commands."""
    import carla as _c  # type: ignore

    kind = str(meta.get("vru_kind") or "")
    if target is not None and kind == "walker":
        _apply_walker_cross(_c, target, meta)

    if meta.get("handed_off") or not cmd.seen_control:
        return
    if not meta.get("const_vel"):
        return
    meta["handed_off"] = True
    try:
        ego.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    print(f"[layout] VRU Giraffe cmd at t={elapsed:.2f}s → release AEB ego seed", flush=True)
