"""CARLA traffic lights / speed landmarks / static props → DSTSR + STATIC dicts.

No Giraffe imports. Packs into GfFakePercPod v2 tail.
Sign names are gold DSTSR_Sign_Name (e_trafficSignals=164, e_stopAhead=196).
"""

from __future__ import annotations

import math
from typing import Any

from _lane_truth import _wrap_pi, world_to_ego_xy_cs

_MAX_TSR = 6
_MAX_STAT = 6
_RADIUS_M = 80.0

# Gold DSTSR_Sign_Name
E_TRAFFIC_SIGNALS = 164
E_STOP_AHEAD = 196


def _u8(v: Any, default: int = 0) -> int:
    try:
        return int(v) & 0xFF
    except (TypeError, ValueError):
        return default & 0xFF


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
    for tl in lights or []:
        try:
            loc = tl.get_location()
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 2.0 or xf > _RADIUS_M or abs(yf) > 18.0:
                continue
            state = tl.get_state()
            if red is not None and state == red:
                name = E_STOP_AHEAD
            elif yellow is not None and state == yellow:
                name = E_TRAFFIC_SIGNALS
            else:
                continue
            tsr.append({"name": name, "long": xf, "lat": yf, "rel": 0})
        except Exception:  # noqa: BLE001
            continue

    try:
        mmap = world.get_map()
        marks = mmap.get_all_landmarks()
    except Exception:  # noqa: BLE001
        marks = []
    for lm in marks or []:
        try:
            typ = str(getattr(lm, "type", "") or "")
            # OpenDRIVE 206 = maximum speed
            if typ not in ("206", "274"):
                continue
            tf = lm.transform
            loc = tf.location
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 2.0 or xf > _RADIUS_M or abs(yf) > 18.0:
                continue
            name = _speed_sign_name(float(getattr(lm, "value", 0.0) or 0.0))
            if name < 0:
                continue
            tsr.append({"name": name, "long": xf, "lat": yf, "rel": 0})
        except Exception:  # noqa: BLE001
            continue

    tsr.sort(key=lambda it: float(it["long"]))
    tsr = tsr[:_MAX_TSR]
    out["tsr_n"] = len(tsr)
    for i, it in enumerate(tsr):
        out[f"tsr{i}_name"] = int(it["name"])
        out[f"tsr{i}_long"] = float(it["long"])
        out[f"tsr{i}_lat"] = float(it["lat"])
        out[f"tsr{i}_rel"] = _u8(it.get("rel"), 0)

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

    FCM DSTSR still only packs red/yellow (collect_tsr_static). Green is HUD-only
    so the driver can see a junction was recognized.
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
        marks = world.get_map().get_all_landmarks()
    except Exception:  # noqa: BLE001
        marks = []
    lim_best: tuple[float, float] | None = None
    for lm in marks or []:
        try:
            typ = str(getattr(lm, "type", "") or "")
            if typ not in ("206", "274"):
                continue
            loc = lm.transform.location
            xf, yf = world_to_ego_xy_cs(ex, ey, c, s, float(loc.x), float(loc.y))
            if xf < 2.0 or xf > _RADIUS_M or abs(yf) > 18.0:
                continue
            kph = float(getattr(lm, "value", 0.0) or 0.0)
            if kph < 3.0:
                continue
            if lim_best is None or xf < lim_best[0]:
                lim_best = (xf, kph)
        except Exception:  # noqa: BLE001
            continue
    if lim_best is not None:
        out["limit_kph"] = float(lim_best[1])
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
