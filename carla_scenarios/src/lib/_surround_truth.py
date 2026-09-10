"""CARLA actors → ego-frame surround objects + synthetic parking slots.

Unlike fake_perc dyn (front FOV wedge), surround keeps side/rear targets.
"""

from __future__ import annotations

import math
import os
from typing import Any

from _objects_truth import (
    _bind_cache,
    _iter_snap_ids,
    _refresh_cache,
    _snap_kin,
    _stable_obj_id,
    _traffic_actors,
    _try_snapshot,
    _xy_to_ego,
    map_carla_class,
)

_MAX_OBJ = 16
_RADIUS_M = 40.0


def _slot_demo_on() -> bool:
    v = (os.environ.get("GF_SURROUND_SLOT_DEMO") or "1").strip().lower()
    return v not in ("0", "off", "false", "no")


def collect_surround_world(
    ego: Any,
    world: Any,
    *,
    radius_m: float = _RADIUS_M,
    max_n: int = _MAX_OBJ,
) -> dict[str, Any]:
    """Nearby vehicles/walkers (full azimuth) + optional free right slot."""
    out: dict[str, Any] = {"objects": [], "slots": [], "n_obj": 0, "n_slot": 0}
    if ego is None or world is None:
        return out

    ego_id = int(getattr(ego, "id", -1))
    snap = _try_snapshot(world)
    ego_tf, ego_vel = _snap_kin(snap, ego_id)
    if ego_tf is None:
        try:
            ego_tf = ego.get_transform()
        except Exception:  # noqa: BLE001
            return out
    if ego_vel is None:
        try:
            ego_vel = ego.get_velocity()
        except Exception:  # noqa: BLE001
            ego_vel = None

    ex = float(ego_tf.location.x)
    ey = float(ego_tf.location.y)
    yaw = math.radians(float(ego_tf.rotation.yaw))
    c, s = math.cos(yaw), math.sin(yaw)
    if ego_vel is not None:
        ego_spd = math.sqrt(
            float(ego_vel.x) ** 2 + float(ego_vel.y) ** 2 + float(ego_vel.z) ** 2
        )
    else:
        ego_spd = 0.0

    r2 = (float(radius_m) * 1.15) ** 2
    _bind_cache(world, ego_id)
    snap_ids = _iter_snap_ids(snap)
    items: list[dict[str, Any]] = []

    def _append(
        aid: int,
        *,
        is_walker: bool,
        typ: str,
        tf: Any,
        vel: Any,
    ) -> None:
        try:
            if aid == ego_id:
                return
            loc = tf.location
            dxw = float(loc.x) - ex
            dyw = float(loc.y) - ey
            if dxw * dxw + dyw * dyw > r2:
                return
            x, y = _xy_to_ego(ex, ey, c, s, float(loc.x), float(loc.y))
            if abs(x) > radius_m or abs(y) > radius_m:
                return
            cls = map_carla_class(typ, is_walker=is_walker)
            rel_v = 0.0
            try:
                af = c * float(vel.x) + s * float(vel.y)
                rel_v = float(af - ego_spd)
            except Exception:  # noqa: BLE001
                rel_v = 0.0
            items.append(
                {
                    "actor_id": aid,
                    "class": cls,
                    "long_m": float(x),
                    "lat_m": float(y),
                    "rel_v": float(rel_v),
                }
            )
        except Exception:  # noqa: BLE001
            return

    if snap is not None and snap_ids:
        _refresh_cache(world, snap_ids)
        from _objects_truth import _CACHE  # noqa: WPS433

        for aid, meta in list(_CACHE.items()):
            if aid == ego_id:
                continue
            tf, vel = _snap_kin(snap, aid)
            if tf is None:
                continue
            if vel is None:
                vel = type("V", (), {"x": 0.0, "y": 0.0, "z": 0.0})()
            _append(
                aid,
                is_walker=bool(meta["is_walker"]),
                typ=str(meta["type_id"]),
                tf=tf,
                vel=vel,
            )
    else:
        for actor in _traffic_actors(world):
            tid = str(getattr(actor, "type_id", "") or "")
            try:
                tf = actor.get_transform()
                vel = actor.get_velocity()
            except Exception:  # noqa: BLE001
                continue
            _append(
                int(actor.id),
                is_walker=tid.startswith("walker"),
                typ=tid,
                tf=tf,
                vel=vel,
            )

    # Prefer nearer; keep rear/side (no FOV cut).
    items.sort(key=lambda it: (abs(it["long_m"]) + abs(it["lat_m"]), abs(it["lat_m"])))
    items = items[: max(0, min(max_n, _MAX_OBJ))]
    objects: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        oid = _stable_obj_id(int(it.get("actor_id") or 0), i)
        objects.append(
            {
                "object_id": oid,
                "object_class": int(it["class"]),
                "long_dist_m": float(it["long_m"]),
                "lat_dist_m": float(it["lat_m"]),
                "rel_vel_long_mps": float(it["rel_v"]),
            }
        )

    slots: list[dict[str, Any]] = []
    if _slot_demo_on():
        # Stage P: synthetic free right bay unless a vehicle occupies that footprint.
        cx, cy = 6.0, -3.2
        occupied = False
        for o in objects:
            dx = float(o["long_dist_m"]) - cx
            dy = float(o["lat_dist_m"]) - cy
            if dx * dx + dy * dy < (2.5**2):
                occupied = True
                break
        slots.append(
            {
                "slot_id": 1,
                "free": 0 if occupied else 1,
                "center_x_m": cx,
                "center_y_m": cy,
                "yaw_rad": 0.0,
                "length_m": 5.0,
                "width_m": 2.4,
            }
        )

    out["objects"] = objects
    out["slots"] = slots
    out["n_obj"] = len(objects)
    out["n_slot"] = len(slots)
    return out
