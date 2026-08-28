"""Place / spawn actors — pose (+ at-rest). No constant-velocity IC / case branches.

``keep_ego=True`` (batch natural continue): keep hero pose & velocity; only
reposition lead/props relative to the current ego. Giraffe owns motion.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from spawn.pick import (
    offset_transform,
    pick_curve_transform,
    pick_follow_transforms,
    pick_lead_ahead_of,
    tf_on_lane,
)
from spawn.roles import (
    ROLE_EGO,
    ROLE_LEAD,
    clear_near,
    destroy_role,
    find_by_role,
    set_role,
    tick_world,
)


def _park_handbrake(actor: Any) -> None:
    """Hold park brake after cold place so slope does not roll into a barrier."""
    try:
        import carla  # type: ignore

        actor.apply_control(
            carla.VehicleControl(
                throttle=0.0,
                brake=1.0,
                steer=0.0,
                hand_brake=True,
                reverse=False,
            )
        )
    except Exception:  # noqa: BLE001
        pass


def _set_transform_at_rest(actor: Any, transform: Any, *, park: bool = False) -> None:
    """Teleport with physics-off, then zero world velocity (still not an IC speed)."""
    import carla  # type: ignore

    try:
        actor.set_simulate_physics(False)
    except Exception:  # noqa: BLE001
        pass
    try:
        actor.set_transform(transform)
    except Exception:  # noqa: BLE001
        pass
    try:
        actor.set_simulate_physics(True)
    except Exception:  # noqa: BLE001
        pass
    try:
        actor.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    try:
        actor.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
        actor.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    except Exception:  # noqa: BLE001
        pass
    if park:
        _park_handbrake(actor)


def roll_npc(actor: Any, speed_mps: float = 10.0) -> None:
    """Drop handbrake and seed world-frame speed so TM does not sit parked."""
    if actor is None:
        return
    speed = abs(float(speed_mps))
    try:
        import carla  # type: ignore

        actor.apply_control(
            carla.VehicleControl(
                throttle=0.35,
                brake=0.0,
                steer=0.0,
                hand_brake=False,
                reverse=False,
            )
        )
        fwd = actor.get_transform().get_forward_vector()
        actor.set_target_velocity(
            carla.Vector3D(float(fwd.x) * speed, float(fwd.y) * speed, 0.0)
        )
    except Exception:  # noqa: BLE001
        pass


def spawn_named(
    world: Any,
    *,
    role: str,
    transform: Any,
    bp_filter: str,
    destroy_existing: bool = True,
    clear_radius_m: float = 16.0,
    keep_yaw: bool = False,
) -> Any:
    """Spawn a role actor. Retry along the same lane only — never town-wide pop."""
    if destroy_existing:
        from spawn.roles import safe_destroy

        old = find_by_role(world, role)
        safe_destroy(old)
        tick_world(world)

    lib = world.get_blueprint_library()
    cands = list(lib.filter(bp_filter)) or list(lib.filter("vehicle.*"))
    if not cands:
        raise RuntimeError(f"no blueprints for {bp_filter!r}")

    def _snap(tf: Any) -> Any:
        try:
            import carla  # type: ignore

            wp = world.get_map().get_waypoint(
                tf.location,
                project_to_road=True,
                lane_type=carla.LaneType.Driving,
            )
            if wp is None:
                return tf
            out = tf_on_lane(wp)
            if keep_yaw:
                out.rotation.yaw = float(tf.rotation.yaw)
            return out
        except Exception:  # noqa: BLE001
            return tf

    attempts: list[Any] = [_snap(transform)]
    # XY only — no dz (air drop) and no map-wide spawn-point fallback (pop).
    nudges = (
        (0.0, 1.5),
        (0.0, -1.5),
        (2.0, 0.0),
        (-2.0, 0.0),
        (0.0, 3.5),
        (0.0, -3.5),
        (8.0, 0.0),
        (12.0, 0.0),
    )
    for fwd, right in nudges:
        attempts.append(_snap(offset_transform(transform, forward_m=fwd, right_m=right)))

    last_err: Optional[BaseException] = None
    radius = max(12.0, float(clear_radius_m))
    protect = {ROLE_EGO, ROLE_LEAD} - {role}
    for i, bp in enumerate(cands[:6]):
        set_role(bp, role)
        for tf in attempts:
            clear_near(world, tf.location, radius_m=radius, protect_roles=protect)
            actor = world.try_spawn_actor(bp, tf)
            if actor is not None:
                if i > 0 or tf is not attempts[0]:
                    print(
                        f"[spawn] {role} ok after nudge "
                        f"(bp={bp.id} loc=({tf.location.x:.1f},{tf.location.y:.1f}))",
                        flush=True,
                    )
                return actor
            try:
                actor = world.spawn_actor(bp, tf)
                return actor
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue

    raise RuntimeError(
        f"spawn_named role={role!r} failed (traffic/occupied). last={last_err}"
    )


def spawn_walker_at(world: Any, transform: Any, *, role: str = "vru") -> Any:
    lib = world.get_blueprint_library()
    walkers = list(lib.filter("walker.pedestrian.*"))
    if not walkers:
        raise RuntimeError("no walker blueprints")
    clear_near(
        world,
        transform.location,
        radius_m=4.0,
        protect_roles={ROLE_EGO, ROLE_LEAD},
    )
    attempts = [transform] + [
        offset_transform(transform, forward_m=f, right_m=r)
        for f, r in ((1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (2.0, 1.0))
    ]
    last_err: Optional[BaseException] = None
    for bp in walkers[:3]:
        if bp.has_attribute("role_name"):
            bp.set_attribute("role_name", role)
        for tf in attempts:
            w = world.try_spawn_actor(bp, tf)
            if w is not None:
                return w
            try:
                return world.spawn_actor(bp, tf)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
    raise RuntimeError(f"spawn_walker_at role={role!r} failed: {last_err}")


def ego_lead(
    world: Any,
    *,
    ego_tf: Any,
    lead_tf: Any,
    ego_filter: str = "vehicle.tesla.model3",
    lead_filter: str = "vehicle.audi.tt",
    keep_ego: bool = False,
    reset: bool = True,
) -> Tuple[Any, Any]:
    """Place hero + lead. keep_ego: do not teleport/zero hero (natural continue)."""
    if reset:
        destroy_role(world, ROLE_LEAD)
        if not keep_ego:
            destroy_role(world, ROLE_EGO)
        tick_world(world)

    ego = find_by_role(world, ROLE_EGO)
    if ego is None:
        clear_near(world, ego_tf.location, radius_m=18.0, protect_roles=set())
        ego = spawn_named(
            world,
            role=ROLE_EGO,
            transform=ego_tf,
            bp_filter=ego_filter,
            destroy_existing=False,
            clear_radius_m=18.0,
        )
        keep_ego = False  # cold spawn this call
    elif not keep_ego:
        _set_transform_at_rest(ego, ego_tf)
    # else: natural continue — leave ego pose & velocity alone

    lead = find_by_role(world, ROLE_LEAD)
    if lead is None:
        lead = spawn_named(
            world,
            role=ROLE_LEAD,
            transform=lead_tf,
            bp_filter=lead_filter,
            destroy_existing=False,
            clear_radius_m=16.0,
        )
    else:
        _set_transform_at_rest(lead, lead_tf, park=False)

    tick_world(world)
    # Quiet velocities after a cold place. keep_ego: leave both moving.
    try:
        import carla  # type: ignore

        if not keep_ego:
            lead.disable_constant_velocity()
            lead.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
            ego.disable_constant_velocity()
            ego.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    except Exception:  # noqa: BLE001
        pass
    tick_world(world)
    return ego, lead


def spawn_ego_lead(
    world: Any,
    *,
    lead_gap_m: float,
    ego_filter: str = "vehicle.tesla.model3",
    lead_filter: str = "vehicle.audi.tt",
    reset: bool = True,
    require_straight: bool = True,
    keep_ego: bool = False,
) -> Tuple[Any, Any]:
    """Pick follow transforms then place. keep_ego → keep hero+lead; no FOV teleport."""
    existing = find_by_role(world, ROLE_EGO) if keep_ego else None
    existing_lead = find_by_role(world, ROLE_LEAD) if keep_ego else None
    if existing is not None:
        if existing_lead is not None:
            print(
                f"[place] natural continue: keep ego id={existing.id} "
                f"lead id={existing_lead.id} (no teleport)",
                flush=True,
            )
            return existing, existing_lead
        # Need a lead but none in world: place far ahead, not in the 80 m FOV.
        gap = max(float(lead_gap_m), 90.0)
        ego_tf = existing.get_transform()
        lead_tf = pick_lead_ahead_of(world, ego_tf, lead_gap_m=gap)
        print(
            f"[place] natural continue: keep ego id={existing.id} "
            f"new lead ahead ≈{gap:.0f}m",
            flush=True,
        )
        return ego_lead(
            world,
            ego_tf=ego_tf,
            lead_tf=lead_tf,
            ego_filter=ego_filter,
            lead_filter=lead_filter,
            keep_ego=True,
            reset=reset,
        )
    ego_tf, lead_tf = pick_follow_transforms(
        world, lead_gap_m=lead_gap_m, require_straight=require_straight
    )
    return ego_lead(
        world,
        ego_tf=ego_tf,
        lead_tf=lead_tf,
        ego_filter=ego_filter,
        lead_filter=lead_filter,
        keep_ego=keep_ego and existing is not None,
        reset=reset,
    )


def spawn_ego_only(
    world: Any,
    *,
    ego_tf: Optional[Any] = None,
    ego_filter: str = "vehicle.tesla.model3",
    keep_ego: bool = False,
    reset_others: bool = True,
) -> Any:
    """Spawn/reposition hero; optionally clear lead. keep_ego → leave hero pose."""
    if reset_others and not keep_ego:
        destroy_role(world, ROLE_LEAD)
        destroy_role(world, ROLE_EGO)
        tick_world(world)

    ego = find_by_role(world, ROLE_EGO)
    if ego is not None and keep_ego:
        print(f"[place] natural continue: keep ego id={ego.id} (no teleport)", flush=True)
        tick_world(world)
        return ego

    if ego_tf is None:
        ego_tf = pick_curve_transform(world)

    if ego is None:
        ego = spawn_named(
            world,
            role=ROLE_EGO,
            transform=ego_tf,
            bp_filter=ego_filter,
            destroy_existing=False,
            clear_radius_m=18.0,
        )
    else:
        _set_transform_at_rest(ego, ego_tf)
    tick_world(world)
    return ego
