"""Case / combo boundary helpers.

Batch natural continue: do not sanitize-destroy for residual speed.
If the hero is *wrecked* (off-road / flipped / dead), destroy so the next case
cold-starts — continuing a guardrail crash is not a natural handoff.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

from spawn.roles import ROLE_EGO, ROLE_LEAD, destroy_role, find_by_role, tick_world

_MAX_REST_MPS = 0.35
_MAX_OFF_LANE_M = 1.6
_MAX_TILT_DEG = 20.0
_MAX_YAW_ERR_DEG = 30.0


def _yaw_delta_deg(a: float, b: float) -> float:
    d = abs(float(a) - float(b)) % 360.0
    return d if d <= 180.0 else 360.0 - d


def _speed_xy(vehicle: Any) -> float:
    try:
        v = vehicle.get_velocity()
        return math.hypot(float(v.x), float(v.y))
    except Exception:  # noqa: BLE001
        return 0.0


def _hard_stop(vehicle: Any, *, session: Any = None) -> None:
    """Stop non-driving helpers. On hero: clear const-vel only (Giraffe owns control)."""
    import carla  # type: ignore

    is_hero = False
    try:
        is_hero = str(vehicle.attributes.get("role_name") or "") == ROLE_EGO
    except Exception:  # noqa: BLE001
        pass
    try:
        vehicle.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    if session is not None:
        session.ap_off(vehicle)
    if is_hero:
        return
    try:
        vehicle.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
        vehicle.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    except Exception:  # noqa: BLE001
        pass
    try:
        vehicle.apply_control(
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


def ego_ok_for_continue(world: Any, ego: Optional[Any] = None) -> Tuple[bool, str]:
    """True if hero can be reused for the next case (on-road, upright, alive)."""
    import carla  # type: ignore

    hero = ego if ego is not None else find_by_role(world, ROLE_EGO)
    if hero is None:
        return False, "missing"
    try:
        if hasattr(hero, "is_alive") and not bool(hero.is_alive):
            return False, "dead"
    except Exception:  # noqa: BLE001
        return False, "dead"
    try:
        tf = hero.get_transform()
        if abs(float(tf.rotation.roll)) > _MAX_TILT_DEG or abs(
            float(tf.rotation.pitch)
        ) > _MAX_TILT_DEG:
            return False, "flipped"
    except Exception:  # noqa: BLE001
        return False, "pose"
    try:
        wp = world.get_map().get_waypoint(
            hero.get_location(),
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:  # noqa: BLE001
        wp = None
    if wp is None:
        return False, "off_road"
    try:
        loc = hero.get_location()
        wloc = wp.transform.location
        lat = math.hypot(float(loc.x) - float(wloc.x), float(loc.y) - float(wloc.y))
        if lat > _MAX_OFF_LANE_M:
            return False, f"off_lane_{lat:.1f}m"
        yaw_err = _yaw_delta_deg(
            float(hero.get_transform().rotation.yaw),
            float(wp.transform.rotation.yaw),
        )
        if yaw_err > _MAX_YAW_ERR_DEG:
            return False, f"yaw_{yaw_err:.0f}deg"
    except Exception:  # noqa: BLE001
        return False, "off_lane"
    return True, "ok"


def reset_wrecked_ego(world: Any, *, reason: str) -> None:
    """Drop hero+lead so the next layout cold-starts (explicit, logged)."""
    had = find_by_role(world, ROLE_EGO) is not None or find_by_role(world, ROLE_LEAD) is not None
    if not had and reason != "suite_start":
        return
    print(
        f"[boundary] clear hero/lead ({reason}) → next layout cold-starts",
        flush=True,
    )
    destroy_role(world, ROLE_LEAD)
    destroy_role(world, ROLE_EGO)
    try:
        tick_world(world)
    except Exception:  # noqa: BLE001
        pass


def sanitize_keep_ego(
    world: Any,
    ego: Optional[Any] = None,
    *,
    max_rest_mps: float = _MAX_REST_MPS,
    attempts: int = 4,
) -> bool:
    """Optional debug: try to stop hero. Never destroys for speed alone."""
    if world is None:
        return False
    hero = ego if ego is not None else find_by_role(world, ROLE_EGO)
    if hero is None:
        print("[boundary] sanitize: no hero", flush=True)
        return False

    for i in range(max(1, int(attempts))):
        _hard_stop(hero)
        try:
            tick_world(world)
        except Exception:  # noqa: BLE001
            pass
        spd = _speed_xy(hero)
        if spd <= max_rest_mps:
            print(
                f"[boundary] sanitize ok |v|={spd:.3f} m/s attempt={i + 1}",
                flush=True,
            )
            return True
        print(
            f"[boundary] sanitize still moving |v|={spd:.3f} m/s attempt={i + 1}",
            flush=True,
        )

    print(
        f"[boundary] sanitize FAILED |v|={_speed_xy(hero):.3f} "
        f"(hero kept — report FAIL upstream; no destroy)",
        flush=True,
    )
    return False


def handoff_keep_ego(ego: Any) -> None:
    """Deprecated alias."""
    if ego is None:
        return
    try:
        world = ego.get_world()
    except Exception:  # noqa: BLE001
        return
    sanitize_keep_ego(world, ego)
