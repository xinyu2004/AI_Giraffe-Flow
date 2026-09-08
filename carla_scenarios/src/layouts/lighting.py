"""Night / HLB / glare layouts."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from spawn.ic import seed_speed
from spawn.pick import offset_transform, pick_follow_transforms
from spawn.place import spawn_ego_only, spawn_named
from spawn.roles import ROLE_LEAD
from _verdict import CmdProbe, release_ego
from layouts.follow_straight import layout_acc_follow


def _lights_on(vehicle: Any) -> None:
    try:
        import carla  # type: ignore

        vehicle.set_light_state(
            carla.VehicleLightState(
                carla.VehicleLightState.LowBeam
                | carla.VehicleLightState.HighBeam
                | carla.VehicleLightState.Position
            )
        )
    except Exception:  # noqa: BLE001
        pass


def layout_hlb_oncoming(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 10.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    ego_tf, ahead = pick_follow_transforms(world, lead_gap_m=60.0)
    oncoming_tf = offset_transform(ahead, forward_m=0.0, right_m=-3.5)
    oncoming_tf.rotation.yaw = (ego_tf.rotation.yaw + 180.0) % 360.0
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    other = spawn_named(
        world,
        role=ROLE_LEAD,
        transform=oncoming_tf,
        bp_filter="vehicle.audi.tt",
    )
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    seed_speed(carla_mod, other, mps, session=session)
    _lights_on(ego)
    _lights_on(other)
    print(f"[layout] HLB_ONCOMING ego={ego.id} other={other.id} (Giraffe drives ego)", flush=True)
    return ego, other, {
        "layout": "hlb_oncoming",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def layout_hlb_urban(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 8.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    ego, lead, _base = layout_acc_follow(
        session, lead_gap_m=28.0, keep_ego=keep_ego
    )
    _lights_on(ego)
    _lights_on(lead)
    mps = float(ego_mps)
    print(f"[layout] HLB_URBAN ego={ego.id} lead={lead.id} (Giraffe drives ego)", flush=True)
    return ego, lead, {
        "layout": "hlb_urban",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def layout_night_glare(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 10.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    ego, other, meta = layout_hlb_oncoming(
        session, keep_ego=keep_ego, ego_mps=ego_mps
    )
    meta["layout"] = "env_night_glare"
    return ego, other, meta


def layout_night_lead_hb(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 9.0,
) -> Tuple[Any, Any, dict[str, Any]]:
    ego, lead, _base = layout_acc_follow(
        session, lead_gap_m=25.0, keep_ego=keep_ego
    )
    _lights_on(ego)
    _lights_on(lead)
    mps = float(ego_mps)
    print(f"[layout] NIGHT_LEAD_HB ego={ego.id} lead={lead.id} (Giraffe drives ego)", flush=True)
    return ego, lead, {
        "layout": "env_night_lead_hb",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def tick_light_handoff(
    elapsed: float,
    ego: Any,
    _target: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    del ego
    if meta.get("handed_off") or not cmd.seen_control:
        return
    meta["handed_off"] = True
    print(f"[layout] lighting Giraffe cmd at t={elapsed:.2f}s", flush=True)
