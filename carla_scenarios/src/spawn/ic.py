"""Named case IC profiles.

Cold start (first case / single-run): place at rest, then named IC may seed speed.
Batch natural continue (``set_natural_continue(True)``): **never** touch hero motion —
Giraffe/planning owns control; IC only rearranges lead/props/ambient.

Profiles:

- ``release_only`` — follow / ACC (no constant velocity)
- ``closing_toward_lead`` — vehicle-vehicle AEB (road + toward lead)
- ``closing_along_heading`` — map road forward (VRU ego / same-dir bike)
- ``closing_along_pose`` — current actor yaw (cross-traffic only)
- ``seed_speed`` — lateral / env light road forward
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

from spawn.roles import ROLE_EGO, tick_world

# Batch mid-suite: skip any IC that would steer/brake/seed the hero.
_NATURAL_CONTINUE = False


def set_natural_continue(enabled: bool) -> None:
    global _NATURAL_CONTINUE
    _NATURAL_CONTINUE = bool(enabled)


def natural_continue() -> bool:
    return _NATURAL_CONTINUE


def _is_hero(vehicle: Any) -> bool:
    try:
        return str(vehicle.attributes.get("role_name") or "") == ROLE_EGO
    except Exception:  # noqa: BLE001
        return False


def _skip_hero_motion_ic(vehicle: Any, *, profile: str) -> bool:
    if not _NATURAL_CONTINUE or not _is_hero(vehicle):
        return False
    print(
        f"[ic] skip {profile} on hero (natural continue; Giraffe drives)",
        flush=True,
    )
    return True


def reset_vehicle_motion(vehicle: Any) -> None:
    import carla  # type: ignore

    try:
        vehicle.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    try:
        vehicle.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    except Exception:  # noqa: BLE001
        pass
    try:
        vehicle.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    except Exception:  # noqa: BLE001
        pass


def _xy_forward(vehicle: Any) -> Tuple[float, float]:
    fwd = vehicle.get_transform().get_forward_vector()
    mag = math.hypot(float(fwd.x), float(fwd.y))
    if mag < 1e-6:
        return 1.0, 0.0
    return float(fwd.x) / mag, float(fwd.y) / mag


def _xy_toward(vehicle: Any, other: Any) -> Tuple[float, float]:
    try:
        a = vehicle.get_location()
        b = other.get_location()
        dx = float(b.x) - float(a.x)
        dy = float(b.y) - float(a.y)
        mag = math.hypot(dx, dy)
        if mag >= 0.5:
            return dx / mag, dy / mag
    except Exception:  # noqa: BLE001
        pass
    return _xy_forward(vehicle)


def _along_track_mps(vehicle: Any, fx: float, fy: float) -> float:
    try:
        v = vehicle.get_velocity()
        return float(v.x) * fx + float(v.y) * fy
    except Exception:  # noqa: BLE001
        return 0.0


def _speed_xy(vehicle: Any) -> float:
    try:
        v = vehicle.get_velocity()
        return math.hypot(float(v.x), float(v.y))
    except Exception:  # noqa: BLE001
        return 0.0


def _snap_road_yaw(vehicle: Any) -> Tuple[float, float]:
    """Align actor yaw to driving-lane waypoint; return unit forward XY."""
    import carla  # type: ignore

    world = vehicle.get_world()
    try:
        wp = world.get_map().get_waypoint(
            vehicle.get_location(),
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:  # noqa: BLE001
        wp = None
    if wp is not None:
        tf = wp.transform
        try:
            tf.location.z = max(
                float(tf.location.z) + 0.2, float(vehicle.get_location().z)
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            vehicle.set_simulate_physics(False)
            vehicle.set_transform(tf)
            vehicle.set_simulate_physics(True)
        except Exception:  # noqa: BLE001
            try:
                vehicle.set_transform(tf)
            except Exception:  # noqa: BLE001
                pass
        try:
            tick_world(world)
        except Exception:  # noqa: BLE001
            pass
    return _xy_forward(vehicle)


def release_only(carla_mod: Any, ego: Any) -> None:
    """Follow-family IC: autopilot off; park brake on until Giraffe drives.

    hand_brake=True avoids Town slope roll-into-barrier when SIL is absent.
    VehicleControl from bridge/planning overrides once cmd arrives.
    """
    if _skip_hero_motion_ic(ego, profile="release_only"):
        return
    try:
        ego.set_autopilot(False)
    except Exception:  # noqa: BLE001
        pass
    try:
        ego.apply_control(
            carla_mod.VehicleControl(
                throttle=0.0,
                brake=1.0,
                steer=0.0,
                hand_brake=True,
                reverse=False,
            )
        )
    except Exception:  # noqa: BLE001
        pass
    reset_vehicle_motion(ego)


def _enable_along(
    carla_mod: Any,
    vehicle: Any,
    speed_mps: float,
    fx: float,
    fy: float,
    *,
    profile: str,
) -> bool:
    """Drive +body-forward. CARLA ``enable_constant_velocity`` is **local** space.

    Passing world-frame (fx,fy)*speed as local XYZ was the ACC→AEB reverse bug:
    when world-forward.x < 0, local x became negative → reverse at |speed|.
    """
    if _skip_hero_motion_ic(vehicle, profile=profile):
        return False
    del fx, fy  # yaw must already face the intended direction; use body +X.
    speed = abs(float(speed_mps))
    world = vehicle.get_world()
    try:
        vehicle.set_autopilot(False)
        vehicle.apply_control(
            carla_mod.VehicleControl(
                throttle=0.0,
                brake=0.0,
                steer=0.0,
                hand_brake=False,
                reverse=False,
            )
        )
    except Exception:  # noqa: BLE001
        pass

    # World-frame target (set_target_velocity) + local-frame constant velocity.
    fwd = vehicle.get_transform().get_forward_vector()
    world_vel = carla_mod.Vector3D(
        float(fwd.x) * speed, float(fwd.y) * speed, 0.0
    )
    local_vel = carla_mod.Vector3D(speed, 0.0, 0.0)
    const_on = False
    try:
        vehicle.set_target_velocity(world_vel)
    except Exception:  # noqa: BLE001
        pass
    try:
        vehicle.enable_constant_velocity(local_vel)
        const_on = True
    except Exception:  # noqa: BLE001
        const_on = False
    for _ in range(2):
        try:
            tick_world(world)
        except Exception:  # noqa: BLE001
            break
    bx, by = _xy_forward(vehicle)
    along = _along_track_mps(vehicle, bx, by)
    spd = _speed_xy(vehicle)
    ok = along >= max(1.0, 0.35 * speed)
    print(
        f"[ic] {profile}: along={along:.2f} |v|={spd:.2f} const={int(const_on)} "
        f"{'ok' if ok else 'WARN'}",
        flush=True,
    )
    return const_on and ok


def closing_along_heading(
    carla_mod: Any, vehicle: Any, speed_mps: float
) -> bool:
    """IC along map road forward."""
    if _skip_hero_motion_ic(vehicle, profile="closing_along_heading"):
        return False
    fx, fy = _snap_road_yaw(vehicle)
    return _enable_along(
        carla_mod, vehicle, speed_mps, fx, fy, profile="closing_along_heading"
    )


def closing_along_pose(
    carla_mod: Any, vehicle: Any, speed_mps: float
) -> bool:
    """IC along current actor yaw (cross-traffic). No road snap."""
    if _skip_hero_motion_ic(vehicle, profile="closing_along_pose"):
        return False
    fx, fy = _xy_forward(vehicle)
    return _enable_along(
        carla_mod, vehicle, speed_mps, fx, fy, profile="closing_along_pose"
    )


def closing_toward_lead(
    carla_mod: Any,
    vehicle: Any,
    speed_mps: float,
    lead: Any,
) -> bool:
    """IC toward lead if mostly along-road; else road forward."""
    if _skip_hero_motion_ic(vehicle, profile="closing_toward_lead"):
        return False
    if lead is None:
        raise ValueError("closing_toward_lead requires lead actor")
    fx, fy = _snap_road_yaw(vehicle)
    tx, ty = _xy_toward(vehicle, lead)
    if tx * fx + ty * fy >= 0.5:
        fx, fy = tx, ty
        try:
            tf = vehicle.get_transform()
            tf.rotation.yaw = math.degrees(math.atan2(fy, fx))
            vehicle.set_simulate_physics(False)
            vehicle.set_transform(tf)
            vehicle.set_simulate_physics(True)
            tick_world(vehicle.get_world())
        except Exception:  # noqa: BLE001
            pass
        fx, fy = _xy_forward(vehicle)
    return _enable_along(
        carla_mod, vehicle, speed_mps, fx, fy, profile="closing_toward_lead"
    )


def seed_speed(carla_mod: Any, vehicle: Any, speed_mps: float) -> bool:
    """Lateral / env light road-forward IC."""
    return closing_along_heading(carla_mod, vehicle, speed_mps)


def set_forward_speed(carla_mod: Any, vehicle: Any, speed_mps: float) -> None:
    if _skip_hero_motion_ic(vehicle, profile="set_forward_speed"):
        return
    speed = abs(float(speed_mps))
    fx, fy = _xy_forward(vehicle)
    vel = carla_mod.Vector3D(fx * speed, fy * speed, 0.0)
    try:
        vehicle.set_target_velocity(vel)
    except Exception:  # noqa: BLE001
        pass


# Compat: residue clearing moved to spawn.boundary
def settle_keep_ego(
    vehicle: Any,
    carla_mod: Optional[Any] = None,
    *,
    ticks: int = 3,
) -> None:
    """Deprecated — use spawn.boundary.sanitize_keep_ego."""
    del carla_mod, ticks
    from spawn.boundary import sanitize_keep_ego

    if vehicle is None:
        return
    sanitize_keep_ego(vehicle.get_world(), vehicle)


def handoff_keep_ego(ego: Any) -> None:
    """Deprecated alias → spawn.boundary.sanitize_keep_ego."""
    from spawn.boundary import handoff_keep_ego as _h

    _h(ego)


def freeze_motion(*actors: Any, carla_mod: Optional[Any] = None) -> None:
    """Brake helpers for layouts; AtomCase uses _verdict.freeze_actors."""
    import carla as _c  # type: ignore

    mod = carla_mod or _c
    for actor in actors:
        if actor is None:
            continue
        reset_vehicle_motion(actor)
        try:
            actor.apply_control(
                mod.VehicleControl(
                    throttle=0.0,
                    brake=1.0,
                    steer=0.0,
                    hand_brake=True,
                    reverse=False,
                )
            )
        except Exception:  # noqa: BLE001
            try:
                actor.apply_control(mod.WalkerControl(speed=0.0))
            except Exception:  # noqa: BLE001
                pass


closing_const_fwd = closing_along_heading
enable_constant_forward = closing_along_heading
