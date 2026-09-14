"""CARLA actors → ego-frame surround objects (+ real slots only).

Envelope (not invent):
  - rear 周视: x in [-40, 0], |y| <= 12
  - side 环视: |y| in (0.8, 10], |x| <= 10
  - forward long-range is FCM / fake_perc — not synthesized here
"""

from __future__ import annotations

import math
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
_REAR_M = 40.0
_SIDE_M = 10.0
_SIDE_X_M = 10.0
_REAR_Y_M = 12.0


def in_surround_envelope(x: float, y: float) -> bool:
    """True if (x,y) ego-frame is in rear 周视 or side 环视 near field."""
    ax = float(x)
    ay = float(y)
    if ax <= 0.0:
        return ax >= -_REAR_M and abs(ay) <= _REAR_Y_M
    if abs(ay) > 0.8:
        return abs(ay) <= _SIDE_M and ax <= _SIDE_X_M
    return False


def collect_surround_world(
    ego: Any,
    world: Any,
    *,
    max_n: int = _MAX_OBJ,
) -> dict[str, Any]:
    """Nearby vehicles/walkers in surround envelope. Slots: only if provided later (none invented)."""
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

    r_max = max(_REAR_M, _SIDE_M, _SIDE_X_M) * 1.15
    r2 = r_max * r_max
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
            if not in_surround_envelope(x, y):
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

    out["objects"] = objects
    out["slots"] = []  # no invented parking bays
    out["n_obj"] = len(objects)
    out["n_slot"] = 0
    return out
