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
    """Destroy every vehicle with role_name==role (not just the first)."""
    for v in list(world.get_actors().filter("vehicle.*")):
        try:
            if v.attributes.get("role_name") == role:
                safe_destroy(v)
        except Exception:  # noqa: BLE001
            continue


def tick_world(world: Any, *, wait_s: float = 0.05) -> None:
    """Advance world without long stalls.

    Sync mode: ``world.tick()``. Async (typical dual-client SIL): short
    ``wait_for_tick`` — never a 1.0s default that freezes the UI thread.
    """
    try:
        settings = world.get_settings()
        if bool(getattr(settings, "synchronous_mode", False)):
            world.tick()
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        world.tick()
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        world.wait_for_tick(max(0.01, float(wait_s)))
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
    n = 0
    r2 = float(radius_m) ** 2
    for v in list(world.get_actors().filter("vehicle.*")):
        try:
            role = str(v.attributes.get("role_name") or "")
            if role in protect:
                continue
            loc = v.get_location()
            dx = float(loc.x) - float(location.x)
            dy = float(loc.y) - float(location.y)
            if dx * dx + dy * dy <= r2:
                safe_destroy(v)
                n += 1
        except Exception:  # noqa: BLE001
            continue
    return n
