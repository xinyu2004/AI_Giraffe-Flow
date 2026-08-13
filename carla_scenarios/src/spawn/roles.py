"""Actor roles + destroy/clear helpers (no speed / IC)."""

from __future__ import annotations

from typing import Any, Optional

ROLE_EGO = "hero"
ROLE_LEAD = "lead"


def set_role(bp: Any, role: str) -> None:
    if bp.has_attribute("role_name"):
        bp.set_attribute("role_name", role)


def find_by_role(world: Any, role: str) -> Optional[Any]:
    for v in world.get_actors().filter("vehicle.*"):
        try:
            if v.attributes.get("role_name") == role:
                return v
        except Exception:  # noqa: BLE001
            continue
    return None


def safe_destroy(actor: Any) -> None:
    """Destroy actor; ignore already-gone (CARLA logs 'not found')."""
    if actor is None:
        return
    try:
        if hasattr(actor, "is_alive") and not bool(actor.is_alive):
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        actor.destroy()
    except Exception:  # noqa: BLE001
        pass


def destroy_role(world: Any, role: str) -> None:
    v = find_by_role(world, role)
    if v is None:
        return
    safe_destroy(v)


def tick_world(world: Any) -> None:
    try:
        world.tick()
    except Exception:  # noqa: BLE001
        try:
            world.wait_for_tick(1.0)
        except Exception:  # noqa: BLE001
            pass


def clear_near(
    world: Any,
    location: Any,
    *,
    radius_m: float = 8.0,
    protect_roles: Optional[set[str]] = None,
) -> int:
    """Destroy non-protected vehicles near a spawn pose (ambient TM leftovers)."""
    protect = protect_roles or {ROLE_EGO, ROLE_LEAD}
    r2 = float(radius_m) ** 2
    n = 0
    for v in list(world.get_actors().filter("vehicle.*")):
        try:
            role = str(v.attributes.get("role_name") or "")
            if role in protect:
                continue
            loc = v.get_location()
            dx = loc.x - location.x
            dy = loc.y - location.y
            dz = loc.z - location.z
            if dx * dx + dy * dy + dz * dz <= r2:
                safe_destroy(v)
                n += 1
        except Exception:  # noqa: BLE001
            continue
    if n:
        tick_world(world)
    return n
