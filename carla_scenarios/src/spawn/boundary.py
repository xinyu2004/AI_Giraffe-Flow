"""Case / combo **boundary** — owns keep_ego world residue.

Lifecycle::

  place (pose, at rest) → case IC (named speed) → run/judge
       ↑                                              │
       └──────── sanitize_keep_ego (batch/combo) ◄────┘

Invariant before the next layout starts:
  - no constant-velocity on hero
  - |v| ≈ 0
keep_ego is an optimization, not a promise: if sanitize fails → destroy hero
so the next place() spawns fresh.
"""

from __future__ import annotations

from typing import Any, Optional

from spawn.roles import ROLE_EGO, destroy_role, find_by_role, tick_world

# Max residual speed (m/s) allowed when entering the next layout.
_MAX_REST_MPS = 0.35


def _speed_xy(vehicle: Any) -> float:
    import math

    try:
        v = vehicle.get_velocity()
        return math.hypot(float(v.x), float(v.y))
    except Exception:  # noqa: BLE001
        return 0.0


def _hard_stop(vehicle: Any) -> None:
    import carla  # type: ignore

    try:
        vehicle.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    try:
        vehicle.set_autopilot(False)
    except Exception:  # noqa: BLE001
        pass
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
    try:
        vehicle.set_simulate_physics(False)
        vehicle.set_transform(vehicle.get_transform())
        vehicle.set_simulate_physics(True)
    except Exception:  # noqa: BLE001
        pass
    try:
        vehicle.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    except Exception:  # noqa: BLE001
        pass


def sanitize_keep_ego(
    world: Any,
    ego: Optional[Any] = None,
    *,
    max_rest_mps: float = _MAX_REST_MPS,
    attempts: int = 4,
) -> bool:
    """Clear hero residue between cases. Return True if hero kept and at rest.

    False means hero was destroyed (or missing) — next place must spawn anew.
    No case_id branches.
    """
    if world is None:
        return False
    hero = ego if ego is not None else find_by_role(world, ROLE_EGO)
    if hero is None:
        print("[boundary] sanitize: no hero (ok, next place will spawn)", flush=True)
        return False

    for i in range(max(1, int(attempts))):
        _hard_stop(hero)
        try:
            tick_world(world)
        except Exception:  # noqa: BLE001
            pass
        _hard_stop(hero)
        try:
            tick_world(world)
        except Exception:  # noqa: BLE001
            pass
        spd = _speed_xy(hero)
        if spd <= max_rest_mps:
            # Release brake so the next IC can move; stay nearly stopped.
            try:
                import carla  # type: ignore

                hero.apply_control(
                    carla.VehicleControl(
                        throttle=0.0,
                        brake=0.0,
                        steer=0.0,
                        hand_brake=False,
                        reverse=False,
                    )
                )
            except Exception:  # noqa: BLE001
                pass
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
        f"[boundary] sanitize FAILED |v|={_speed_xy(hero):.3f} → destroy hero "
        f"(keep_ego downgrade)",
        flush=True,
    )
    destroy_role(world, ROLE_EGO)
    try:
        tick_world(world)
    except Exception:  # noqa: BLE001
        pass
    return False


# Backward-compatible name used by older call sites.
def handoff_keep_ego(ego: Any) -> None:
    """Deprecated alias: sanitize using ego's world. Prefer sanitize_keep_ego."""
    if ego is None:
        return
    try:
        world = ego.get_world()
    except Exception:  # noqa: BLE001
        return
    sanitize_keep_ego(world, ego)
