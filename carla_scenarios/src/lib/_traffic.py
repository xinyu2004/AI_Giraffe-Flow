"""Ambient live traffic (Traffic Manager) for all cases.

Density from carla.env::

  GF_TRAFFIC_DENSITY=0|1|2|3   # default 1
  GF_TRAFFIC_COUNT=N           # optional absolute override

Batch runs do **not** wipe traffic between cases — only top-up if below target
so the world feels continuous. Hero/lead/vru roles are never treated as ambient.
"""

from __future__ import annotations

import os
import random
from typing import Any, Optional

from _spawn import ROLE_EGO, ROLE_LEAD

ROLE_TRAFFIC_PREFIX = "traffic_"

# density → target live vehicles (approx, around map / corridor)
_DENSITY_COUNT = {
    0: 0,
    1: 8,
    2: 18,
    3: 32,
}

_PROTECTED_ROLES = {ROLE_EGO, ROLE_LEAD, "vru", "hazard"}


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
    """Top-up TM vehicles to density target. Never mass-despawn (natural batch)."""
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
    # Prefer ordinary cars; skip bikes if many choices.
    cars = [bp for bp in bps if "bike" not in bp.id and "bicycle" not in bp.id]
    if not cars:
        cars = bps
    if not cars:
        print(f"{log_prefix} no vehicle blueprints", flush=True)
        return have

    spawns = list(world.get_map().get_spawn_points())
    if near is not None:
        try:
            loc = near.get_location()

            def _dist(tf: Any) -> float:
                return (tf.location.x - loc.x) ** 2 + (tf.location.y - loc.y) ** 2

            spawns.sort(key=_dist)
        except Exception:  # noqa: BLE001
            random.shuffle(spawns)
    else:
        random.shuffle(spawns)

    # Avoid stacking on hero/lead
    blocked: list[Any] = []
    for role in (ROLE_EGO, ROLE_LEAD):
        from _spawn import find_by_role

        a = find_by_role(world, role)
        if a is not None:
            blocked.append(a.get_location())

    spawned = 0
    seq = have
    for tf in spawns:
        if spawned >= need:
            break
        if any(
            (tf.location.x - b.x) ** 2 + (tf.location.y - b.y) ** 2 < 36.0
            for b in blocked
        ):
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
        f"spawned=+{spawned} have={total} (no wipe between cases)",
        flush=True,
    )
    return total
