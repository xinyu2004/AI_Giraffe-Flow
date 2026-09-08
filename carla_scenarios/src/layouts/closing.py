"""Closing / AEB-family layouts (stopped or slow hazard ahead)."""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

from spawn.ic import (
    aeb_ego_seed,
    closing_along_heading,
    closing_along_pose,
    closing_toward_lead,
)
from spawn.pick import offset_transform
from spawn.place import (
    _set_transform_at_rest,
    reseat_lead_relative,
    spawn_ego_lead,
    spawn_ego_only,
    spawn_named,
)
from spawn.roles import ROLE_LEAD, find_by_role, safe_destroy, tick_world
from _verdict import CmdProbe, release_ego


def _pair_gap_speed(ego: Any, lead: Any) -> tuple[float, float]:
    try:
        ev = ego.get_velocity()
        ego_mps = math.hypot(float(ev.x), float(ev.y))
        el, ll = ego.get_location(), lead.get_location()
        gap_m = math.hypot(float(ll.x) - float(el.x), float(ll.y) - float(el.y))
        return gap_m, ego_mps
    except Exception:  # noqa: BLE001
        return 0.0, 0.0


def _hold_brake(carla_mod: Any, vehicle: Any) -> None:
    """Park brake only — caller already ap_off'd if needed."""
    try:
        vehicle.apply_control(
            carla_mod.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)
        )
    except Exception:  # noqa: BLE001
        pass


def _place_cross_lead(
    session: Any,
    ego: Any,
    *,
    gap_m: float,
    lateral_m: float,
) -> tuple[Any, float, float]:
    world = session.world
    ego_tf = ego.get_transform()
    right = ego_tf.get_right_vector()
    into_x, into_y = -float(right.x), -float(right.y)
    yaw_into = math.degrees(math.atan2(into_y, into_x))

    lat_candidates = [
        lateral_m,
        -lateral_m,
        lateral_m + 2.0,
        -(lateral_m + 2.0),
        8.0,
        -8.0,
    ]
    fwd_candidates = [gap_m * 0.85, gap_m * 0.7, gap_m]
    poses: list[tuple[Any, float, float]] = []
    for lat in lat_candidates:
        for fwd in fwd_candidates:
            cross_tf = offset_transform(ego_tf, forward_m=fwd, right_m=lat)
            cross_tf.rotation.yaw = yaw_into
            poses.append((cross_tf, lat, fwd))

    lead = find_by_role(world, ROLE_LEAD)
    if lead is not None:
        session.ap_off(lead)
        for cross_tf, lat, fwd in poses[:4]:
            _set_transform_at_rest(lead, cross_tf, park=False)
            return lead, lat, fwd

    last_err: Optional[BaseException] = None
    for cross_tf, lat, fwd in poses:
        try:
            lead = spawn_named(
                world,
                role=ROLE_LEAD,
                transform=cross_tf,
                bp_filter="vehicle.audi.a2",
                clear_radius_m=4.0,
                keep_yaw=True,
            )
            return lead, lat, fwd
        except RuntimeError as exc:
            last_err = exc
            continue
    raise RuntimeError(
        f"layout_aeb_intersection_cross: could not place cross vehicle "
        f"(traffic/occupied). last={last_err}"
    )


def layout_aeb_stopped(
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 40.0,
    ego_mps: float = 12.0,
    layout_name: str = "aeb_stopped",
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    gap_m = float(gap_m)
    ego_mps = float(ego_mps)
    design_gap = gap_m
    const_on = False

    if keep_ego:
        ego = spawn_ego_only(world, keep_ego=True, reset_others=False)
        release_ego(carla_mod, ego, session=session)
        lead = reseat_lead_relative(
            world,
            ego,
            session=session,
            forward_m=gap_m,
            park=True,
            lead_filter="vehicle.audi.tt",
        )
        _hold_brake(carla_mod, lead)
        gap_m, ego_mps = _pair_gap_speed(ego, lead)
        if gap_m < 1.0:
            gap_m = design_gap
        ic_s = "giraffe_only+reseat_lead"
        print(
            f"[layout] {layout_name} keep_ego: reseat parked lead gap≈{gap_m:.0f}m "
            f"(ego kept)",
            flush=True,
        )
    else:
        ego, lead = spawn_ego_lead(
            world,
            lead_gap_m=gap_m,
            reset=True,
            require_straight=True,
            keep_ego=False,
        )
        release_ego(carla_mod, ego, session=session)
        session.ap_off(lead)
        _hold_brake(carla_mod, lead)
        aeb_ego_seed(True)
        try:
            const_on = closing_toward_lead(
                carla_mod, ego, ego_mps, lead, session=session
            )
        finally:
            aeb_ego_seed(False)
        ic_s = "aeb_ego_seed+closing_toward_lead"

    ttc = gap_m / max(ego_mps, 0.1)
    print(
        f"[layout] {layout_name} gap≈{gap_m:.0f}m ego_v≈{ego_mps:.1f} "
        f"TTC≈{ttc:.1f}s const={int(const_on)} ic={ic_s}",
        flush=True,
    )
    return ego, lead, {
        "layout": layout_name,
        "gap_m": gap_m,
        "ego_mps": ego_mps,
        "ttc0": round(ttc, 2),
        "const_vel": const_on,
        "keep_ego": keep_ego,
        "ic": ic_s,
    }


def layout_aeb_ccru(
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 35.0,
    ego_mps: float = 11.0,
    lead_mps: float = 3.0,
    layout_name: str = "aeb_ccru",
) -> Tuple[Any, Any, dict[str, Any]]:
    carla_mod = session.carla
    ego, lead, meta = layout_aeb_stopped(
        session,
        keep_ego=keep_ego,
        gap_m=gap_m,
        ego_mps=ego_mps,
        layout_name=layout_name,
    )
    try:
        lead.apply_control(carla_mod.VehicleControl(throttle=0.15, brake=0.0))
        closing_along_heading(carla_mod, lead, float(lead_mps), session=session)
    except Exception:  # noqa: BLE001
        pass
    meta["lead_ic"] = "closing_along_heading"
    meta["lead_mps"] = float(lead_mps)
    return ego, lead, meta


def layout_aeb_intersection_cross(
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 32.0,
    ego_mps: float = 10.0,
    lateral_m: float = 6.0,
    cross_mps: float = 6.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    gap_m = float(gap_m)
    ego_mps = float(ego_mps)
    lateral_m = float(lateral_m)
    cross_mps = float(cross_mps)

    if keep_ego:
        ego = spawn_ego_only(world, keep_ego=True, reset_others=False)
        release_ego(carla_mod, ego, session=session)
        lead, used_lat, used_fwd = _place_cross_lead(
            session, ego, gap_m=gap_m, lateral_m=lateral_m
        )
        closing_along_pose(carla_mod, lead, cross_mps, session=session)
        print(
            f"[layout] INTERSECTION_CROSS keep_ego: reseat cross "
            f"lat≈{used_lat:.1f} fwd≈{used_fwd:.1f} ego={ego.id} cross={lead.id}",
            flush=True,
        )
        return ego, lead, {
            "layout": "aeb_intersection_cross",
            "gap_m": gap_m,
            "lateral_m": used_lat,
            "ego_mps": ego_mps,
            "cross_mps": cross_mps,
            "keep_ego": True,
            "const_vel": False,
            "ic": "giraffe_only",
            "cross_ic": "closing_along_pose",
        }

    ego, _lead = spawn_ego_lead(
        world,
        lead_gap_m=gap_m,
        reset=True,
        require_straight=True,
        keep_ego=False,
    )
    release_ego(carla_mod, ego, session=session)
    safe_destroy(_lead)
    tick_world(world)

    lead, used_lat, used_fwd = _place_cross_lead(
        session, ego, gap_m=gap_m, lateral_m=lateral_m
    )

    aeb_ego_seed(True)
    try:
        const_on = closing_along_heading(
            carla_mod, ego, ego_mps, session=session
        )
    finally:
        aeb_ego_seed(False)
    closing_along_pose(carla_mod, lead, cross_mps, session=session)
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
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 32.0,
    ego_mps: float = 10.0,
    lateral_m: float = 6.0,
    cross_mps: float = 6.0,
    reveal_s: float = 2.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    ego, lead, meta = layout_aeb_intersection_cross(
        session,
        keep_ego=keep_ego,
        gap_m=gap_m,
        ego_mps=ego_mps,
        lateral_m=lateral_m,
        cross_mps=cross_mps,
    )
    meta["layout"] = "occluded_lateral"
    meta["reveal_s"] = float(reveal_s)
    meta["keep_ego"] = keep_ego
    meta["revealed"] = False
    try:
        lead.disable_constant_velocity()
    except Exception:  # noqa: BLE001
        pass
    _hold_brake(session.carla, lead)
    if keep_ego:
        print(
            "[layout] occluded_lateral keep_ego: cross parked off-path; "
            "reveal on tick",
            flush=True,
        )
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
    if lead is not None and layout in ("aeb_stopped", "fcw"):
        try:
            lead.apply_control(
                _c.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)
            )
        except Exception:  # noqa: BLE001
            pass

    if layout == "occluded_lateral" and not meta.get("revealed"):
        reveal_s = float(meta.get("reveal_s") or 2.0)
        if elapsed >= reveal_s and lead is not None:
            meta["revealed"] = True
            try:
                from spawn.pick import offset_transform as _off

                gap = float(meta.get("gap_m") or 25.0)
                lead.set_transform(
                    _off(ego.get_transform(), forward_m=gap * 0.55, right_m=0.0)
                )
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
    session: Any,
    *,
    keep_ego: bool = False,
    gap_m: float = 50.0,
    ego_mps: float = 10.0,
    layout_name: str = "fcw",
) -> Tuple[Any, Any, dict[str, Any]]:
    return layout_aeb_stopped(
        session,
        keep_ego=keep_ego,
        gap_m=gap_m,
        ego_mps=ego_mps,
        layout_name=layout_name,
    )


def layout_isa_follow(
    session: Any,
    *,
    keep_ego: bool = False,
    lead_gap_m: float = 30.0,
    lead_speed_diff_pct: float = 15.0,
    speed_limit_kph: float = 50.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    from layouts.follow_straight import layout_acc_follow

    ego, lead, base = layout_acc_follow(
        session,
        lead_gap_m=float(lead_gap_m),
        lead_speed_diff_pct=float(lead_speed_diff_pct),
        keep_ego=keep_ego,
    )
    return ego, lead, {
        **base,
        "layout": "isa_limit_follow",
        "speed_limit_kph": float(speed_limit_kph),
    }
