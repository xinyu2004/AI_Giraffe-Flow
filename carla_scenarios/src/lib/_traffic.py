"""Ambient live traffic (Traffic Manager) for all cases.

Density from carla.env::

  GF_TRAFFIC_DENSITY=0|1|2|3   # default 1
  GF_TRAFFIC_COUNT=N           # optional absolute override

Batch runs do **not** wipe traffic between cases — only top-up if below target.
New ambient must spawn on Driving lanes and never suddenly in front of ego.
Hero/lead/vru roles are never treated as ambient. Do not cull strays mid-run.
"""

from __future__ import annotations

import math
import os
import random
from typing import Any, Optional

from _spawn import ROLE_EGO, ROLE_LEAD

ROLE_TRAFFIC_PREFIX = "traffic_"

_DENSITY_COUNT = {
    0: 0,
    1: 8,
    2: 18,
    3: 32,
}

_PROTECTED_ROLES = {ROLE_EGO, ROLE_LEAD, "vru", "hazard"}
_MAX_OFF_LANE_M = 2.5


def traffic_density() -> int:
    raw = (os.environ.get("GF_TRAFFIC_DENSITY") or "1").strip()
    try:
        return max(0, min(3, int(raw)))
    except ValueError:
        return 1


def traffic_target_count() -> int:
    raw = os.environ.get("GF_TRAFFIC_COUNT")
    if raw is not None and str(raw).strip() != "":
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return int(_DENSITY_COUNT.get(traffic_density(), 8))


def _role_of(actor: Any) -> str:
    try:
        return str(actor.attributes.get("role_name") or "")
    except Exception:  # noqa: BLE001
        return ""


def _is_ambient(actor: Any) -> bool:
    role = _role_of(actor)
    if role in _PROTECTED_ROLES:
        return False
    if role.startswith(ROLE_TRAFFIC_PREFIX):
        return True
    # Unlabeled NPC left from prior session — treat as ambient stock.
    if role == "" or role == "autopilot":
        return True
    return False


def count_ambient(world: Any) -> int:
    n = 0
    for v in world.get_actors().filter("vehicle.*"):
        if _is_ambient(v):
            n += 1
    return n


def _driving_wp_at(world: Any, location: Any) -> Optional[Any]:
    import carla  # type: ignore

    try:
        wp = world.get_map().get_waypoint(
            location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:  # noqa: BLE001
        return None
    if wp is None:
        return None
    try:
        if int(wp.lane_type) != int(carla.LaneType.Driving):
            return None
    except Exception:  # noqa: BLE001
        pass
    try:
        wloc = wp.transform.location
        lat = math.hypot(
            float(location.x) - float(wloc.x), float(location.y) - float(wloc.y)
        )
        if lat > _MAX_OFF_LANE_M:
            return None
    except Exception:  # noqa: BLE001
        return None
    return wp


def _snap_spawn_to_driving(world: Any, tf: Any) -> Optional[Any]:
    """Map a CARLA spawn point onto a Driving lane; reject off-road / water-ish."""
    import carla  # type: ignore

    wp = _driving_wp_at(world, tf.location)
    if wp is None or getattr(wp, "is_junction", False):
        return None
    out = wp.transform
    out.location.z = float(out.location.z) + 0.35
    out.rotation.pitch = 0.0
    out.rotation.roll = 0.0
    out.rotation.yaw = float(wp.transform.rotation.yaw)
    # Sanity: z should stay near road (reject underwater / flying spawns)
    try:
        if abs(float(out.location.z) - float(tf.location.z)) > 8.0:
            return None
    except Exception:  # noqa: BLE001
        pass
    return out


def _on_driving_road(world: Any, actor: Any) -> bool:
    try:
        return _driving_wp_at(world, actor.get_location()) is not None
    except Exception:  # noqa: BLE001
        return False


def _in_ego_forward_cone(
    ego_tf: Any,
    spawn_loc: Any,
    *,
    ahead_m: float = 55.0,
    half_width_m: float = 4.5,
) -> bool:
    """True if spawn sits in ego's forward corridor (would 'pop' in front)."""
    try:
        el = ego_tf.location
        yaw = math.radians(float(ego_tf.rotation.yaw))
        fx, fy = math.cos(yaw), math.sin(yaw)
        dx = float(spawn_loc.x) - float(el.x)
        dy = float(spawn_loc.y) - float(el.y)
        along = dx * fx + dy * fy
        if along < 8.0 or along > ahead_m:
            return False
        lat = abs(-dx * fy + dy * fx)
        return lat < half_width_m
    except Exception:  # noqa: BLE001
        return False


def _configure_tm(tm: Any, vehicle: Any, *, density: int) -> None:
    try:
        tm.vehicle_percentage_speed_difference(vehicle, random.uniform(-5.0, 25.0))
        tm.ignore_lights_percentage(vehicle, 30.0 if density >= 2 else 10.0)
        tm.auto_lane_change(vehicle, density >= 1)
        tm.distance_to_leading_vehicle(vehicle, random.uniform(4.0, 10.0))
    except Exception:  # noqa: BLE001
        pass


def ensure_ambient_traffic(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    near: Optional[Any] = None,
    log_prefix: str = "[traffic]",
) -> int:
    """Top-up TM vehicles on Driving lanes; never spawn into ego forward cone."""
    del carla_mod

    target = traffic_target_count()
    density = traffic_density()
    have = count_ambient(world)
    if target <= 0:
        print(f"{log_prefix} density={density} target=0 (ambient off) have={have}", flush=True)
        return have
    if have >= target:
        print(
            f"{log_prefix} density={density} target={target} have={have} (ok, keep)",
            flush=True,
        )
        return have

    need = target - have
    tm = client.get_trafficmanager()
    lib = world.get_blueprint_library()
    bps = list(lib.filter("vehicle.*"))
    cars = [bp for bp in bps if "bike" not in bp.id and "bicycle" not in bp.id]
    if not cars:
        cars = bps
    if not cars:
        print(f"{log_prefix} no vehicle blueprints", flush=True)
        return have

    raw_spawns = list(world.get_map().get_spawn_points())
    # Only keep spawn poses that snap cleanly onto a Driving lane.
    spawns: list[Any] = []
    for tf in raw_spawns:
        snapped = _snap_spawn_to_driving(world, tf)
        if snapped is not None:
            spawns.append(snapped)
    if not spawns:
        # Fallback: dense waypoint sample (never raw off-road spawn points).
        try:
            for wp in world.get_map().generate_waypoints(6.0):
                if getattr(wp, "is_junction", False):
                    continue
                snapped = _snap_spawn_to_driving(world, wp.transform)
                if snapped is not None:
                    spawns.append(snapped)
        except Exception:  # noqa: BLE001
            pass
    if not spawns:
        print(f"{log_prefix} no on-road spawn poses", flush=True)
        return have

    ego_tf = None
    if near is not None:
        try:
            ego_tf = near.get_transform()
            loc = near.get_location()

            def _dist(tf: Any) -> float:
                return (tf.location.x - loc.x) ** 2 + (tf.location.y - loc.y) ** 2

            # Prefer side / behind ego — not the closest point (often ahead).
            spawns.sort(key=_dist)
            # Prefer mid-distance ring over immediate neighbors.
            mid = [s for s in spawns if 40.0**2 < _dist(s) < 120.0**2]
            near_ring = [s for s in spawns if 20.0**2 < _dist(s) <= 40.0**2]
            far = [s for s in spawns if _dist(s) >= 120.0**2]
            spawns = mid + near_ring + far + [s for s in spawns if _dist(s) <= 20.0**2]
        except Exception:  # noqa: BLE001
            random.shuffle(spawns)
            ego_tf = None
    else:
        random.shuffle(spawns)

    blocked: list[Any] = []
    for role in (ROLE_EGO, ROLE_LEAD):
        from _spawn import find_by_role

        a = find_by_role(world, role)
        if a is not None:
            blocked.append(a.get_location())
            if ego_tf is None and role == ROLE_EGO:
                try:
                    ego_tf = a.get_transform()
                except Exception:  # noqa: BLE001
                    pass

    spawned = 0
    seq = have
    skipped_cone = 0
    for tf in spawns:
        if spawned >= need:
            break
        if any(
            (tf.location.x - b.x) ** 2 + (tf.location.y - b.y) ** 2 < 36.0
            for b in blocked
        ):
            continue
        if ego_tf is not None and _in_ego_forward_cone(ego_tf, tf.location):
            skipped_cone += 1
            continue
        bp = random.choice(cars)
        if bp.has_attribute("role_name"):
            bp.set_attribute("role_name", f"{ROLE_TRAFFIC_PREFIX}{seq}")
        if bp.has_attribute("color"):
            try:
                bp.set_attribute(
                    "color", random.choice(bp.get_attribute("color").recommended_values)
                )
            except Exception:  # noqa: BLE001
                pass
        actor = world.try_spawn_actor(bp, tf)
        if actor is None:
            continue
        # Reject if physics immediately slid off-road.
        try:
            world.tick()
        except Exception:  # noqa: BLE001
            pass
        if not _on_driving_road(world, actor):
            try:
                actor.destroy()
            except Exception:  # noqa: BLE001
                pass
            continue
        try:
            actor.set_autopilot(True, tm.get_port())
            _configure_tm(tm, actor, density=density)
        except Exception:  # noqa: BLE001
            try:
                actor.destroy()
            except Exception:  # noqa: BLE001
                pass
            continue
        blocked.append(tf.location)
        seq += 1
        spawned += 1

    try:
        world.tick()
    except Exception:  # noqa: BLE001
        pass

    total = count_ambient(world)
    print(
        f"{log_prefix} density={density} target={target} "
        f"spawned=+{spawned} skip_front={skipped_cone} have={total} "
        f"(on-road; no front-pop; keep strays)",
        flush=True,
    )
    return total
