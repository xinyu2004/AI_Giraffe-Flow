"""Town04 surface lot: aisle ego, static parked cars, empty-bay PLD truth."""

from __future__ import annotations

import math
from typing import Any, Tuple

from spawn.place import spawn_ego_only
from spawn.roles import ROLE_EGO, clear_near, set_role, tick_world
from _surround_truth import write_parking_bays
from _verdict import release_ego

# Town04 west lot aisle (surface). Ego faces −x along the aisle.
_EGO_X = 283.0
_EGO_Y = -206.0
_EGO_Z = 0.35
_EGO_YAW_DEG = 180.0

# Perpendicular bays to the aisle right (world +y). Slot 2 is the HMI pick.
_BAYS = (
    {"id": 1, "free": 0, "x": 278.0, "y": -200.5},
    {"id": 2, "free": 1, "x": 272.5, "y": -200.5},
    {"id": 3, "free": 1, "x": 267.0, "y": -200.5},
    {"id": 4, "free": 0, "x": 261.5, "y": -200.5},
)
_BAY_LEN = 5.0
_BAY_WID = 2.4
_BAY_YAW = math.radians(-90.0)


def slot_corners_world(
    cx: float, cy: float, yaw: float, length: float, width: float
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    hl, hw = 0.5 * length, 0.5 * width
    c, s = math.cos(yaw), math.sin(yaw)
    pts = []
    for lx, ly in ((-hl, -hw), (hl, -hw), (hl, hw)):
        pts.append((cx + c * lx - s * ly, cy + s * lx + c * ly))
    return pts[0], pts[1], pts[2]


def _tf(carla_mod: Any, x: float, y: float, z: float, yaw_deg: float) -> Any:
    return carla_mod.Transform(
        carla_mod.Location(x=float(x), y=float(y), z=float(z)),
        carla_mod.Rotation(pitch=0.0, yaw=float(yaw_deg), roll=0.0),
    )


def _spawn_parked(world: Any, carla_mod: Any, tf: Any, role: str) -> Any | None:
    lib = world.get_blueprint_library()
    cands = list(lib.filter("vehicle.tesla.model3")) or list(lib.filter("vehicle.*"))
    if not cands:
        return None
    clear_near(world, tf.location, radius_m=3.5, protect_roles={ROLE_EGO})
    for bp in cands[:4]:
        set_role(bp, role)
        actor = world.try_spawn_actor(bp, tf)
        if actor is None:
            continue
        try:
            actor.apply_control(
                carla_mod.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)
            )
        except Exception:  # noqa: BLE001
            pass
        return actor
    return None


def layout_parking_lot(
    session: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    ego_tf = _tf(carla_mod, _EGO_X, _EGO_Y, _EGO_Z, _EGO_YAW_DEG)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    try:
        ego.apply_control(
            carla_mod.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)
        )
    except Exception:  # noqa: BLE001
        pass

    parked: list[int] = []
    for bay in _BAYS:
        if int(bay["free"]):
            continue
        ptf = _tf(carla_mod, bay["x"], bay["y"], _EGO_Z, math.degrees(_BAY_YAW))
        actor = _spawn_parked(world, carla_mod, ptf, f"park{bay['id']}")
        if actor is not None:
            parked.append(int(actor.id))
    tick_world(world)

    bays = []
    for bay in _BAYS:
        bays.append(
            {
                "id": int(bay["id"]),
                "free": int(bay["free"]),
                "center_x_m": float(bay["x"]),
                "center_y_m": float(bay["y"]),
                "yaw_rad": _BAY_YAW,
                "length_m": _BAY_LEN,
                "width_m": _BAY_WID,
            }
        )
    write_parking_bays(bays)

    p0, p1, p2 = slot_corners_world(
        float(_BAYS[1]["x"]), float(_BAYS[1]["y"]), _BAY_YAW, _BAY_LEN, _BAY_WID
    )
    print(
        f"[layout] PARKING_LOT Town04 aisle ego={ego.id} parked={parked} "
        f"bays={len(bays)} pick=2",
        flush=True,
    )
    return ego, None, {
        "layout": "parking_lot",
        "parking_bays": bays,
        "pick_slot_id": 2,
        "pick_p_world": (p0, p1, p2),
        "ic": "giraffe_only",
    }
