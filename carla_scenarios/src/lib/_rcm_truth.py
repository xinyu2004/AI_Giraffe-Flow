"""CARLA → rear FOV truth for RCM (Perception_Rear_Out_St).

Front FOV stays in fake_perc/FCM. Here: x≤0 ∧ rear camera FOV (~120°) ∧ ≤35 m.
No TSR. Prefer silence upstream when nothing valid (caller sets valid).
"""

from __future__ import annotations

import math
from typing import Any

from _lane_truth import _ego_pose, _fit_c0_c1_c2, _road_c1_yaw, world_to_ego_xy_cs
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
_MAX_LANE = 8
_REAR_FOV_DEG = 120.0  # matches kFsRearFovDeg / camera_contract rear
_REAR_CAP_M = 35.0


def optic_in_rear_wedge(
    x: float,
    y: float,
    *,
    fov_deg: float = _REAR_FOV_DEG,
    cap_m: float = _REAR_CAP_M,
) -> bool:
    """Behind ego: x<0, |atan2(y,−x)| ≤ half rear FOV, range ≤ cap."""
    xf = float(x)
    yf = float(y)
    if xf >= 0.0:
        return False
    rng = math.hypot(xf, yf)
    if rng > float(cap_m) * 1.05 or abs(xf) > float(cap_m):
        return False
    half = 0.5 * float(fov_deg) * math.pi / 180.0
    return abs(math.atan2(yf, -xf)) <= half


def _sample_edge_poly_behind(
    ego: Any,
    wp: Any,
    *,
    side: str,
    half_w: float,
    horizon_m: float = 35.0,
    pose: tuple[float, float, float, float, float] | None = None,
) -> tuple[float, float, float]:
    """Sample lane edge behind ego → (c0, c1, c2) in ego frame (x forward)."""
    if pose is None:
        pose = _ego_pose(ego)
    ex, ey, c, s, ego_yaw = pose
    xs: list[float] = []
    ys: list[float] = []
    cur = wp
    dist = 0.0
    sign = 1.0 if side == "left" else -1.0
    for _ in range(12):
        try:
            loc = cur.transform.location
            yaw = math.radians(float(cur.transform.rotation.yaw))
            lx = float(loc.x) + sign * half_w * math.sin(yaw)
            ly = float(loc.y) + sign * half_w * (-math.cos(yaw))
            xe, ye = world_to_ego_xy_cs(ex, ey, c, s, lx, ly)
            if xe <= 2.0:
                xs.append(xe)
                ys.append(ye)
        except Exception:  # noqa: BLE001
            break
        if dist >= horizon_m:
            break
        try:
            prev = cur.previous(5.0)
            if not prev:
                break
            cur = prev[0]
            dist += 5.0
        except Exception:  # noqa: BLE001
            break
    if not xs:
        c1 = _road_c1_yaw(ego_yaw, wp)
        return sign * half_w, c1, 0.0
    return _fit_c0_c1_c2(xs, ys)


def collect_rcm_lanes(ego: Any, world: Any) -> list[dict[str, Any]]:
    """Host left/right polys behind ego (side 0/1). Empty if map unavailable."""
    out: list[dict[str, Any]] = []
    if ego is None or world is None:
        return out
    try:
        carla = __import__("carla")
        loc = ego.get_transform().location
        wp = world.get_map().get_waypoint(
            loc, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        if wp is None:
            return out
        half = float(wp.lane_width) * 0.5
        pose = _ego_pose(ego)
        lc0, lc1, lc2 = _sample_edge_poly_behind(
            ego, wp, side="left", half_w=half, pose=pose
        )
        rc0, rc1, rc2 = _sample_edge_poly_behind(
            ego, wp, side="right", half_w=half, pose=pose
        )
        out.append(
            {
                "c0_m": lc0,
                "c1_rad": lc1,
                "c2": lc2,
                "c3": 0.0,
                "view_range_m": _REAR_CAP_M,
                "quality": 2,
                "side": 0,
            }
        )
        out.append(
            {
                "c0_m": rc0,
                "c1_rad": rc1,
                "c2": rc2,
                "c3": 0.0,
                "view_range_m": _REAR_CAP_M,
                "quality": 2,
                "side": 1,
            }
        )
    except Exception:  # noqa: BLE001
        return []
    return out[:_MAX_LANE]


def collect_rcm_objects(ego: Any, world: Any, *, max_n: int = _MAX_OBJ) -> list[dict[str, Any]]:
    """Vehicles/walkers in rear optical wedge."""
    items: list[dict[str, Any]] = []
    if ego is None or world is None:
        return items

    ego_id = int(getattr(ego, "id", -1))
    snap = _try_snapshot(world)
    ego_tf, ego_vel = _snap_kin(snap, ego_id)
    if ego_tf is None:
        try:
            ego_tf = ego.get_transform()
        except Exception:  # noqa: BLE001
            return items
    if ego_vel is None:
        try:
            ego_vel = ego.get_velocity()
        except Exception:  # noqa: BLE001
            ego_vel = None

    ex = float(ego_tf.location.x)
    ey = float(ego_tf.location.y)
    yaw = math.radians(float(ego_tf.rotation.yaw))
    c, s = math.cos(yaw), math.sin(yaw)
    ego_fx = c * float(ego_vel.x) + s * float(ego_vel.y) if ego_vel is not None else 0.0
    ego_fy = -s * float(ego_vel.x) + c * float(ego_vel.y) if ego_vel is not None else 0.0

    r_max = _REAR_CAP_M * 1.2
    r2 = r_max * r_max
    _bind_cache(world, ego_id)
    snap_ids = _iter_snap_ids(snap)

    def _append(aid: int, *, is_walker: bool, typ: str, tf: Any, vel: Any) -> None:
        try:
            if aid == ego_id:
                return
            loc = tf.location
            dxw = float(loc.x) - ex
            dyw = float(loc.y) - ey
            if dxw * dxw + dyw * dyw > r2:
                return
            x, y = _xy_to_ego(ex, ey, c, s, float(loc.x), float(loc.y))
            if not optic_in_rear_wedge(x, y):
                return
            af = c * float(vel.x) + s * float(vel.y)
            al = -s * float(vel.x) + c * float(vel.y)
            abs_v = math.sqrt(float(vel.x) ** 2 + float(vel.y) ** 2 + float(vel.z) ** 2)
            items.append(
                {
                    "actor_id": aid,
                    "object_class": map_carla_class(typ, is_walker=is_walker),
                    "long_dist_m": float(x),
                    "lat_dist_m": float(y),
                    "rel_vel_long_mps": float(af - ego_fx),
                    "rel_vel_lat_mps": float(al - ego_fy),
                    "abs_vel_mps": float(abs_v),
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

    items.sort(key=lambda o: abs(float(o["long_dist_m"])))
    items = items[: max(0, min(max_n, _MAX_OBJ))]
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        out.append(
            {
                "object_id": _stable_obj_id(int(it.get("actor_id") or 0), i),
                "object_class": int(it["object_class"]),
                "long_dist_m": float(it["long_dist_m"]),
                "lat_dist_m": float(it["lat_dist_m"]),
                "rel_vel_long_mps": float(it["rel_vel_long_mps"]),
                "rel_vel_lat_mps": float(it["rel_vel_lat_mps"]),
                "abs_vel_mps": float(it["abs_vel_mps"]),
            }
        )
    return out


def collect_rcm_truth(ego: Any, world: Any) -> dict[str, Any]:
    """Full rear truth dict for pack_rcm_truth_pod."""
    lanes = collect_rcm_lanes(ego, world)
    objects = collect_rcm_objects(ego, world)
    return {
        "lanes": lanes,
        "objects": objects,
        "n_lane": len(lanes),
        "n_obj": len(objects),
        "valid": 1 if (lanes or objects) else 1,  # empty scene still valid truth
    }
