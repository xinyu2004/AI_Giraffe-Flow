"""Case-level layout kwargs — env read only at the orchestration edge.

Layouts must not call ``os.environ``. ``CaseAtom`` merges these kwargs into
``layout(session, keep_ego=…, **kwargs)``.
"""

from __future__ import annotations

import os
from typing import Any


def _f(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _s(key: str, default: str) -> str:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip()


# tag -> kwargs consumed by that case's layout_*
_BY_TAG: dict[str, dict[str, Any]] = {
    "acc": {
        "lead_gap_m": 20.0,
        "lead_speed_diff_pct": 15.0,
    },
    "acc_cut_in": {},  # filled in kwargs_for_case
    "aeb": {},
    "aeb_ccru": {},
    "aeb_intersection_cross": {},
    "aeb_occluded_lateral": {},
    "aeb_pedestrian": {},
    "aeb_bicycle": {},
    "fcw": {},
    "isa_limit_follow": {},
}


def kwargs_for_case(tag: str) -> dict[str, Any]:
    """Build layout kwargs for ``tag`` (process env / defaults). Call once per case."""
    t = (tag or "").strip().lower()

    if t == "acc":
        return {
            "lead_gap_m": _f("GF_ACC_GAP_M", 20.0),
            "lead_speed_diff_pct": _f("GF_ACC_LEAD_DIFF_PCT", 15.0),
        }
    if t == "acc_cut_in":
        return {
            "gap_m": _f("GF_CUTIN_GAP_M", 28.0),
            "side": _s("GF_CUTIN_SIDE", "left").lower(),
            "ego_mps": _f("GF_CUTIN_EGO_MPS", 10.0),
        }
    if t == "aeb":
        return {
            "gap_m": _f("GF_AEB_GAP_M", 40.0),
            "ego_mps": _f("GF_AEB_EGO_MPS", 12.0),
            "layout_name": "aeb_stopped",
        }
    if t == "aeb_ccru":
        return {
            "gap_m": _f("GF_AEB_CCRU_GAP_M", 35.0),
            "ego_mps": _f("GF_AEB_CCRU_EGO_MPS", 11.0),
            "lead_mps": _f("GF_AEB_CCRU_LEAD_MPS", 3.0),
            "layout_name": "aeb_ccru",
        }
    if t in ("aeb_intersection_cross", "aeb_occluded_lateral"):
        out = {
            "gap_m": _f("GF_AEB_X_GAP_M", 32.0),
            "ego_mps": _f("GF_AEB_X_EGO_MPS", 10.0),
            "lateral_m": _f("GF_AEB_X_LAT_M", 6.0),
            "cross_mps": _f("GF_AEB_X_CROSS_MPS", 6.0),
        }
        if t == "aeb_occluded_lateral":
            out["reveal_s"] = _f("GF_AEB_OCC_REVEAL_S", 2.0)
        return out
    if t == "aeb_pedestrian":
        return {
            "gap_m": _f("GF_AEB_PED_GAP_M", 28.0),
            "ego_mps": _f("GF_AEB_PED_EGO_MPS", 8.0),
            "lat_m": _f("GF_AEB_PED_LAT_M", 5.0),
            "ped_speed": _f("GF_AEB_PED_MPS", 1.4),
        }
    if t == "aeb_bicycle":
        return {
            "gap_m": _f("GF_AEB_BIKE_GAP_M", 30.0),
            "ego_mps": _f("GF_AEB_BIKE_EGO_MPS", 10.0),
            "bike_mps": _f("GF_AEB_BIKE_MPS", 4.0),
        }
    if t == "fcw":
        return {
            "gap_m": _f("GF_FCW_GAP_M", 40.0),
            "ego_mps": _f("GF_FCW_EGO_MPS", 12.0),
            "layout_name": "fcw",
        }
    if t == "isa_limit_follow":
        return {
            "lead_gap_m": _f("GF_ISA_GAP_M", 20.0),
            "lead_speed_diff_pct": _f("GF_ISA_LEAD_DIFF_PCT", 15.0),
            "speed_limit_kph": _f("GF_ISA_LIMIT_KPH", 50.0),
        }
    if t == "lka_curve_entry":
        return {"ego_mps": _f("GF_LKA_EGO_MPS", 9.0)}
    if t == "lka_in_curve":
        return {"ego_mps": _f("GF_LKA_EGO_MPS", 8.0)}
    if t == "ldw_drift":
        return {
            "offset_m": _f("GF_LDW_OFFSET_M", 0.6),
            "ego_mps": _f("GF_LDW_EGO_MPS", 8.0),
        }
    if t == "elk_overshoot":
        return {
            "offset_m": _f("GF_ELK_OFFSET_M", 0.9),
            "ego_mps": _f("GF_ELK_EGO_MPS", 9.0),
        }
    if t == "lcc_straight":
        return {"ego_mps": _f("GF_LCC_EGO_MPS", 10.0)}
    if t in ("hlb_oncoming", "env_night_glare"):
        return {"ego_mps": _f("GF_HLB_EGO_MPS", 10.0)}
    if t == "hlb_urban":
        return {"ego_mps": _f("GF_HLB_EGO_MPS", 8.0)}
    if t == "env_night_lead_hb":
        return {"ego_mps": _f("GF_NIGHT_LEAD_EGO_MPS", 9.0)}
    if t == "tsr_speed_limit":
        return {
            "limit_kph": _f("GF_TSR_LIMIT_KPH", 60.0),
            "ego_mps": _f("GF_TSR_EGO_MPS", 12.0),
        }
    if t in ("env_lane_split", "env_lane_merge"):
        return {"ego_mps": _f("GF_ROAD_EGO_MPS", 10.0)}
    if t in ("env_tunnel_entry", "env_tunnel_exit"):
        return {
            "ego_mps": _f("GF_TUNNEL_EGO_MPS", 10.0),
            "switch_s": _f("GF_TUNNEL_SWITCH_S", 3.0),
        }
    return {}
