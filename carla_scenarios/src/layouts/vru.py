"""VRU (pedestrian / bicycle) AEB layouts."""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

from spawn.ic import aeb_ego_seed, closing_along_heading
from spawn.pick import offset_transform
from spawn.place import (
    reseat_lead_relative,
    spawn_ego_lead,
    spawn_ego_only,
    spawn_named,
    spawn_walker_at,
)
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


def _spawn_ped_target(
    session: Any,
    ego: Any,
    *,
    gap_m: float,
    lat_m: float,
    ped_speed: float,
) -> tuple[Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    ego_tf = ego.get_transform()
    ped_tf = offset_transform(ego_tf, forward_m=gap_m * 0.7, right_m=lat_m)
    right = ego_tf.get_right_vector()
    into_road_x, into_road_y = -float(right.x), -float(right.y)
    ped_tf.rotation.yaw = math.degrees(math.atan2(into_road_y, into_road_x))

    destroy_role(world, ROLE_LEAD)
    try:
        for w in world.get_actors().filter("walker.*"):
            if (w.attributes.get("role_name") or "") == "vru":
                safe_destroy(w)
    except Exception:  # noqa: BLE001
        pass
    tick_world(world)

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
        "vru_kind": "walker" if is_walker else "bike_fallback",
        "vru_dir_x": into_road_x,
        "vru_dir_y": into_road_y,
        "vru_speed": ped_speed,
    }
    if is_walker:
        _apply_walker_cross(carla_mod, target, meta)
    else:
        closing_along_heading(
            carla_mod, target, max(ped_speed, 1.2), session=session
        )
    return target, meta


def layout_aeb_pedestrian(
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 28.0,
    ego_mps: float = 8.0,
    lat_m: float = 5.0,
    ped_speed: float = 1.4,
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    gap_m = float(gap_m)
    ego_mps = float(ego_mps)
    lat_m = float(lat_m)
    ped_speed = float(ped_speed)

    if keep_ego:
        ego = spawn_ego_only(world, keep_ego=True, reset_others=False)
        release_ego(carla_mod, ego, session=session)
        target, vru_meta = _spawn_ped_target(
            session, ego, gap_m=gap_m, lat_m=lat_m, ped_speed=ped_speed
        )
        meta = {
            "layout": "aeb_pedestrian",
            "gap_m": gap_m,
            "ego_mps": ego_mps,
            "keep_ego": True,
            "const_vel": False,
            "ic": "giraffe_only",
            **vru_meta,
        }
        tick_world(world)
        if vru_meta["vru_kind"] == "walker":
            _apply_walker_cross(carla_mod, target, meta)
        print(
            f"[layout] PED_CROSS keep_ego: reseat VRU gap≈{gap_m} lat≈{lat_m} "
            f"ego={ego.id} vru={target.id} kind={meta['vru_kind']}",
            flush=True,
        )
        return ego, target, meta

    ego, lead_dummy = spawn_ego_lead(
        world,
        lead_gap_m=gap_m,
        reset=True,
        require_straight=True,
        keep_ego=False,
    )
    safe_destroy(lead_dummy)
    destroy_role(world, ROLE_LEAD)
    release_ego(carla_mod, ego, session=session)

    target, vru_meta = _spawn_ped_target(
        session, ego, gap_m=gap_m, lat_m=lat_m, ped_speed=ped_speed
    )
    meta = {
        "layout": "aeb_pedestrian",
        "gap_m": gap_m,
        "ego_mps": ego_mps,
        "ic": "aeb_ego_seed",
        **vru_meta,
    }

    aeb_ego_seed(True)
    try:
        const_on = closing_along_heading(
            carla_mod, ego, ego_mps, session=session
        )
    finally:
        aeb_ego_seed(False)
    meta["const_vel"] = const_on
    tick_world(world)
    if vru_meta["vru_kind"] == "walker":
        _apply_walker_cross(carla_mod, target, meta)

    print(
        f"[layout] PED_CROSS gap≈{gap_m} lat≈{lat_m} "
        f"ego={ego.id} vru={target.id} kind={meta['vru_kind']} "
        f"ic_ego=aeb_ego_seed",
        flush=True,
    )
    return ego, target, meta


def layout_aeb_bicycle(
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 30.0,
    ego_mps: float = 10.0,
    bike_mps: float = 4.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    gap_m = float(gap_m)
    ego_mps = float(ego_mps)
    bike_mps = float(bike_mps)

    if keep_ego:
        ego = spawn_ego_only(world, keep_ego=True, reset_others=False)
        release_ego(carla_mod, ego, session=session)
        bike = reseat_lead_relative(
            world,
            ego,
            session=session,
            forward_m=gap_m,
            right_m=0.8,
            lead_filter="vehicle.bh.crossbike",
            park=False,
        )
        closing_along_heading(carla_mod, bike, bike_mps, session=session)
        print(
            f"[layout] BICYCLE keep_ego: reseat bike gap≈{gap_m} "
            f"ego={ego.id} bike={bike.id}",
            flush=True,
        )
        return ego, bike, {
            "layout": "aeb_bicycle",
            "gap_m": gap_m,
            "ego_mps": ego_mps,
            "bike_mps": bike_mps,
            "keep_ego": True,
            "const_vel": False,
            "ic": "giraffe_only",
            "vru_kind": "bicycle",
        }

    ego, _ = spawn_ego_lead(
        world,
        lead_gap_m=gap_m,
        reset=True,
        require_straight=True,
        keep_ego=False,
    )
    destroy_role(world, ROLE_LEAD)
    release_ego(carla_mod, ego, session=session)

    ego_tf = ego.get_transform()
    bike_tf = offset_transform(ego_tf, forward_m=gap_m, right_m=0.8)
    bike_tf.rotation.yaw = ego_tf.rotation.yaw
    bike = spawn_named(
        world,
        role=ROLE_LEAD,
        transform=bike_tf,
        bp_filter="vehicle.bh.crossbike",
    )
    session.ap_off(bike)

    closing_along_heading(carla_mod, bike, bike_mps, session=session)
    aeb_ego_seed(True)
    try:
        const_on = closing_along_heading(
            carla_mod, ego, ego_mps, session=session
        )
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
    print(
        f"[layout] VRU Giraffe cmd at t={elapsed:.2f}s → release AEB ego seed",
        flush=True,
    )
