"""CARLA actors → ego-frame dyn objects for fake_perc / GfFakePercPod (no Giraffe imports)."""

from __future__ import annotations

import math
from typing import Any

from _lane_truth import _wrap_pi

# Gold OBJ_Object_Class
CLS_CAR = 1
CLS_TRUCK = 2
CLS_MOTORBIKE = 3
CLS_BICYCLE = 4
CLS_PEDESTRIAN = 5
CLS_TWO_WHEELER = 9

_MAX_DYN = 13
_RADIUS_M = 90.0
SEE_FOV_DEG = 50.0
_HOST_LANE_HALF_M = 1.75
_OCC_PAD_M = 2.0


def _stable_obj_id(actor_id: int, slot: int) -> int:
    """Map CARLA actor id → FCM uint8. Same actor keeps the same id across frames."""
    try:
        aid = int(actor_id)
    except (TypeError, ValueError):
        aid = 0
    if 1 <= aid <= 255:
        return aid
    if aid > 255:
        return (aid % 254) + 1
    return max(1, int(slot) + 1)

# Static actor attrs (type_id / bbox). Kinematics come from snapshot each tick.
_CACHE: dict[int, dict[str, Any]] = {}
_SKIP: set[int] = set()
_KEY: tuple[int, int] | None = None


def map_carla_class(type_id: str, *, is_walker: bool = False) -> int:
    t = (type_id or "").lower()
    if is_walker or "walker" in t or "pedestrian" in t:
        return CLS_PEDESTRIAN
    if "truck" in t or "bus" in t or "firetruck" in t or "ambulance" in t or "carlacola" in t or "sprinter" in t or "fusorosa" in t or "hgv" in t:
        return CLS_TRUCK
    if "motorcycle" in t or "motorbike" in t or "harley" in t or "kawasaki" in t or "yamaha" in t or "ninja" in t:
        return CLS_MOTORBIKE
    if "bicycle" in t or "bike" in t:
        return CLS_BICYCLE
    if "vespa" in t or "scooter" in t:
        return CLS_TWO_WHEELER
    return CLS_CAR


def _bbox_lw(actor: Any, default_l: float, default_w: float) -> tuple[float, float]:
    try:
        bb = actor.bounding_box.extent
        return max(1.0, float(bb.x) * 2.0), max(0.5, float(bb.y) * 2.0)
    except Exception:  # noqa: BLE001
        return default_l, default_w


def _xy_to_ego(ex: float, ey: float, c: float, s: float, wx: float, wy: float) -> tuple[float, float]:
    """World XY → ego (x forward, y left+). c,s = cos/sin(ego yaw)."""
    dx = float(wx) - ex
    dy = float(wy) - ey
    xf = c * dx + s * dy
    y_left = s * dx - c * dy
    return xf, y_left


def optic_in_wedge(x: float, y: float, *, fov_deg: float = SEE_FOV_DEG) -> bool:
    """Forward driving wedge: x>0 and |atan2(y,x)| ≤ half of see_fov_deg (50°)."""
    if float(x) <= 0.0:
        return False
    half = 0.5 * float(fov_deg) * math.pi / 180.0
    return abs(math.atan2(float(y), float(x))) <= half


def drop_host_behind_occupy(
    items: list[dict[str, Any]],
    *,
    lane_half_m: float = _HOST_LANE_HALF_M,
    pad_m: float = _OCC_PAD_M,
) -> list[dict[str, Any]]:
    """Host-lane objects beyond the nearest occupy face are optically hidden."""
    host = [
        it
        for it in items
        if abs(float(it["lat_m"])) <= lane_half_m and float(it["long_m"]) > 0.0
    ]
    if not host:
        return items
    occ = min(float(it["long_m"]) for it in host)
    out: list[dict[str, Any]] = []
    for it in items:
        if abs(float(it["lat_m"])) <= lane_half_m and float(it["long_m"]) > occ + pad_m:
            continue
        out.append(it)
    return out


def _try_snapshot(world: Any) -> Any:
    try:
        return world.get_snapshot()
    except Exception:  # noqa: BLE001
        return None


def _snap_kin(snap: Any, actor_id: int) -> tuple[Any, Any]:
    if snap is None:
        return None, None
    try:
        sh = snap.find(int(actor_id))
    except Exception:  # noqa: BLE001
        return None, None
    if sh is None:
        return None, None
    try:
        return sh.get_transform(), sh.get_velocity()
    except Exception:  # noqa: BLE001
        return None, None


def reset_dyn_object_cache() -> None:
    """Drop type_id/bbox cache (tests / new world)."""
    global _CACHE, _SKIP, _KEY
    _CACHE = {}
    _SKIP = set()
    _KEY = None


def _bind_cache(world: Any, ego_id: int) -> None:
    global _KEY
    key = (id(world), int(ego_id))
    if _KEY != key:
        reset_dyn_object_cache()
        _KEY = key


def _iter_snap_ids(snap: Any) -> list[int]:
    if snap is None:
        return []
    out: list[int] = []
    try:
        for sh in snap:
            out.append(int(getattr(sh, "id")))
        if out:
            return out
    except Exception:  # noqa: BLE001
        pass
    return []


def _fetch_by_ids(world: Any, ids: list[int]) -> list[Any]:
    if not ids:
        return []
    got: Any = None
    try:
        got = world.get_actors(ids)
    except TypeError:
        try:
            got = world.get_actors(actor_ids=ids)
        except Exception:  # noqa: BLE001
            return []
    except Exception:  # noqa: BLE001
        return []
    try:
        return list(got)
    except Exception:  # noqa: BLE001
        return []


def _put_actor(actor: Any) -> None:
    try:
        aid = int(actor.id)
    except Exception:  # noqa: BLE001
        return
    tid = str(getattr(actor, "type_id", "") or "")
    is_walker = tid.startswith("walker")
    is_veh = tid.startswith("vehicle.")
    if not is_walker and not is_veh:
        _SKIP.add(aid)
        _CACHE.pop(aid, None)
        return
    if is_walker:
        length_m, width_m = 0.6, 0.6
    else:
        length_m, width_m = _bbox_lw(actor, 4.5, 1.8)
    _CACHE[aid] = {
        "type_id": tid,
        "is_walker": bool(is_walker),
        "length_m": float(length_m),
        "width_m": float(width_m),
    }
    _SKIP.discard(aid)


def _fill_cache_full(world: Any, snap_ids: list[int]) -> None:
    for actor in _traffic_actors(world):
        _put_actor(actor)
    for sid in snap_ids:
        if sid not in _CACHE:
            _SKIP.add(int(sid))


def _refresh_cache(world: Any, snap_ids: list[int]) -> None:
    """First tick: one full get_actors. Later: only unknown snapshot ids."""
    live = set(int(s) for s in snap_ids)
    for aid in list(_CACHE):
        if live and aid not in live:
            del _CACHE[aid]
    if not _CACHE:
        _fill_cache_full(world, snap_ids)
        return
    unknown = [sid for sid in snap_ids if sid not in _CACHE and sid not in _SKIP]
    if not unknown:
        return
    fetched = _fetch_by_ids(world, unknown)
    seen: set[int] = set()
    for actor in fetched:
        _put_actor(actor)
        try:
            seen.add(int(actor.id))
        except Exception:  # noqa: BLE001
            pass
    for sid in unknown:
        if sid not in seen and sid not in _CACHE:
            _SKIP.add(int(sid))


def _traffic_actors(world: Any) -> list[Any]:
    """One get_actors() RPC; classify vehicle/walker client-side (no second filter RPC)."""
    try:
        all_a = world.get_actors()
    except Exception:  # noqa: BLE001
        return []
    out: list[Any] = []
    try:
        for a in all_a:
            tid = str(getattr(a, "type_id", "") or "")
            if tid.startswith("vehicle.") or tid.startswith("walker."):
                out.append(a)
        if out:
            return out
    except Exception:  # noqa: BLE001
        pass
    # Mock / older API: only filter() works
    try:
        out.extend(list(all_a.filter("vehicle.*")))
    except Exception:  # noqa: BLE001
        pass
    try:
        out.extend(list(all_a.filter("walker.pedestrian.*")))
    except Exception:  # noqa: BLE001
        pass
    return out


def collect_dyn_objects(
    ego: Any,
    world: Any,
    *,
    lead: Any = None,
    radius_m: float = _RADIUS_M,
    max_n: int = _MAX_DYN,
) -> dict[str, Any]:
    """Enumerate nearby vehicles + walkers → flat truth fields for FCM."""
    out: dict[str, Any] = {
        "dyn_n": 0,
        "vd_count": 0,
        "ped_count": 0,
        "cipv_id": 0,
    }
    if ego is None or world is None:
        return out

    ego_id = int(getattr(ego, "id", -1))
    lead_id = int(getattr(lead, "id", -1)) if lead is not None else -1
    items: list[dict[str, Any]] = []

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

    def _append(
        aid: int,
        *,
        is_walker: bool,
        typ: str,
        tf: Any,
        vel: Any,
        length_m: float,
        width_m: float,
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
            if x > radius_m or abs(y) > radius_m * 0.6:
                return
            if not optic_in_wedge(x, y):
                return
            cls = map_carla_class(typ, is_walker=is_walker)
            try:
                # Ego +x forward, +y left. CARLA yaw delta alone was opposite lane
                # poly (C2<0 right bend needed negative heading). Negate once here.
                heading = _wrap_pi(
                    yaw - math.radians(float(tf.rotation.yaw))
                )
            except Exception:  # noqa: BLE001
                heading = 0.0
            rel_v = 0.0
            try:
                af = c * float(vel.x) + s * float(vel.y)
                rel_v = float(af - ego_spd)
            except Exception:  # noqa: BLE001
                rel_v = 0.0
            assign = 3
            if y > 1.5:
                assign = 2
            elif y < -1.5:
                assign = 4
            if abs(y) > 4.5:
                assign = 1 if y > 0 else 5
            items.append(
                {
                    "actor_id": aid,
                    "class": cls,
                    "long_m": float(x),
                    "lat_m": float(y),
                    "heading_rad": float(heading),
                    "length_m": float(length_m),
                    "width_m": float(width_m),
                    "rel_v": float(rel_v),
                    "assign": int(assign),
                    "is_walker": bool(is_walker),
                    "is_lead": bool(aid == lead_id),
                }
            )
        except Exception:  # noqa: BLE001
            return

    if snap is not None and snap_ids:
        _refresh_cache(world, snap_ids)
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
                length_m=float(meta["length_m"]),
                width_m=float(meta["width_m"]),
            )
    else:
        for actor in _traffic_actors(world):
            tid = str(getattr(actor, "type_id", "") or "")
            try:
                tf = actor.get_transform()
                vel = actor.get_velocity()
            except Exception:  # noqa: BLE001
                continue
            is_walker = tid.startswith("walker")
            if is_walker:
                length_m, width_m = 0.6, 0.6
            else:
                length_m, width_m = _bbox_lw(actor, 4.5, 1.8)
            _append(
                int(actor.id),
                is_walker=is_walker,
                typ=tid,
                tf=tf,
                vel=vel,
                length_m=length_m,
                width_m=width_m,
            )

    items = drop_host_behind_occupy(items)
    # Prefer lead, then nearer ahead
    items.sort(key=lambda it: (0 if it["is_lead"] else 1, it["long_m"], abs(it["lat_m"])))
    items = items[: max(1, min(max_n, _MAX_DYN))]

    # Stable IDs follow CARLA actor (uint8); CIPV = that object's id, not list slot.
    cipv_id = 0
    vd_n = 0
    ped_n = 0
    for i, it in enumerate(items):
        oid = _stable_obj_id(int(it.get("actor_id") or 0), i)
        it["id"] = oid
        if it["is_walker"]:
            ped_n += 1
        else:
            vd_n += 1
        if it["is_lead"] and it["assign"] == 3 and cipv_id == 0:
            cipv_id = oid
    if cipv_id == 0:
        for it in items:
            if not it["is_walker"] and it["assign"] == 3 and it["long_m"] > 0.5:
                cipv_id = int(it["id"])
                break

    out["dyn_n"] = len(items)
    out["vd_count"] = vd_n
    out["ped_count"] = ped_n
    out["cipv_id"] = int(cipv_id)
    for i, it in enumerate(items):
        p = f"obj{i}_"
        out[p + "id"] = int(it["id"])
        out[p + "class"] = int(it["class"])
        out[p + "long"] = float(it["long_m"])
        out[p + "lat"] = float(it["lat_m"])
        out[p + "heading"] = float(it["heading_rad"])
        out[p + "len"] = float(it["length_m"])
        out[p + "wid"] = float(it["width_m"])
        out[p + "rel_v"] = float(it["rel_v"])
        out[p + "assign"] = int(it["assign"])
        out[p + "ped"] = 1 if it["is_walker"] else 0

    # Keep legacy lead_* in sync with CIPV when possible
    if cipv_id > 0:
        for it in items:
            if int(it["id"]) == cipv_id:
                out["lead_from_dyn_long"] = float(it["long_m"])
                out["lead_from_dyn_lat"] = float(it["lat_m"])
                out["lead_from_dyn_heading"] = float(it["heading_rad"])
                out["lead_from_dyn_rel_v"] = float(it["rel_v"])
                out["lead_from_dyn_assign"] = int(it["assign"])
                break
    return out
