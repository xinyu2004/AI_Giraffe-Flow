"""Closing / AEB-family layouts (stopped or slow hazard ahead)."""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from spawn.ic import (
    aeb_ego_seed,
    closing_along_heading,
    closing_along_pose,
    closing_toward_lead,
)
from spawn.pick import offset_transform
from spawn.place import spawn_ego_lead, spawn_named
from spawn.roles import ROLE_LEAD, safe_destroy
from _verdict import CmdProbe, release_ego


def _hold_brake(carla_mod: Any, vehicle: Any) -> None:
    try:
        vehicle.set_autopilot(False)
        vehicle.apply_control(
            carla_mod.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)
        )
    except Exception:  # noqa: BLE001
        pass


def layout_aeb_stopped(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
    gap_env: str = "GF_AEB_GAP_M",
    ego_env: str = "GF_AEB_EGO_MPS",
    default_gap: float = 40.0,
    default_ego: float = 12.0,
    layout_name: str = "aeb_stopped",
) -> Tuple[Any, Any, dict[str, Any]]:
    del client
    gap_m = float(os.environ.get(gap_env) or default_gap)
    ego_mps = float(os.environ.get(ego_env) or default_ego)
    ego, lead = spawn_ego_lead(
        world,
        lead_gap_m=gap_m,
        reset=True,
        require_straight=True,
        keep_ego=keep_ego,
    )
    release_ego(carla_mod, ego)
    const_on = False
    if keep_ego:
        print(
            f"[layout] {layout_name} keep_ego: no park-teleport / no ego seed",
            flush=True,
        )
    else:
        _hold_brake(carla_mod, lead)
        aeb_ego_seed(True)
        try:
            const_on = closing_toward_lead(carla_mod, ego, ego_mps, lead)
        finally:
            aeb_ego_seed(False)
    ttc = gap_m / max(ego_mps, 0.1)
    print(
        f"[layout] {layout_name} gap≈{gap_m:.0f}m ego_v≈{ego_mps:.1f} "
        f"TTC≈{ttc:.1f}s const={int(const_on)} ic=aeb_ego_seed+closing_toward_lead",
        flush=True,
    )
    return ego, lead, {
        "layout": layout_name,
        "gap_m": gap_m,
        "ego_mps": ego_mps,
        "ttc0": round(ttc, 2),
        "const_vel": const_on,
        "keep_ego": keep_ego,
        "ic": "aeb_ego_seed" if not keep_ego else "giraffe_only",
    }


def layout_aeb_ccru(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    """Crossing / slow same-direction target (CCRs/CCRm-ish)."""
    ego, lead, meta = layout_aeb_stopped(
        carla_mod,
        client,
        world,
        keep_ego=keep_ego,
        gap_env="GF_AEB_CCRU_GAP_M",
        ego_env="GF_AEB_CCRU_EGO_MPS",
        default_gap=35.0,
        default_ego=11.0,
        layout_name="aeb_ccru",
    )
    # Slow rolling lead instead of full stop.
    lead_mps = float(os.environ.get("GF_AEB_CCRU_LEAD_MPS") or "3")
    if not keep_ego:
        try:
            lead.apply_control(carla_mod.VehicleControl(throttle=0.15, brake=0.0))
            closing_along_heading(carla_mod, lead, lead_mps)
        except Exception:  # noqa: BLE001
            pass
        meta["lead_ic"] = "closing_along_heading"
    meta["lead_mps"] = lead_mps
    return ego, lead, meta


def layout_aeb_intersection_cross(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    """Hazard placed laterally ahead — approximates crossing path."""
    del client
    gap_m = float(os.environ.get("GF_AEB_X_GAP_M") or "32")
    ego_mps = float(os.environ.get("GF_AEB_X_EGO_MPS") or "10")
    lateral_m = float(os.environ.get("GF_AEB_X_LAT_M") or "6")
    if keep_ego:
        ego, lead = spawn_ego_lead(
            world,
            lead_gap_m=gap_m,
            reset=True,
            require_straight=True,
            keep_ego=True,
        )
        release_ego(carla_mod, ego)
        print("[layout] INTERSECTION_CROSS keep_ego: no lateral pop", flush=True)
        return ego, lead, {
            "layout": "aeb_intersection_cross",
            "gap_m": gap_m,
            "ego_mps": ego_mps,
            "keep_ego": True,
            "const_vel": False,
            "ic": "giraffe_only",
        }
    ego, _lead = spawn_ego_lead(
        world,
        lead_gap_m=gap_m,
        reset=True,
        require_straight=True,
        keep_ego=keep_ego,
    )
    release_ego(carla_mod, ego)
    # Replace lead with lateral offset actor (ambient TM may occupy the cell).
    safe_destroy(_lead)
    try:
        world.tick()
    except Exception:  # noqa: BLE001
        pass
    import math

    ego_tf = ego.get_transform()
    right = ego_tf.get_right_vector()
    into_x, into_y = -float(right.x), -float(right.y)
    yaw_into = math.degrees(math.atan2(into_y, into_x))

    # Try several corridor poses: TM / curb often blocks the first guess.
    lat_candidates = [lateral_m, -lateral_m, lateral_m + 2.0, -(lateral_m + 2.0),
                      lateral_m + 4.0, -(lateral_m + 4.0), 8.0, -8.0]
    fwd_candidates = [gap_m * 0.85, gap_m * 0.7, gap_m * 1.0, gap_m * 0.55]
    lead = None
    last_err: Optional[BaseException] = None
    used_lat = lateral_m
    used_fwd = gap_m * 0.85
    for lat in lat_candidates:
        for fwd in fwd_candidates:
            cross_tf = offset_transform(ego_tf, forward_m=fwd, right_m=lat)
            cross_tf.rotation.yaw = yaw_into
            try:
                lead = spawn_named(
                    world,
                    role=ROLE_LEAD,
                    transform=cross_tf,
                    bp_filter="vehicle.audi.a2",
                    clear_radius_m=18.0,
                    keep_yaw=True,
                )
                used_lat = lat
                used_fwd = fwd
                break
            except RuntimeError as exc:
                last_err = exc
                continue
        if lead is not None:
            break
    if lead is None:
        raise RuntimeError(
            f"layout_aeb_intersection_cross: could not place cross vehicle "
            f"(traffic/occupied). last={last_err}"
        )

    cross_mps = float(os.environ.get("GF_AEB_X_CROSS_MPS") or "6")
    # Ego: AEB-only seed. Cross: scenario IC.
    aeb_ego_seed(True)
    try:
        const_on = closing_along_heading(carla_mod, ego, ego_mps)
    finally:
        aeb_ego_seed(False)
    closing_along_pose(carla_mod, lead, cross_mps)
    print(
        f"[layout] INTERSECTION_CROSS gap≈{gap_m} lat≈{used_lat:.1f} fwd≈{used_fwd:.1f} "
        f"ego={ego.id} cross={lead.id} "
        f"ic_ego=aeb_ego_seed ic_cross=closing_along_pose",
        flush=True,
    )
    return ego, lead, {
        "layout": "intersection_cross",
        "gap_m": gap_m,
        "lateral_m": used_lat,
        "ego_mps": ego_mps,
        "cross_mps": cross_mps,
        "const_vel": const_on,
        "ic": "aeb_ego_seed",
        "cross_ic": "closing_along_pose",
    }


def layout_aeb_occluded_lateral(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    """Sudden lateral object — start offset, then snap into path mid-case via tick."""
    ego, lead, meta = layout_aeb_intersection_cross(
        carla_mod, client, world, keep_ego=keep_ego
    )
    meta["layout"] = "occluded_lateral"
    meta["reveal_s"] = float(os.environ.get("GF_AEB_OCC_REVEAL_S") or "2.0")
    meta["keep_ego"] = keep_ego
    if not keep_ego:
        try:
            lead.disable_constant_velocity()
        except Exception:  # noqa: BLE001
            pass
        _hold_brake(carla_mod, lead)
    return ego, lead, meta


def tick_aeb_handoff(
    elapsed: float,
    ego: Any,
    lead: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    import carla as _c  # type: ignore

    layout = str(meta.get("layout") or "")
    if lead is not None and layout in ("aeb_stopped", "fcw") and not meta.get("keep_ego"):
        try:
            lead.apply_control(
                _c.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)
            )
        except Exception:  # noqa: BLE001
            pass

    if layout == "occluded_lateral" and not meta.get("revealed"):
        reveal_s = float(meta.get("reveal_s") or 2.0)
        if meta.get("keep_ego"):
            meta["revealed"] = True
        elif elapsed >= reveal_s and lead is not None:
            meta["revealed"] = True
            try:
                from spawn.pick import offset_transform as _off
                from spawn.ic import closing_along_pose

                gap = float(meta.get("gap_m") or 25.0)
                lead.set_transform(
                    _off(ego.get_transform(), forward_m=gap * 0.55, right_m=0.0)
                )
                closing_along_pose(_c, lead, 0.1)
            except Exception:  # noqa: BLE001
                pass
            print(f"[layout] occluded reveal at t={elapsed:.2f}s", flush=True)

    if meta.get("handed_off") or not cmd.seen_control:
        return
    if not meta.get("const_vel"):
        return
    meta["handed_off"] = True
    try:
        ego.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    print(f"[layout] Giraffe cmd at t={elapsed:.2f}s → release AEB ego seed", flush=True)


def layout_fcw(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    ego, lead, meta = layout_aeb_stopped(
        carla_mod,
        client,
        world,
        keep_ego=keep_ego,
        gap_env="GF_FCW_GAP_M",
        ego_env="GF_FCW_EGO_MPS",
        default_gap=50.0,
        default_ego=10.0,
        layout_name="fcw",
    )
    return ego, lead, meta


def layout_isa_follow(
    carla_mod: Any,
    client: Any,
    world: Any,
    *,
    keep_ego: bool = False,
) -> Tuple[Any, Any, dict[str, Any]]:
    from layouts.follow_straight import layout_acc_follow

    ego, lead, base = layout_acc_follow(
        carla_mod, client, world, lead_gap_m=30.0, keep_ego=keep_ego
    )
    meta = {
        **base,
        "layout": "isa_limit_follow",
        "speed_limit_kph": float(os.environ.get("GF_ISA_LIMIT_KPH") or "50"),
    }
    return ego, lead, meta
