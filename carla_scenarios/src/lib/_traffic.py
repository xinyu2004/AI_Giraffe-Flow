"""Ambient traffic as a local bubble that follows the ego.

carla.env::

  GF_TRAFFIC_NUMBER=18   # ~N new see-cone units per rolling 5 s; 0=off

Waypoints: ego-centric flood (no generate_waypoints). Host exam window empty.
"""

from __future__ import annotations

import math
import os
import random
import time
from typing import Any, Optional

from _spawn import ROLE_EGO, ROLE_LEAD
from spawn.pick import offset_transform, tf_on_lane
from spawn.place import roll_npc
from spawn.roles import find_by_role

ROLE_TRAFFIC_PREFIX = "traffic_"
ROLE_TRAFFIC_PED_PREFIX = "traffic_ped_"

_PROTECTED_ROLES = {ROLE_EGO, ROLE_LEAD, "vru", "hazard"}
_MAX_OFF_LANE_M = 2.5
_LANE_W_M = 3.5
_CARRIAGE_M = 14.0

_BUBBLE_M = 80.0
_CULL_M = 120.0
_NO_POP_AHEAD_M = 20.0
_EXAM_BEHIND_M = -8.0
_EXAM_AHEAD_MIN_M = 70.0
_EXAM_FIXTURE_PAD_M = 25.0
_MAX_PER_MAINTAIN = 2
_MAX_PEDS = 3
_MAINTAIN_PERIOD_S = 2.0
_SEE_ALONG_LO_M = 8.0
_SEE_ALONG_HI_M = 80.0
_SEE_LAT_M = 16.0
_EVICT_REPLAY_M = 22.0
_SEE5_S = 5.0
_CELL_M = 20.0
_FLOOD_STEP_M = 8.0
_FLOOD_MAX_N = 80
_FLOOD_RING_N = 36
_XING_PAIR_CAP = 24

_AMBIENT_WEIGHTS = (("car", 6), ("truck", 2), ("motorcycle", 2))
_SLOT_WEIGHTS = {
    "left_ahead": (("truck", 4), ("car", 3), ("motorcycle", 2)),
    "right_ahead": (("truck", 3), ("car", 4), ("motorcycle", 2)),
    "left_behind": (("car", 6), ("motorcycle", 3), ("truck", 1)),
    "right_behind": (("car", 6), ("motorcycle", 2), ("truck", 1)),
    "oncoming": (("car", 5), ("truck", 2), ("motorcycle", 2)),
    "crossing": (("car", 6), ("truck", 2), ("motorcycle", 1)),
    "host_far": (("car", 5), ("truck", 2), ("motorcycle", 1)),
}
_FILL_ORDER = (
    "right_ahead",
    "left_behind",
    "crossing",
    "left_ahead",
    "oncoming",
    "right_behind",
    "host_far",
)
_SLOT_CAPS_AT_18 = {
    "right_ahead": 4,
    "left_behind": 4,
    "crossing": 2,
    "left_ahead": 2,
    "oncoming": 2,
    "right_behind": 2,
    "host_far": 2,
}
_MOTORCYCLE_KEYS = (
    "motorcycle",
    "motorbike",
    "harley",
    "kawasaki",
    "yamaha",
    "vespa",
    "ninja",
    "low_rider",
)
_TRUCK_KEYS = (
    "truck",
    "bus",
    "firetruck",
    "ambulance",
    "carlacola",
    "cybertruck",
    "sprinter",
    "fusorosa",
    "hgv",
)
_BICYCLE_KEYS = ("bicycle", "crossbike", "gazelle", "diamondback")
_SKIP_AMBIENT_BP = ("bus", "firetruck", "ambulance", "fire")
_VRU_CASE_TAGS = ("aeb_pedestrian", "aeb_bicycle")

_maintain_last_s = -1e9
_role_seq = 0
_seen5_events: list[tuple[float, int]] = []
_flood_cell: tuple[int, int] | None = None
_flood_tfs: list[Any] = []
_bp_buckets: dict[str, list[Any]] | None = None


def ambient_bp_kind(bp_id: str) -> str:
    """car | truck | motorcycle | bicycle. Bicycles are not ambient stock."""
    t = (bp_id or "").lower()
    if any(k in t for k in _BICYCLE_KEYS):
        return "bicycle"
    if any(k in t for k in _MOTORCYCLE_KEYS):
        return "motorcycle"
    if "bike" in t:
        return "bicycle"
    if any(k in t for k in _TRUCK_KEYS):
        return "truck"
    return "car"


def ambient_bp_allowed(bp_id: str) -> bool:
    """Drop buses / emergency — those were the 'car became a coach' morph."""
    t = (bp_id or "").lower()
    return not any(k in t for k in _SKIP_AMBIENT_BP)


def _bucket_ambient_bps(bps: list[Any]) -> dict[str, list[Any]]:
    buckets: dict[str, list[Any]] = {"car": [], "truck": [], "motorcycle": []}
    for bp in bps:
        bid = getattr(bp, "id", "") or ""
        if not ambient_bp_allowed(bid):
            continue
        kind = ambient_bp_kind(bid)
        if kind in buckets:
            buckets[kind].append(bp)
    return buckets


def _cached_buckets(world: Any) -> dict[str, list[Any]]:
    """Blueprint list is static; do not re-filter the library on every keep_ego seed."""
    global _bp_buckets
    if _bp_buckets and any(_bp_buckets.values()):
        return _bp_buckets
    _bp_buckets = _bucket_ambient_bps(
        list(world.get_blueprint_library().filter("vehicle.*"))
    )
    return _bp_buckets


def _pick_ambient_bp(
    buckets: dict[str, list[Any]],
    *,
    slot: str = "side",
) -> Any:
    table = _SLOT_WEIGHTS.get(slot, _AMBIENT_WEIGHTS)
    kinds = [k for k, _w in table if buckets.get(k)]
    if not kinds:
        kinds = [k for k, _w in _AMBIENT_WEIGHTS if buckets.get(k)]
        table = _AMBIENT_WEIGHTS
    if not kinds:
        return None
    weights = [w for k, w in table if k in kinds]
    kind = random.choices(kinds, weights=weights, k=1)[0]
    return random.choice(buckets[kind])


def traffic_number(snap: Any = None) -> int:
    """Rolling 5 s see-cone appearance target. Prefer Snapshot.traffic_number."""
    if snap is not None:
        return max(0, int(snap.traffic_number))
    raw = (os.environ.get("GF_TRAFFIC_NUMBER") or "18").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 18


def maintain_period_s(snap: Any = None) -> float:
    if snap is not None:
        return max(0.5, float(snap.traffic_maintain_s))
    raw = (os.environ.get("GF_TRAFFIC_MAINTAIN_S") or str(_MAINTAIN_PERIOD_S)).strip()
    try:
        return max(0.5, float(raw))
    except ValueError:
        return _MAINTAIN_PERIOD_S


def live_stock_cap(number: int) -> int:
    """Simultaneous bubble size ≈ N/2."""
    if number <= 0:
        return 0
    return max(4, int(number) // 2)


def ego_cell(x: float, y: float, *, cell_m: float = _CELL_M) -> tuple[int, int]:
    return (int(math.floor(float(x) / cell_m)), int(math.floor(float(y) / cell_m)))


def prune_seen5(now_s: float, events: list[tuple[float, int]]) -> list[tuple[float, int]]:
    cut = float(now_s) - _SEE5_S
    return [(t, aid) for t, aid in events if t >= cut]


def seen5_count(events: list[tuple[float, int]], now_s: float) -> int:
    return len({aid for t, aid in prune_seen5(now_s, events)})


def slot_caps_for_target(target: int) -> dict[str, int]:
    """Scale the density-2 slot table to the bubble target."""
    if target <= 0:
        return {k: 0 for k in _SLOT_CAPS_AT_18}
    scale = max(1.0, float(target) / 18.0) if target >= 18 else float(target) / 18.0
    caps = {k: max(0, int(round(v * scale))) for k, v in _SLOT_CAPS_AT_18.items()}
    if target > 0 and sum(caps.values()) == 0:
        caps["right_ahead"] = 1
        caps["left_behind"] = min(1, target - 1)
    extra = target - sum(caps.values())
    i = 0
    while extra > 0 and caps:
        key = _FILL_ORDER[i % len(_FILL_ORDER)]
        caps[key] = caps.get(key, 0) + 1
        extra -= 1
        i += 1
    while extra < 0:
        grew = False
        for key in reversed(_FILL_ORDER):
            if caps.get(key, 0) > 0:
                caps[key] -= 1
                extra += 1
                grew = True
                if extra >= 0:
                    break
        if not grew:
            break
    return caps


def exam_window_end_m(fixture_along_m: Optional[float]) -> float:
    if fixture_along_m is None or fixture_along_m <= 0.0:
        return _EXAM_AHEAD_MIN_M
    return max(_EXAM_AHEAD_MIN_M, float(fixture_along_m) + _EXAM_FIXTURE_PAD_M)


def in_exam_tube(
    along_m: float,
    lat_left_m: float,
    exam_end_m: float,
    *,
    lane_w_m: float = _LANE_W_M,
) -> bool:
    half = 0.5 * float(lane_w_m)
    return abs(lat_left_m) <= half and _EXAM_BEHIND_M <= along_m <= float(exam_end_m)


def spawn_band_ok(slot: str, along_m: float, *, exam_end_m: float = _EXAM_AHEAD_MIN_M) -> bool:
    """Allowed longitudinal band for a *new* spawn (never 0–20 m ahead)."""
    a = float(along_m)
    if 0.0 <= a < _NO_POP_AHEAD_M:
        return False
    if slot == "right_ahead":
        return 25.0 <= a <= 70.0
    if slot == "left_behind":
        return -45.0 <= a <= -18.0
    if slot == "left_ahead":
        return 25.0 <= a <= 70.0
    if slot == "right_behind":
        return -45.0 <= a <= -18.0
    if slot == "oncoming":
        return 25.0 <= a <= 80.0
    if slot == "crossing":
        return 20.0 <= a <= 80.0
    if slot == "host_far":
        return a >= float(exam_end_m) and a <= 90.0
    return False


def in_see_cone(along_m: float, lat_left_m: float) -> bool:
    """Windshield / near-side band the driver can actually see."""
    return _SEE_ALONG_LO_M <= float(along_m) <= _SEE_ALONG_HI_M and abs(
        lat_left_m
    ) <= _SEE_LAT_M


def _wp_key(wp: Any) -> tuple[float, float, int]:
    loc = wp.transform.location
    return (round(float(loc.x), 0), round(float(loc.y), 0), int(getattr(wp, "lane_id", 0)))


def _flood_start_wp(world: Any, ego_tf: Any) -> Any:
    import carla  # type: ignore

    try:
        return world.get_map().get_waypoint(
            ego_tf.location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:  # noqa: BLE001
        return None


def _flood_remember(tf: Any, have: set[tuple[float, float]]) -> None:
    global _flood_tfs
    try:
        loc = tf.location
        tkey = (round(float(loc.x), 0), round(float(loc.y), 0))
    except Exception:  # noqa: BLE001
        return
    if tkey in have:
        return
    _flood_tfs.append(tf)
    have.add(tkey)


def _flood_prune(ego_tf: Any) -> None:
    global _flood_tfs
    el = ego_tf.location
    keep_r2 = (float(_BUBBLE_M) + float(_CELL_M)) ** 2
    kept: list[Any] = []
    for tf in _flood_tfs:
        try:
            loc = tf.location
            dx = float(loc.x) - float(el.x)
            dy = float(loc.y) - float(el.y)
        except Exception:  # noqa: BLE001
            continue
        if dx * dx + dy * dy <= keep_r2:
            kept.append(tf)
    _flood_tfs = kept


def _flood_take_wp(wp: Any, el: Any, have: set[tuple[float, float]]) -> None:
    try:
        loc = wp.transform.location
        dx = float(loc.x) - float(el.x)
        dy = float(loc.y) - float(el.y)
    except Exception:  # noqa: BLE001
        return
    if dx * dx + dy * dy > float(_BUBBLE_M) * float(_BUBBLE_M):
        return
    try:
        tf = tf_on_lane(wp)
    except Exception:  # noqa: BLE001
        tf = wp.transform
    _flood_remember(tf, have)


def _flood_ring(world: Any, ego_tf: Any) -> None:
    """One ring from current ego: next/prev/sides/opposite of start only."""
    start = _flood_start_wp(world, ego_tf)
    if start is None:
        return
    el = ego_tf.location
    have = {
        (round(float(tf.location.x), 0), round(float(tf.location.y), 0))
        for tf in _flood_tfs
    }
    seeds: list[Any] = [start]
    try:
        seeds.extend(list(start.next(_FLOOD_STEP_M) or []))
        seeds.extend(list(start.previous(_FLOOD_STEP_M) or []))
    except Exception:  # noqa: BLE001
        pass
    try:
        for side in (start.get_left_lane(), start.get_right_lane(), _opposite_wp(start)):
            if side is not None:
                seeds.append(side)
    except Exception:  # noqa: BLE001
        pass
    extra: list[Any] = []
    for wp in seeds:
        extra.append(wp)
        try:
            extra.extend(list(wp.next(_FLOOD_STEP_M) or []))
            extra.extend(list(wp.previous(_FLOOD_STEP_M) or []))
        except Exception:  # noqa: BLE001
            pass
        try:
            left = wp.get_left_lane()
            right = wp.get_right_lane()
            if left is not None:
                extra.append(left)
            if right is not None:
                extra.append(right)
        except Exception:  # noqa: BLE001
            pass
    seen: set[tuple[float, float, int]] = set()
    n = 0
    for wp in extra:
        if n >= _FLOOD_RING_N:
            break
        try:
            key = _wp_key(wp)
        except Exception:  # noqa: BLE001
            continue
        if key in seen:
            continue
        seen.add(key)
        n += 1
        _flood_take_wp(wp, el, have)


def _flood_cold(world: Any, ego_tf: Any) -> None:
    """First fill only. Opposite once from start — not on every hop."""
    start = _flood_start_wp(world, ego_tf)
    if start is None:
        return
    el = ego_tf.location
    have: set[tuple[float, float]] = set()
    seen: set[tuple[float, float, int]] = set()
    q: list[Any] = [start]
    try:
        opp = _opposite_wp(start)
        if opp is not None:
            q.append(opp)
    except Exception:  # noqa: BLE001
        pass
    hops = 0
    r2 = float(_BUBBLE_M) * float(_BUBBLE_M)
    while q and hops < _FLOOD_MAX_N:
        wp = q.pop()
        try:
            key = _wp_key(wp)
        except Exception:  # noqa: BLE001
            continue
        if key in seen:
            continue
        seen.add(key)
        hops += 1
        try:
            loc = wp.transform.location
            dx = float(loc.x) - float(el.x)
            dy = float(loc.y) - float(el.y)
        except Exception:  # noqa: BLE001
            continue
        if dx * dx + dy * dy > r2:
            continue
        _flood_take_wp(wp, el, have)
        try:
            for nxt in list(wp.next(_FLOOD_STEP_M) or []) + list(wp.previous(_FLOOD_STEP_M) or []):
                q.append(nxt)
        except Exception:  # noqa: BLE001
            pass
        try:
            for side in (wp.get_left_lane(), wp.get_right_lane()):
                if side is not None:
                    q.append(side)
        except Exception:  # noqa: BLE001
            pass


def _flood_walk(world: Any, ego_tf: Any, *, ring_only: bool = False) -> list[Any]:
    """Same cell → reuse. keep_ego / new cell → one ring. Cold start → bounded flood."""
    global _flood_cell
    el = ego_tf.location
    cell = ego_cell(float(el.x), float(el.y))
    if cell == _flood_cell and _flood_tfs:
        return _flood_tfs
    if ring_only or _flood_tfs:
        _flood_ring(world, ego_tf)
    else:
        _flood_cold(world, ego_tf)
    _flood_prune(ego_tf)
    _flood_cell = cell
    return _flood_tfs


def flood_candidates(
    world: Any,
    ego_tf: Any,
    exam_end: float,
    *,
    light: bool = False,
) -> list[tuple[str, Any]]:
    """Classify cached flood transforms. keep_ego skips junction waypoint tables."""
    tfs = _flood_walk(world, ego_tf, ring_only=light)
    out: list[tuple[str, Any]] = []
    for tf in tfs:
        rel = _ego_rel(ego_tf, tf.location)
        if rel is None:
            continue
        slot = classify_spawn(ego_tf, tf)
        if slot == "host":
            slot = "host_far" if rel[0] >= exam_end else "host"
        if slot == "skip" or slot == "host":
            continue
        if not spawn_band_ok(slot, rel[0], exam_end_m=exam_end):
            continue
        out.append((slot, tf))
    if not light:
        try:
            out.extend(_xing_candidates(ego_tf, world.get_map()))
        except Exception:  # noqa: BLE001
            pass
    random.shuffle(out)
    return out


def should_cull_live(slot: str, z_m: float) -> bool:
    """Only exam-tube, gone-far, or fallen. Junctions stay."""
    if float(z_m) < -1.0:
        return True
    return slot in ("far", "host")


def allow_ambient_peds(
    tag: str = "",
    meta: Optional[dict[str, Any]] = None,
    *,
    keep_ego: bool = False,
) -> bool:
    """keep_ego has no exam VRU in FOV — sidewalk peds are OK. Cold AEB/VRU skip."""
    if keep_ego:
        return True
    t = (tag or "").strip().lower()
    if any(k in t for k in _VRU_CASE_TAGS):
        return False
    layout = str((meta or {}).get("layout") or "").strip().lower()
    if any(k in layout for k in _VRU_CASE_TAGS):
        return False
    kind = str((meta or {}).get("vru_kind") or "").strip().lower()
    if kind in ("walker", "bike", "bicycle"):
        return False
    return True


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
    if role == "" or role == "autopilot":
        return True
    return False


def _is_ambient_ped(actor: Any) -> bool:
    role = _role_of(actor)
    if role in _PROTECTED_ROLES:
        return False
    return role.startswith(ROLE_TRAFFIC_PED_PREFIX)


def count_ambient(world: Any) -> int:
    n = 0
    for v in world.get_actors().filter("vehicle.*"):
        if _is_ambient(v):
            n += 1
    return n


def _next_role(prefix: str = ROLE_TRAFFIC_PREFIX) -> str:
    global _role_seq
    _role_seq += 1
    return f"{prefix}{_role_seq}"


def _clear_ambient(world: Any) -> int:
    n = 0
    for v in list(world.get_actors().filter("vehicle.*")):
        if not _is_ambient(v):
            continue
        try:
            v.destroy()
            n += 1
        except Exception:  # noqa: BLE001
            pass
    for w in list(world.get_actors().filter("walker.*")):
        if not _is_ambient_ped(w):
            continue
        try:
            w.destroy()
            n += 1
        except Exception:  # noqa: BLE001
            pass
    if n:
        try:
            world.tick()
        except Exception:  # noqa: BLE001
            pass
    return n


def _driving_wp_at(world: Any, location: Any) -> Optional[Any]:
    import carla  # type: ignore

    try:
        wp = world.get_map().get_waypoint(
            location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:  # noqa: BLE001
        return None
    if wp is None:
        return None
    try:
        if int(wp.lane_type) != int(carla.LaneType.Driving):
            return None
    except Exception:  # noqa: BLE001
        pass
    try:
        wloc = wp.transform.location
        lat = math.hypot(
            float(location.x) - float(wloc.x), float(location.y) - float(wloc.y)
        )
        if lat > _MAX_OFF_LANE_M:
            return None
    except Exception:  # noqa: BLE001
        return None
    return wp


def _on_driving_road(world: Any, actor: Any) -> bool:
    try:
        return _driving_wp_at(world, actor.get_location()) is not None
    except Exception:  # noqa: BLE001
        return False


def _ego_rel(ego_tf: Any, loc: Any) -> tuple[float, float] | None:
    """along = forward m, lat_left = left m."""
    try:
        el = ego_tf.location
        yaw = math.radians(float(ego_tf.rotation.yaw))
        fx, fy = math.cos(yaw), math.sin(yaw)
        dx = float(loc.x) - float(el.x)
        dy = float(loc.y) - float(el.y)
        along = dx * fx + dy * fy
        lat_left = -dx * fy + dy * fx
        return along, lat_left
    except Exception:  # noqa: BLE001
        return None


def _yaw_delta_deg(a_deg: float, b_deg: float) -> float:
    return abs((float(a_deg) - float(b_deg) + 180.0) % 360.0 - 180.0)


def same_direction(ego_tf: Any, spawn_tf: Any, *, max_deg: float = 55.0) -> bool:
    try:
        return _yaw_delta_deg(ego_tf.rotation.yaw, spawn_tf.rotation.yaw) <= max_deg
    except Exception:  # noqa: BLE001
        return False


def classify_spawn(
    ego_tf: Any,
    spawn_tf: Any,
    *,
    lane_w_m: float = _LANE_W_M,
    carriage_m: float = _CARRIAGE_M,
) -> str:
    """host | left_ahead | left_behind | right_ahead | right_behind | oncoming | skip."""
    if not same_direction(ego_tf, spawn_tf):
        return "oncoming"
    rel = _ego_rel(ego_tf, spawn_tf.location)
    if rel is None:
        return "oncoming"
    along, lat_left = rel
    if abs(lat_left) > carriage_m:
        return "oncoming"
    half = 0.5 * float(lane_w_m)
    adj = half + float(lane_w_m)
    if abs(lat_left) <= half:
        return "host"
    if along > -8.0 and along < 12.0:
        return "skip"
    pace = "ahead" if along >= 18.0 else ("behind" if along <= -18.0 else "skip")
    if pace == "skip":
        return "skip"
    if half < lat_left <= adj:
        return f"left_{pace}"
    if -adj <= lat_left < -half:
        return f"right_{pace}"
    return "skip"


def spawn_slot(ego_tf: Any, spawn_tf: Any, **kwargs: Any) -> str:
    """Back-compat alias for classify_spawn."""
    return classify_spawn(ego_tf, spawn_tf, **kwargs)


def classify_live(
    ego_tf: Any,
    other_tf: Any,
    *,
    exam_end_m: float = _EXAM_AHEAD_MIN_M,
    lane_w_m: float = _LANE_W_M,
    carriage_m: float = _CARRIAGE_M,
) -> str:
    """Bubble-aware live class: far | host | host_far | crossing | lane slots | skip."""
    rel = _ego_rel(ego_tf, other_tf.location)
    if rel is None:
        return "far"
    along, lat_left = rel
    if abs(along) > _CULL_M or math.hypot(along, lat_left) > _CULL_M:
        return "far"
    try:
        yaw_d = _yaw_delta_deg(ego_tf.rotation.yaw, other_tf.rotation.yaw)
    except Exception:  # noqa: BLE001
        yaw_d = 0.0
    if 70.0 <= yaw_d <= 110.0:
        return "crossing"
    slot = classify_spawn(
        ego_tf, other_tf, lane_w_m=lane_w_m, carriage_m=carriage_m
    )
    if slot == "host":
        if in_exam_tube(along, lat_left, exam_end_m, lane_w_m=lane_w_m):
            return "host"
        return "host_far"
    return slot


def _fixture_along_m(world: Any, ego_tf: Any, fixture: Any | None) -> Optional[float]:
    actors: list[Any] = []
    if fixture is not None:
        actors.append(fixture)
    for role in (ROLE_LEAD, "vru", "hazard"):
        try:
            a = find_by_role(world, role)
        except Exception:  # noqa: BLE001
            a = None
        if a is not None:
            actors.append(a)
    best: Optional[float] = None
    for a in actors:
        try:
            rel = _ego_rel(ego_tf, a.get_location())
        except Exception:  # noqa: BLE001
            continue
        if rel is None or rel[0] <= 0.5:
            continue
        if best is None or rel[0] < best:
            best = rel[0]
    return best


def _tm_speed_diff(kind: str, slot: str) -> float:
    if slot == "crossing":
        return random.uniform(8.0, 22.0)
    if slot.endswith("_ahead") or kind == "truck" or slot == "host_far":
        return random.uniform(38.0, 55.0)
    if slot.endswith("_behind"):
        return random.uniform(-28.0, -12.0)
    if kind == "motorcycle":
        return random.uniform(-12.0, 6.0)
    return random.uniform(-8.0, 12.0)


def _seed_speed_mps(kind: str, slot: str) -> float:
    if slot == "crossing":
        return random.uniform(6.0, 9.0)
    if slot.endswith("_ahead") or kind == "truck" or slot == "host_far":
        return random.uniform(7.0, 9.5)
    if slot.endswith("_behind"):
        return random.uniform(16.0, 20.0)
    return 12.0


def _configure_tm(tm: Any, vehicle: Any, *, density: int, kind: str, slot: str) -> None:
    del density
    try:
        tm.vehicle_percentage_speed_difference(vehicle, _tm_speed_diff(kind, slot))
        tm.ignore_lights_percentage(vehicle, 0.0)
        tm.auto_lane_change(vehicle, False)
        tm.distance_to_leading_vehicle(vehicle, random.uniform(10.0, 16.0))
    except Exception:  # noqa: BLE001
        pass
    try:
        tm.ignore_signs_percentage(vehicle, 0.0)
    except Exception:  # noqa: BLE001
        pass


def _empty_slot_counts() -> dict[str, int]:
    return {k: 0 for k in (*_FILL_ORDER, "host")}


def _count_near(
    world: Any,
    ego_tf: Any,
    exam_end: float,
) -> tuple[dict[str, int], int]:
    slots = _empty_slot_counts()
    near = 0
    for v in world.get_actors().filter("vehicle.*"):
        if not _is_ambient(v):
            continue
        try:
            slot = classify_live(ego_tf, v.get_transform(), exam_end_m=exam_end)
        except Exception:  # noqa: BLE001
            continue
        if slot == "far":
            continue
        near += 1
        if slot in slots:
            slots[slot] += 1
        elif slot == "skip":
            pass
        else:
            slots[slot] = slots.get(slot, 0) + 1
    return slots, near


def _count_peds_near(world: Any, ego_tf: Any) -> int:
    n = 0
    for w in world.get_actors().filter("walker.*"):
        if not _is_ambient_ped(w):
            continue
        try:
            rel = _ego_rel(ego_tf, w.get_location())
        except Exception:  # noqa: BLE001
            continue
        if rel is None:
            continue
        if math.hypot(rel[0], rel[1]) <= _CULL_M:
            n += 1
    return n


def _note_seen5(world: Any, ego_tf: Any) -> int:
    """Unique see-cone entries in the rolling 5 s window."""
    global _seen5_events
    now = time.time()
    _seen5_events = prune_seen5(now, _seen5_events)
    have = {aid for _, aid in _seen5_events}

    def _maybe(actor: Any) -> None:
        try:
            rel = _ego_rel(ego_tf, actor.get_location())
            aid = int(actor.id)
        except Exception:  # noqa: BLE001
            return
        if rel is None or not in_see_cone(rel[0], rel[1]):
            return
        if aid in have:
            return
        _seen5_events.append((now, aid))
        have.add(aid)

    for v in world.get_actors().filter("vehicle.*"):
        if _is_ambient(v):
            _maybe(v)
    for w in world.get_actors().filter("walker.*"):
        if _is_ambient_ped(w) or _role_of(w) == "vru":
            _maybe(w)
    return seen5_count(_seen5_events, now)


def _cull_bubble(world: Any, ego_tf: Any, exam_end: float) -> tuple[int, list[Any]]:
    n = 0
    dead: list[Any] = []
    for v in list(world.get_actors().filter("vehicle.*")):
        if not _is_ambient(v):
            continue
        try:
            tf = v.get_transform()
            slot = classify_live(ego_tf, tf, exam_end_m=exam_end)
            z = float(tf.location.z)
        except Exception:  # noqa: BLE001
            slot, z = "far", -9.0
        if not should_cull_live(slot, z):
            continue
        try:
            dead.append(tf.location)
            v.destroy()
            n += 1
        except Exception:  # noqa: BLE001
            pass
    for w in list(world.get_actors().filter("walker.*")):
        if not _is_ambient_ped(w):
            continue
        drop = False
        loc = None
        try:
            loc = w.get_location()
            rel = _ego_rel(ego_tf, loc)
            drop = (
                rel is None
                or math.hypot(rel[0], rel[1]) > _CULL_M
                or float(loc.z) < -1.0
            )
        except Exception:  # noqa: BLE001
            drop = True
        if drop:
            try:
                if loc is not None:
                    dead.append(loc)
                w.destroy()
                n += 1
            except Exception:  # noqa: BLE001
                pass
    return n, dead


def _blocked_locs(world: Any, extra: Optional[Any] = None) -> list[Any]:
    locs: list[Any] = []
    for role in (ROLE_EGO, ROLE_LEAD, "vru", "hazard"):
        a = find_by_role(world, role)
        if a is not None:
            try:
                locs.append(a.get_location())
            except Exception:  # noqa: BLE001
                pass
    if extra is not None:
        try:
            locs.append(extra.get_location())
        except Exception:  # noqa: BLE001
            pass
    for v in world.get_actors().filter("vehicle.*"):
        try:
            locs.append(v.get_location())
        except Exception:  # noqa: BLE001
            continue
    return locs


def _too_close(loc: Any, blocked: list[Any], *, min_m: float = 10.0) -> bool:
    r2 = min_m * min_m
    try:
        x, y = float(loc.x), float(loc.y)
    except Exception:  # noqa: BLE001
        return True
    for b in blocked:
        try:
            if (x - float(b.x)) ** 2 + (y - float(b.y)) ** 2 < r2:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _opposite_wp(wp: Any) -> Optional[Any]:
    cur = wp
    try:
        base_yaw = float(wp.transform.rotation.yaw)
    except Exception:  # noqa: BLE001
        return None
    for _ in range(6):
        try:
            nxt = cur.get_left_lane()
        except Exception:  # noqa: BLE001
            return None
        if nxt is None:
            return None
        try:
            yaw = float(nxt.transform.rotation.yaw)
        except Exception:  # noqa: BLE001
            cur = nxt
            continue
        if _yaw_delta_deg(base_yaw, yaw) > 120.0:
            return nxt
        cur = nxt
    return None


def _xing_candidates(ego_tf: Any, mmap: Any) -> list[tuple[str, Any]]:
    import carla  # type: ignore

    try:
        ego_wp = mmap.get_waypoint(
            ego_tf.location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:  # noqa: BLE001
        return []
    if ego_wp is None:
        return []
    cur = ego_wp
    junc = None
    walked = 0.0
    while walked < _BUBBLE_M:
        try:
            nxts = cur.next(4.0)
        except Exception:  # noqa: BLE001
            break
        if not nxts:
            break
        cur = nxts[0]
        walked += 4.0
        if getattr(cur, "is_junction", False):
            try:
                junc = cur.get_junction()
            except Exception:  # noqa: BLE001
                junc = None
            break
    if junc is None:
        return []
    out: list[tuple[str, Any]] = []
    try:
        pairs = list(junc.get_waypoints(carla.LaneType.Driving) or [])
    except Exception:  # noqa: BLE001
        pairs = []
    if len(pairs) > _XING_PAIR_CAP:
        pairs = pairs[:_XING_PAIR_CAP]
    ego_yaw = float(ego_tf.rotation.yaw)
    for pair in pairs:
        try:
            entry = pair[0]
        except Exception:  # noqa: BLE001
            continue
        try:
            yaw = float(entry.transform.rotation.yaw)
        except Exception:  # noqa: BLE001
            continue
        if not (70.0 <= _yaw_delta_deg(ego_yaw, yaw) <= 110.0):
            continue
        tf = entry.transform
        try:
            prevs = entry.previous(8.0)
            if prevs:
                tf = tf_on_lane(prevs[0])
        except Exception:  # noqa: BLE001
            pass
        rel = _ego_rel(ego_tf, tf.location)
        if rel is None or not spawn_band_ok("crossing", rel[0]):
            continue
        out.append(("crossing", tf))
    return out


def _corridor_candidates(
    world: Any,
    ego_tf: Any,
    exam_end: float,
) -> list[tuple[str, Any]]:
    return flood_candidates(world, ego_tf, exam_end)


def _arm_vehicle(
    tm: Any,
    actor: Any,
    *,
    density: int,
    kind: str,
    slot: str,
    session: Any = None,
) -> bool:
    try:
        if session is not None:
            session.ap_on(actor)
        else:
            actor.set_autopilot(True, tm.get_port())
        _configure_tm(tm, actor, density=density, kind=kind, slot=slot)
        roll_npc(actor, _seed_speed_mps(kind, slot))
        return True
    except Exception:  # noqa: BLE001
        try:
            actor.destroy()
        except Exception:  # noqa: BLE001
            pass
        return False


def _spawn_one(
    world: Any,
    tm: Any,
    buckets: dict[str, list[Any]],
    slot: str,
    tf: Any,
    blocked: list[Any],
    *,
    density: int,
    session: Any = None,
) -> bool:
    if _too_close(tf.location, blocked):
        return False
    bp = _pick_ambient_bp(buckets, slot=slot)
    if bp is None:
        return False
    kind = ambient_bp_kind(bp.id)
    if bp.has_attribute("role_name"):
        bp.set_attribute("role_name", _next_role())
    if bp.has_attribute("color"):
        try:
            bp.set_attribute(
                "color", random.choice(bp.get_attribute("color").recommended_values)
            )
        except Exception:  # noqa: BLE001
            pass
    actor = world.try_spawn_actor(bp, tf)
    if actor is None:
        return False
    if not _arm_vehicle(
        tm, actor, density=density, kind=kind, slot=slot, session=session
    ):
        return False
    blocked.append(tf.location)
    return True


def _ped_candidates(ego_tf: Any, mmap: Any) -> list[Any]:
    """Sidewalk-ish poses 25–60 m ahead, 4–8 m off center — in the windshield."""
    try:
        ego_wp = mmap.get_waypoint(
            ego_tf.location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:  # noqa: BLE001
        return []
    if ego_wp is None:
        return []
    tfs: list[Any] = []
    for dist in (28.0, 38.0, 48.0, 58.0):
        try:
            nxts = ego_wp.next(dist) or []
        except Exception:  # noqa: BLE001
            nxts = []
        for wp in nxts:
            if getattr(wp, "is_junction", False):
                continue
            for right_m in (5.6, -5.6):
                try:
                    tf = offset_transform(wp.transform, right_m=right_m)
                    tf.location.z = float(wp.transform.location.z) + 1.0
                except Exception:  # noqa: BLE001
                    continue
                rel = _ego_rel(ego_tf, tf.location)
                if rel is None or not in_see_cone(rel[0], rel[1]):
                    continue
                if abs(rel[1]) < 3.2:
                    continue
                tfs.append(tf)
    random.shuffle(tfs)
    return tfs


def _spawn_peds(
    carla_mod: Any,
    world: Any,
    ego_tf: Any,
    *,
    need: int,
    log_prefix: str,
    avoid: Optional[list[Any]] = None,
) -> int:
    del log_prefix
    if need <= 0:
        return 0
    try:
        mmap = world.get_map()
    except Exception:  # noqa: BLE001
        return 0
    lib = world.get_blueprint_library()
    bps = list(lib.filter("walker.pedestrian.*"))
    if not bps:
        return 0
    got = 0
    blocked = _blocked_locs(world)
    if avoid:
        blocked.extend(avoid)
    yaw = math.radians(float(ego_tf.rotation.yaw))
    fx, fy = math.cos(yaw), math.sin(yaw)
    for tf in _ped_candidates(ego_tf, mmap):
        if got >= need:
            break
        if _too_close(tf.location, blocked, min_m=6.0):
            continue
        bp = random.choice(bps)
        if bp.has_attribute("role_name"):
            bp.set_attribute("role_name", _next_role(ROLE_TRAFFIC_PED_PREFIX))
        w = world.try_spawn_actor(bp, tf)
        if w is None:
            continue
        try:
            w.apply_control(
                carla_mod.WalkerControl(
                    direction=carla_mod.Vector3D(fx, fy, 0.0),
                    speed=1.2,
                )
            )
        except Exception:  # noqa: BLE001
            pass
        blocked.append(tf.location)
        got += 1
    return got


def _log_bubble(
    log_prefix: str,
    *,
    number: int,
    near: int,
    slots: dict[str, int],
    ped: int,
    evicted: int,
    added: int,
    seed: bool,
    seen5: int = 0,
) -> None:
    print(
        f"{log_prefix} bubble seen5={seen5}/{number} near={near} "
        f"L+={slots.get('left_ahead', 0)} L-={slots.get('left_behind', 0)} "
        f"R+={slots.get('right_ahead', 0)} R-={slots.get('right_behind', 0)} "
        f"oncoming={slots.get('oncoming', 0)} xing={slots.get('crossing', 0)} "
        f"ped={ped} host={slots.get('host', 0)} "
        f"evicted={evicted} +{added} "
        f"{'seed' if seed else 'tick'} (exam empty)",
        flush=True,
    )


def _fill_slots(
    world: Any,
    tm: Any,
    ego_tf: Any,
    exam_end: float,
    buckets: dict[str, list[Any]],
    *,
    density: int,
    target: int,
    max_add: int,
    tick_after: bool,
    avoid: Optional[list[Any]] = None,
    light: bool = False,
    session: Any = None,
) -> int:
    if max_add <= 0 or target <= 0:
        return 0
    slots, near = _count_near(world, ego_tf, exam_end)
    room = max(0, target - near)
    budget = min(max_add, room)
    if budget <= 0:
        return 0
    caps = slot_caps_for_target(target)
    blocked = _blocked_locs(world)
    added = 0
    cands = flood_candidates(world, ego_tf, exam_end, light=light)

    def _try_list(items: list[tuple[str, Any]], *, honor_caps: bool) -> None:
        nonlocal added
        for slot, tf in items:
            if added >= budget:
                return
            if honor_caps and slots.get(slot, 0) >= caps.get(slot, 0):
                continue
            if slot == "host":
                continue
            if avoid and _too_close(tf.location, avoid, min_m=_EVICT_REPLAY_M):
                continue
            if _spawn_one(
                world,
                tm,
                buckets,
                slot,
                tf,
                blocked,
                density=density,
                session=session,
            ):
                slots[slot] = slots.get(slot, 0) + 1
                added += 1

    _try_list(cands, honor_caps=True)
    if added < budget:
        _try_list(cands, honor_caps=False)
    if tick_after and added:
        try:
            world.tick()
        except Exception:  # noqa: BLE001
            pass
    return added


def _prep_tm(client: Any, *, session: Any = None) -> Any:
    if session is not None:
        tm = session.tm
    else:
        from _carla_env import get_traffic_manager

        tm = get_traffic_manager(client)
    try:
        tm.set_hybrid_physics_mode(True)
        tm.set_hybrid_physics_radius(_BUBBLE_M)
    except Exception:  # noqa: BLE001
        pass
    return tm


def _topup_budget(*, seen5: int, number: int, near_n: int, live: int, evicted: int) -> int:
    """How many ambient to add this maintain/seed pulse."""
    if number <= 0 or live <= 0:
        return 0
    if near_n >= live:
        return 0
    room = live - near_n
    if seen5 < number:
        return min(_MAX_PER_MAINTAIN, room)
    return min(_MAX_PER_MAINTAIN, evicted, room)


def ensure_ambient_traffic(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    near: Optional[Any] = None,
    rebuild: bool = True,
    log_prefix: str = "[traffic]",
    allow_peds: bool = True,
    fixture: Any | None = None,
    session: Any = None,
) -> int:
    """Seed the local bubble from the *current* ego. rebuild wipes leftover stock."""
    global _maintain_last_s, _seen5_events, _flood_cell, _flood_tfs

    snap = getattr(session, "snap", None) if session is not None else None
    number = traffic_number(snap)
    live = live_stock_cap(number)
    _maintain_last_s = 0.0
    if rebuild:
        _seen5_events = []
        _flood_cell = None
        _flood_tfs = []
    if number <= 0:
        if rebuild:
            _clear_ambient(world)
        print(f"{log_prefix} bubble off number=0", flush=True)
        return 0

    ego_tf = None
    if near is not None:
        try:
            ego_tf = near.get_transform()
        except Exception:  # noqa: BLE001
            ego_tf = None
    if ego_tf is None:
        ego = find_by_role(world, ROLE_EGO)
        if ego is not None:
            try:
                ego_tf = ego.get_transform()
            except Exception:  # noqa: BLE001
                ego_tf = None
    if ego_tf is None:
        print(f"{log_prefix} bubble skip (no ego pose)", flush=True)
        return 0

    t_seed = time.time()
    print(
        f"{log_prefix} seed enter rebuild={int(rebuild)} "
        f"(ego flood + cell cache)",
        flush=True,
    )
    cleared = 0
    if rebuild:
        cleared = _clear_ambient(world)
    exam_end = exam_window_end_m(_fixture_along_m(world, ego_tf, fixture))
    evicted, avoid = _cull_bubble(world, ego_tf, exam_end)
    print(
        f"{log_prefix} seed culled={cleared + evicted} dt={time.time() - t_seed:0.2f}s",
        flush=True,
    )
    added = 0
    ped = 0
    try:
        if rebuild:
            t_fill = time.time()
            tm = _prep_tm(client, session=session)
            buckets = _cached_buckets(world)
            print(
                f"{log_prefix} seed fill light=0 max_add={min(8, number)} "
                f"prep={time.time() - t_fill:0.2f}s",
                flush=True,
            )
            if any(buckets.values()):
                added = _fill_slots(
                    world,
                    tm,
                    ego_tf,
                    exam_end,
                    buckets,
                    density=0,
                    target=live,
                    max_add=min(8, number),
                    tick_after=True,
                    avoid=avoid,
                    light=False,
                    session=session,
                )
            print(
                f"{log_prefix} seed filled +{added} dt={time.time() - t_fill:0.2f}s",
                flush=True,
            )
            if allow_peds:
                have_ped = _count_peds_near(world, ego_tf)
                ped = _spawn_peds(
                    carla_mod,
                    world,
                    ego_tf,
                    need=max(0, _MAX_PEDS - have_ped),
                    log_prefix=log_prefix,
                    avoid=avoid,
                )
                if ped:
                    try:
                        world.tick()
                    except Exception:  # noqa: BLE001
                        pass
        else:
            print(
                f"{log_prefix} seed fill skip spawn keep_ego culled={cleared + evicted} "
                f"(top-up on tick)",
                flush=True,
            )
    except Exception as exc:  # noqa: BLE001
        print(
            f"{log_prefix} seed fail after culled: {type(exc).__name__}: {exc}",
            flush=True,
        )
        raise
    slots, near_n = _count_near(world, ego_tf, exam_end)
    ped_n = _count_peds_near(world, ego_tf)
    seen5 = _note_seen5(world, ego_tf)
    _log_bubble(
        log_prefix,
        number=number,
        near=near_n,
        slots=slots,
        ped=ped_n,
        evicted=cleared + evicted,
        added=added + ped,
        seed=True,
        seen5=seen5,
    )
    print(
        f"{log_prefix} seed done dt={time.time() - t_seed:0.2f}s "
        f"near={near_n} +{added + ped}",
        flush=True,
    )
    return near_n


def maintain_ambient_traffic(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    near: Optional[Any] = None,
    fixture: Any | None = None,
    elapsed_s: float = 0.0,
    period_s: float | None = None,
    allow_peds: bool = True,
    log_prefix: str = "[traffic]",
    session: Any = None,
) -> int:
    """Periodic cull; top-up only if bubble stock below cap (not seen5-starved)."""
    global _maintain_last_s

    snap = getattr(session, "snap", None) if session is not None else None
    number = traffic_number(snap)
    if number <= 0:
        return 0
    period = float(period_s) if period_s is not None else maintain_period_s(snap)
    if elapsed_s - _maintain_last_s < period:
        return -1
    _maintain_last_s = elapsed_s

    if near is None:
        near = find_by_role(world, ROLE_EGO)
    if near is None:
        return 0
    try:
        ego_tf = near.get_transform()
    except Exception:  # noqa: BLE001
        return 0

    live = live_stock_cap(number)
    t_m = time.time()
    exam_end = exam_window_end_m(_fixture_along_m(world, ego_tf, fixture))
    evicted, avoid = _cull_bubble(world, ego_tf, exam_end)
    seen5 = _note_seen5(world, ego_tf)
    _slots0, near_n = _count_near(world, ego_tf, exam_end)
    max_add = _topup_budget(
        seen5=seen5, number=number, near_n=near_n, live=live, evicted=evicted
    )
    added = 0
    ped = 0
    if max_add > 0:
        tm = _prep_tm(client, session=session)
        buckets = _cached_buckets(world)
        if any(buckets.values()):
            added = _fill_slots(
                world,
                tm,
                ego_tf,
                exam_end,
                buckets,
                density=0,
                target=live,
                max_add=max_add,
                tick_after=False,
                avoid=avoid,
                light=True,
                session=session,
            )
    if allow_peds:
        have_ped = _count_peds_near(world, ego_tf)
        ped = _spawn_peds(
            carla_mod,
            world,
            ego_tf,
            need=min(2, max(0, _MAX_PEDS - have_ped)),
            log_prefix=log_prefix,
            avoid=avoid,
        )
    seen5 = _note_seen5(world, ego_tf)
    dt_m = time.time() - t_m
    if evicted or added or ped:
        slots, near_n = _count_near(world, ego_tf, exam_end)
        _log_bubble(
            log_prefix,
            number=number,
            near=near_n,
            slots=slots,
            ped=_count_peds_near(world, ego_tf),
            evicted=evicted,
            added=added + ped,
            seed=False,
            seen5=seen5,
        )
        if dt_m > 0.20:
            print(f"{log_prefix} maintain slow dt={dt_m:0.2f}s", flush=True)
        return near_n
    if dt_m > 0.20:
        print(f"{log_prefix} maintain slow dt={dt_m:0.2f}s (no change)", flush=True)
    return 0
