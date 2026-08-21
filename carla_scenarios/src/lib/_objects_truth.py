"""CARLA actors → ego-frame dyn objects for carla_truth (no Giraffe imports)."""

from __future__ import annotations

import math
from typing import Any, Optional

from _lane_truth import _wrap_pi, _ego_yaw_rad, world_to_ego_xy

# Gold OBJ_Object_Class
CLS_CAR = 1
CLS_TRUCK = 2
CLS_MOTORBIKE = 3
CLS_BICYCLE = 4
CLS_PEDESTRIAN = 5
CLS_TWO_WHEELER = 9

_MAX_DYN = 13
_RADIUS_M = 90.0


def map_carla_class(type_id: str, *, is_walker: bool = False) -> int:
    t = (type_id or "").lower()
    if is_walker or "walker" in t or "pedestrian" in t:
        return CLS_PEDESTRIAN
    if "truck" in t or "bus" in t or "firetruck" in t or "ambulance" in t:
        return CLS_TRUCK
    if "motorcycle" in t or "motorbike" in t:
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

    def _consider(actor: Any, *, is_walker: bool) -> None:
        try:
            if not actor.is_alive:
                return
            aid = int(actor.id)
            if aid == ego_id:
                return
            loc = actor.get_location()
            x, y = world_to_ego_xy(ego, float(loc.x), float(loc.y))
            if x < -5.0 or x > radius_m:
                return
            if abs(y) > radius_m * 0.6:
                return
            typ = ""
            try:
                typ = str(actor.type_id)
            except Exception:  # noqa: BLE001
                typ = "walker" if is_walker else "vehicle"
            cls = map_carla_class(typ, is_walker=is_walker)
            try:
                ayaw = math.radians(float(actor.get_transform().rotation.yaw))
                heading = _wrap_pi(ayaw - _ego_yaw_rad(ego))
            except Exception:  # noqa: BLE001
                heading = 0.0
            if is_walker:
                length_m, width_m = 0.6, 0.6
            else:
                length_m, width_m = _bbox_lw(actor, 4.5, 1.8)
            # Relative long velocity (lead-like): actor_speed_along_ego_x - ego_speed
            try:
                ev = ego.get_velocity()
                av = actor.get_velocity()
                ego_spd = math.sqrt(ev.x**2 + ev.y**2 + ev.z**2)
                # project actor vel onto ego forward
                eyaw = _ego_yaw_rad(ego)
                af = math.cos(eyaw) * av.x + math.sin(eyaw) * av.y
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
                    "long_m": float(max(0.0, x)),
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

    try:
        for v in world.get_actors().filter("vehicle.*"):
            _consider(v, is_walker=False)
    except Exception:  # noqa: BLE001
        pass
    try:
        for w in world.get_actors().filter("walker.pedestrian.*"):
            _consider(w, is_walker=True)
    except Exception:  # noqa: BLE001
        pass

    # Prefer lead, then nearer ahead
    items.sort(key=lambda it: (0 if it["is_lead"] else 1, it["long_m"], abs(it["lat_m"])))
    items = items[: max(1, min(max_n, _MAX_DYN))]

    # Stable 1..n IDs; CIPV = lead if present else nearest host-lane ahead
    cipv_id = 0
    vd_n = 0
    ped_n = 0
    for i, it in enumerate(items):
        oid = i + 1
        it["id"] = oid
        if it["is_walker"]:
            ped_n += 1
        else:
            vd_n += 1
        if it["is_lead"] and cipv_id == 0:
            cipv_id = oid
    if cipv_id == 0:
        for it in items:
            if not it["is_walker"] and it["assign"] == 3 and it["long_m"] > 0.5:
                cipv_id = int(it["id"])
                break
    if cipv_id == 0 and items:
        for it in items:
            if not it["is_walker"]:
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
