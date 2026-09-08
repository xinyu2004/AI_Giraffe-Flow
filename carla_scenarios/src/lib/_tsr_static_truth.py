"""CARLA traffic lights / speed landmarks / static props → DSTSR + STATIC dicts.

No Giraffe imports. Packs into GfFakePercPod v2 tail.
Sign names are gold DSTSR_Sign_Name (e_trafficSignals=164, e_stopAhead=196).

ME-style semantics (SIL approx, not a camera tracker):
  - stable m_DSTSR_ID (1–127), not slot index
  - DSTSR_Relevancy from host-corridor |lat| (not always 0)
  - sort: Relevant 196/164 first (readability only; planning must scan all)
"""

from __future__ import annotations

import math
import time
from typing import Any

from _lane_truth import _wrap_pi, world_to_ego_xy_cs

_MAX_TSR = 6
_MAX_STAT = 6
_RADIUS_M = 80.0
# 1:1 gf_plan_cal.reg_stop_behind_m — keep red/yellow after the pole.
_REG_STOP_BEHIND_M = 8.0

# Landmark list is static per map; cache to avoid get_all_landmarks every tick.
_LANDMARK_TTL_S = 2.0
_landmark_cache_key: str = ""
_landmark_cache_at: float = -1e9
_landmark_cache: list[Any] = []


def _cached_landmarks(world: Any) -> list[Any]:
    """Throttle OpenDRIVE landmark scans (Town04 is expensive)."""
    global _landmark_cache_key, _landmark_cache_at, _landmark_cache
    now = time.time()
    key = ""
    try:
        key = str(world.get_map().name)
    except Exception:  # noqa: BLE001
        key = "map"
    if key == _landmark_cache_key and (now - _landmark_cache_at) < _LANDMARK_TTL_S:
        return _landmark_cache
    try:
        marks = list(world.get_map().get_all_landmarks())
    except Exception:  # noqa: BLE001
        marks = []
    _landmark_cache_key = key
    _landmark_cache_at = now
    _landmark_cache = marks
    return marks

# Gold DSTSR_Sign_Name
E_TRAFFIC_SIGNALS = 164  # yellow (abused)
E_STOP_AHEAD = 196       # red (abused)
# SIL green — gold has no green enum; FCM passes through; planning ignores ≠164/196.
E_TRAFFIC_GO = 198
# Gold DSTSR_Sup1_SignName — minimum speed (Sign_Name still holds e_std_*).
E_MINIMUM = 27

# Gold DSTSR_Relevancy
REL_RELEVANT = 0
REL_OTHER_LANE = 2
REL_FAR_IRRELEVANT = 5

# Host corridor half-width (m). Speed signs: tight. Lights: wide (CARLA poles
# sit beside the lane; Foxglove host reds often |lat|≈5–8 — do not mark OTHER).
_REL_HOST_LAT_M = 2.0
_REL_OTHER_LAT_M = 8.0
_REL_LIGHT_HOST_LAT_M = 10.0
_REL_LIGHT_OTHER_LAT_M = 18.0  # align gf_plan_cal.reg_stop_lat_m


def _u8(v: Any, default: int = 0) -> int:
    try:
        return int(v) & 0xFF
    except (TypeError, ValueError):
        return default & 0xFF


def stable_tsr_id(raw: Any, fallback_slot: int = 0) -> int:
    """Map actor/landmark id → gold m_DSTSR_ID range 1–127."""
    try:
        v = int(raw) % 127
    except (TypeError, ValueError):
        v = 0
    if v <= 0:
        v = (int(fallback_slot) % 127) + 1
    return v


def tsr_relevancy(lat_m: float, long_m: float, name: int = -1) -> int:
    """SIL Relevancy heuristic (DSTSR_Relevancy). Lights ≠ speed-sign corridor."""
    lat = abs(float(lat_m))
    lon = float(long_m)
    if lon < -_REG_STOP_BEHIND_M or lon > _RADIUS_M:
        return REL_FAR_IRRELEVANT
    is_light = int(name) in (E_TRAFFIC_SIGNALS, E_STOP_AHEAD, E_TRAFFIC_GO)
    if is_light:
        if lat <= _REL_LIGHT_HOST_LAT_M:
            return REL_RELEVANT
        if lat <= _REL_LIGHT_OTHER_LAT_M:
            return REL_OTHER_LANE
        return REL_FAR_IRRELEVANT
    if lat <= _REL_HOST_LAT_M:
        return REL_RELEVANT
    if lat <= _REL_OTHER_LAT_M:
        return REL_OTHER_LANE
    return REL_FAR_IRRELEVANT


def _tsr_sort_key(it: dict[str, Any]) -> tuple[int, float]:
    """Relevant stop lights first, then by long. Not a planning contract."""
    name = int(it.get("name") or 0)
    rel = int(it.get("rel") or 0)
    stop = 1 if (rel == REL_RELEVANT and name in (E_TRAFFIC_SIGNALS, E_STOP_AHEAD)) else 0
    # Green after stops (HUD); not a planning stop.
    return (0 if stop else 1, float(it.get("long") or 0.0))


def _speed_sign_name(kph: float) -> int:
    """Map km/h to e_std_* (10→0 … 140→13)."""
    try:
        v = float(kph)
    except (TypeError, ValueError):
        return -1
    if v < 3.0:
        return -1
    if v < 8.0:
        return 100  # e_std_5
    stepped = int(round(v / 10.0) * 10)
    if stepped < 10:
        stepped = 10
    if stepped > 140:
        stepped = 140
    return (stepped // 10) - 1


def _ego_pose(ego: Any) -> tuple[float, float, float, float, float]:
    et = ego.get_transform()
    el = et.location
    yaw = math.radians(float(et.rotation.yaw))
    return float(el.x), float(el.y), math.cos(yaw), math.sin(yaw), yaw


def _landmark_raw_id(lm: Any) -> int:
    rid = getattr(lm, "id", None)
    if rid is not None:
        try:
            return int(rid)
        except (TypeError, ValueError):
            pass
    typ = str(getattr(lm, "type", "") or "")
    try:
        loc = lm.transform.location
        hx = int(round(float(loc.x) * 10.0)) ^ int(round(float(loc.y) * 10.0))
        return (hash((typ, hx)) & 0x7FFFFFFF) or 1
    except Exception:  # noqa: BLE001
        return 1


def collect_tsr_static(ego: Any, world: Any) -> dict[str, Any]:
    """Ahead TSR (lights + speed) and static props. Empty dict fields if CARLA missing."""
    out: dict[str, Any] = {"tsr_n": 0, "stat_n": 0}
    try:
        carla = __import__("carla")
    except ImportError:
        return out

    try:
        ex, ey, c, s, yaw = _ego_pose(ego)
    except Exception:  # noqa: BLE001
        return out

    tsr: list[dict[str, Any]] = []
    try:
        lights = world.get_actors().filter("traffic.traffic_light")
    except Exception:  # noqa: BLE001
        lights = []
    red = getattr(getattr(carla, "TrafficLightState", None), "Red", None)
    yellow = getattr(getattr(carla, "TrafficLightState", None), "Yellow", None)
    green = getattr(getattr(carla, "TrafficLightState", None), "Green", None)
    for tl in lights or []:
        try:
            loc = tl.get_location()
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < -_REG_STOP_BEHIND_M or xf > _RADIUS_M or abs(yf) > 18.0:
                continue
            state = tl.get_state()
            if red is not None and state == red:
                name = E_STOP_AHEAD
            elif yellow is not None and state == yellow:
                name = E_TRAFFIC_SIGNALS
            elif green is not None and state == green:
                name = E_TRAFFIC_GO
            else:
                continue
            raw_id = int(getattr(tl, "id", 0) or 0)
            tsr.append(
                {
                    "id": raw_id,
                    "name": name,
                    "long": xf,
                    "lat": yf,
                    "rel": tsr_relevancy(yf, xf, name),
                }
            )
        except Exception:  # noqa: BLE001
            continue

    try:
        marks = _cached_landmarks(world)
    except Exception:  # noqa: BLE001
        marks = []
    for lm in marks or []:
        try:
            typ = str(getattr(lm, "type", "") or "")
            # OpenDRIVE DE: 274=max, 275=min. Keep 206 as max for maps that use it.
            if typ not in ("206", "274", "275"):
                continue
            tf = lm.transform
            loc = tf.location
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 2.0 or xf > _RADIUS_M or abs(yf) > 18.0:
                continue
            name = _speed_sign_name(float(getattr(lm, "value", 0.0) or 0.0))
            if name < 0:
                continue
            is_min = typ == "275"
            tsr.append(
                {
                    "id": _landmark_raw_id(lm),
                    "name": name,
                    "sup1": E_MINIMUM if is_min else 0,
                    "long": xf,
                    "lat": yf,
                    "rel": tsr_relevancy(yf, xf, name),
                }
            )
        except Exception:  # noqa: BLE001
            continue

    tsr.sort(key=_tsr_sort_key)
    tsr = tsr[:_MAX_TSR]
    out["tsr_n"] = len(tsr)
    for i, it in enumerate(tsr):
        out[f"tsr{i}_id"] = stable_tsr_id(it.get("id"), i)
        out[f"tsr{i}_name"] = int(it["name"])
        out[f"tsr{i}_sup1"] = int(it.get("sup1") or 0)
        out[f"tsr{i}_long"] = float(it["long"])
        out[f"tsr{i}_lat"] = float(it["lat"])
        out[f"tsr{i}_rel"] = _u8(it.get("rel"), REL_RELEVANT)

    stat: list[dict[str, Any]] = []
    try:
        props = world.get_actors().filter("static.*")
    except Exception:  # noqa: BLE001
        props = []
    for actor in props or []:
        try:
            tid = str(getattr(actor, "type_id", "") or "").lower()
            if not any(k in tid for k in ("barrier", "wall", "fence", "guardrail", "container")):
                continue
            tf = actor.get_transform()
            loc = tf.location
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 1.0 or xf > _RADIUS_M or abs(yf) > 12.0:
                continue
            try:
                bb = actor.bounding_box.extent
                ln = max(0.8, float(bb.x) * 2.0)
                wd = max(0.4, float(bb.y) * 2.0)
            except Exception:  # noqa: BLE001
                ln, wd = 2.0, 0.6
            heading = _wrap_pi(math.radians(float(tf.rotation.yaw)) - yaw)
            stat.append(
                {
                    "id": int(getattr(actor, "id", 0) or 0) % 120 + 1,
                    "cls": 1,
                    "assign": 3 if abs(yf) < 1.8 else (2 if yf > 0 else 4),
                    "long": xf,
                    "lat": yf,
                    "heading": heading,
                    "len": ln,
                    "wid": wd,
                }
            )
        except Exception:  # noqa: BLE001
            continue
    stat.sort(key=lambda it: float(it["long"]))
    stat = stat[:_MAX_STAT]
    out["stat_n"] = len(stat)
    for i, it in enumerate(stat):
        out[f"stat{i}_id"] = _u8(it["id"], i + 1) or (i + 1)
        out[f"stat{i}_cls"] = _u8(it["cls"], 1) or 1
        out[f"stat{i}_assign"] = _u8(it["assign"], 3) or 3
        out[f"stat{i}_long"] = float(it["long"])
        out[f"stat{i}_lat"] = float(it["lat"])
        out[f"stat{i}_heading"] = float(it["heading"])
        out[f"stat{i}_len"] = float(it["len"])
        out[f"stat{i}_wid"] = float(it["wid"])
    return out


def hud_light_label(state: Any) -> str | None:
    """CARLA TrafficLightState or name → RED / YEL / GRN."""
    raw = str(getattr(state, "name", state) or "").strip().lower()
    if raw == "red":
        return "RED"
    if raw == "yellow":
        return "YEL"
    if raw == "green":
        return "GRN"
    return None


def collect_hud_signs(ego: Any, world: Any) -> dict[str, Any]:
    """Nearest ahead light (incl. green) and speed landmark for the instrument.

    DSTSR also packs green as E_TRAFFIC_GO=198 (planning ignores; only 164/196 stop).
    """
    out: dict[str, Any] = {
        "sig": None,
        "sig_m": None,
        "limit_kph": None,
        "ped": None,
        "ped_m": None,
    }
    try:
        ex, ey, c, s, _yaw = _ego_pose(ego)
    except Exception:  # noqa: BLE001
        return out
    try:
        lights = world.get_actors().filter("traffic.traffic_light")
    except Exception:  # noqa: BLE001
        lights = []
    best: tuple[float, str] | None = None
    for tl in lights or []:
        try:
            loc = tl.get_location()
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 2.0 or xf > _RADIUS_M or abs(yf) > 18.0:
                continue
            label = hud_light_label(tl.get_state())
            if label is None:
                continue
            if best is None or xf < best[0]:
                best = (xf, label)
        except Exception:  # noqa: BLE001
            continue
    if best is not None:
        out["sig_m"] = float(best[0])
        out["sig"] = best[1]
    try:
        marks = _cached_landmarks(world)
    except Exception:  # noqa: BLE001
        marks = []
    lim_max: tuple[float, float] | None = None
    lim_min: tuple[float, float] | None = None
    for lm in marks or []:
        try:
            typ = str(getattr(lm, "type", "") or "")
            if typ not in ("206", "274", "275"):
                continue
            loc = lm.transform.location
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 2.0 or xf > _RADIUS_M or abs(yf) > 18.0:
                continue
            kph = float(getattr(lm, "value", 0.0) or 0.0)
            if kph < 3.0:
                continue
            if typ == "275":
                if lim_min is None or xf < lim_min[0]:
                    lim_min = (xf, kph)
            else:
                if lim_max is None or xf < lim_max[0]:
                    lim_max = (xf, kph)
        except Exception:  # noqa: BLE001
            continue
    if lim_max is not None:
        out["limit_kph"] = float(lim_max[1])
    if lim_min is not None:
        out["limit_min_kph"] = float(lim_min[1])
    try:
        walkers = world.get_actors().filter("walker.*")
    except Exception:  # noqa: BLE001
        walkers = []
    ped_best: tuple[float, str] | None = None
    for w in walkers or []:
        try:
            loc = w.get_location()
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 2.0 or xf > _RADIUS_M or abs(yf) > 14.0:
                continue
            if ped_best is None or xf < ped_best[0]:
                ped_best = (xf, "PED")
        except Exception:  # noqa: BLE001
            continue
    if ped_best is not None:
        out["ped_m"] = float(ped_best[0])
        out["ped"] = ped_best[1]
    return out
