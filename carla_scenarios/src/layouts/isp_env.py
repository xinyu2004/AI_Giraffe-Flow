"""Tunnel entry/exit — approximate ISP exposure transitions via weather."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from spawn.pick import pick_follow_transforms
from spawn.place import spawn_ego_only
from _verdict import CmdProbe, release_ego
from _weather import WeatherConfig, apply_weather


def _cfg_bright() -> WeatherConfig:
    return WeatherConfig(
        preset="tunnel_bright",
        cloudiness=5.0,
        precipitation=0.0,
        precipitation_deposits=0.0,
        wetness=0.0,
        wind_intensity=5.0,
        sun_azimuth_angle=90.0,
        sun_altitude_angle=70.0,
        fog_density=0.0,
        fog_distance=0.0,
        wiper_speed=0,
    )


def _cfg_dark() -> WeatherConfig:
    return WeatherConfig(
        preset="tunnel_dark",
        cloudiness=90.0,
        precipitation=0.0,
        precipitation_deposits=0.0,
        wetness=0.0,
        wind_intensity=5.0,
        sun_azimuth_angle=0.0,
        sun_altitude_angle=-40.0,
        fog_density=30.0,
        fog_distance=20.0,
        wiper_speed=0,
    )


def layout_tunnel_entry(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 10.0,
    switch_s: float = 3.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    apply_weather(world, carla_mod, _cfg_bright())
    ego_tf, _ = pick_follow_transforms(world, lead_gap_m=25.0)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    print(
        f"[layout] TUNNEL_ENTRY ego={ego.id} switch_s={switch_s} (Giraffe drives)",
        flush=True,
    )
    return ego, None, {
        "layout": "env_tunnel_entry",
        "ego_mps": float(ego_mps),
        "const_vel": False,
        "ic": "giraffe_only",
        "switch_s": float(switch_s),
        "to_dark": True,
    }


def layout_tunnel_exit(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 10.0,
    switch_s: float = 3.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    apply_weather(world, carla_mod, _cfg_dark())
    ego_tf, _ = pick_follow_transforms(world, lead_gap_m=25.0)
    ego = spawn_ego_only(world, ego_tf=ego_tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    print(
        f"[layout] TUNNEL_EXIT ego={ego.id} switch_s={switch_s} (Giraffe drives)",
        flush=True,
    )
    return ego, None, {
        "layout": "env_tunnel_exit",
        "ego_mps": float(ego_mps),
        "const_vel": False,
        "ic": "giraffe_only",
        "switch_s": float(switch_s),
        "to_dark": False,
    }


def tick_tunnel(
    elapsed: float,
    ego: Any,
    _t: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    import carla as _c  # type: ignore

    if not meta.get("switched") and elapsed >= float(meta.get("switch_s") or 3.0):
        meta["switched"] = True
        cfg = _cfg_dark() if meta.get("to_dark") else _cfg_bright()
        try:
            apply_weather(ego.get_world(), _c, cfg)
        except Exception:  # noqa: BLE001
            pass
        print(f"[layout] tunnel weather switch t={elapsed:.2f}s → {cfg.preset}", flush=True)

    if meta.get("handed_off") or not cmd.seen_control:
        return
    meta["handed_off"] = True
    print(f"[layout] tunnel Giraffe cmd at t={elapsed:.2f}s", flush=True)
