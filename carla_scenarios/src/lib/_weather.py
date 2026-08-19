"""CARLA weather helpers (env-configurable presets for AFC cases).

Presets + overrides (process env / carla.env)::

  GF_WEATHER_PRESET     sun | rain | fog | dusk | night | clear
  GF_SUN_ALTITUDE_DEG   sun height (deg); high ≈ overhead
  GF_SUN_AZIMUTH_DEG    sun compass (deg)
  GF_SUN_BRIGHTNESS     0..1  (maps mainly to cloudiness; 1=harsh sun)
  GF_RAIN_AMOUNT        0..100 precipitation
  GF_RAIN_WETNESS       0..100 road/lens wetness deposits
  GF_FOG_DENSITY        0..100
  GF_WIND               0..100
  GF_WIPER_SPEED        0=off 1=slow 2=fast (best-effort; see apply_wiper)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class WeatherConfig:
    preset: str
    cloudiness: float
    precipitation: float
    precipitation_deposits: float
    wetness: float
    wind_intensity: float
    sun_azimuth_angle: float
    sun_altitude_angle: float
    fog_density: float
    fog_distance: float
    wiper_speed: int  # 0..2

    def describe(self) -> str:
        return (
            f"preset={self.preset} sun_alt={self.sun_altitude_angle:.0f} "
            f"sun_az={self.sun_azimuth_angle:.0f} cloud={self.cloudiness:.0f} "
            f"rain={self.precipitation:.0f} wet={self.wetness:.0f} "
            f"fog={self.fog_density:.0f} wiper={self.wiper_speed}"
        )


_PRESETS: dict[str, dict[str, float]] = {
    # Harsh sun / glare — low cloud, high altitude (override azimuth for backlight).
    "sun": {
        "cloudiness": 5.0,
        "precipitation": 0.0,
        "precipitation_deposits": 0.0,
        "wetness": 0.0,
        "wind_intensity": 10.0,
        "sun_azimuth_angle": 45.0,
        "sun_altitude_angle": 70.0,
        "fog_density": 0.0,
        "fog_distance": 0.0,
        "wiper_speed": 0.0,
    },
    "rain": {
        "cloudiness": 90.0,
        "precipitation": 80.0,
        "precipitation_deposits": 60.0,
        "wetness": 90.0,
        "wind_intensity": 40.0,
        "sun_azimuth_angle": 180.0,
        "sun_altitude_angle": 25.0,
        "fog_density": 5.0,
        "fog_distance": 40.0,
        "wiper_speed": 2.0,
    },
    "fog": {
        "cloudiness": 70.0,
        "precipitation": 5.0,
        "precipitation_deposits": 10.0,
        "wetness": 20.0,
        "wind_intensity": 5.0,
        "sun_azimuth_angle": 90.0,
        "sun_altitude_angle": 35.0,
        "fog_density": 60.0,
        "fog_distance": 15.0,
        "wiper_speed": 0.0,
    },
    # Low sun in front of ego → backlight / bloom stress.
    "dusk": {
        "cloudiness": 15.0,
        "precipitation": 0.0,
        "precipitation_deposits": 0.0,
        "wetness": 0.0,
        "wind_intensity": 5.0,
        "sun_azimuth_angle": 0.0,
        "sun_altitude_angle": 8.0,
        "fog_density": 2.0,
        "fog_distance": 80.0,
        "wiper_speed": 0.0,
    },
    "night": {
        "cloudiness": 40.0,
        "precipitation": 0.0,
        "precipitation_deposits": 0.0,
        "wetness": 0.0,
        "wind_intensity": 5.0,
        "sun_azimuth_angle": 0.0,
        "sun_altitude_angle": -30.0,
        "fog_density": 0.0,
        "fog_distance": 0.0,
        "wiper_speed": 0.0,
    },
    "clear": {
        "cloudiness": 10.0,
        "precipitation": 0.0,
        "precipitation_deposits": 0.0,
        "wetness": 0.0,
        "wind_intensity": 5.0,
        "sun_azimuth_angle": 120.0,
        "sun_altitude_angle": 55.0,
        "fog_density": 0.0,
        "fog_distance": 0.0,
        "wiper_speed": 0.0,
    },
    # Wet road after rain (little precip) — specular / ISP stress.
    "wet": {
        "cloudiness": 55.0,
        "precipitation": 5.0,
        "precipitation_deposits": 70.0,
        "wetness": 85.0,
        "wind_intensity": 15.0,
        "sun_azimuth_angle": 100.0,
        "sun_altitude_angle": 30.0,
        "fog_density": 8.0,
        "fog_distance": 50.0,
        "wiper_speed": 1.0,
    },
    # Snow / low-mu approximation (CARLA precipitation_deposits + fog).
    "snow": {
        "cloudiness": 95.0,
        "precipitation": 40.0,
        "precipitation_deposits": 80.0,
        "wetness": 60.0,
        "wind_intensity": 35.0,
        "sun_azimuth_angle": 160.0,
        "sun_altitude_angle": 15.0,
        "fog_density": 25.0,
        "fog_distance": 30.0,
        "wiper_speed": 2.0,
    },
}


def _f(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return float(default)
    return float(raw)


def _i(key: str, default: int) -> int:
    return int(round(_f(key, float(default))))


def load_weather(preset: Optional[str] = None) -> WeatherConfig:
    try:
        from _carla_env import load_local_env

        load_local_env()
    except Exception:  # noqa: BLE001
        pass

    name = (preset or os.environ.get("GF_WEATHER_PRESET") or "clear").strip().lower()
    base = dict(_PRESETS.get(name) or _PRESETS["clear"])
    if name not in _PRESETS:
        name = name or "custom"

    # Brightness 1 → fewer clouds; 0 → heavy overcast (sun presets).
    if os.environ.get("GF_SUN_BRIGHTNESS") not in (None, ""):
        b = max(0.0, min(1.0, _f("GF_SUN_BRIGHTNESS", 1.0)))
        base["cloudiness"] = (1.0 - b) * 85.0

    return WeatherConfig(
        preset=name,
        cloudiness=_f("GF_CLOUDINESS", base["cloudiness"]),
        precipitation=_f("GF_RAIN_AMOUNT", base["precipitation"]),
        precipitation_deposits=_f(
            "GF_RAIN_DEPOSITS", base["precipitation_deposits"]
        ),
        wetness=_f("GF_RAIN_WETNESS", base["wetness"]),
        wind_intensity=_f("GF_WIND", base["wind_intensity"]),
        sun_azimuth_angle=_f("GF_SUN_AZIMUTH_DEG", base["sun_azimuth_angle"]),
        sun_altitude_angle=_f("GF_SUN_ALTITUDE_DEG", base["sun_altitude_angle"]),
        fog_density=_f("GF_FOG_DENSITY", base["fog_density"]),
        fog_distance=_f("GF_FOG_DISTANCE", base["fog_distance"]),
        wiper_speed=max(0, min(2, _i("GF_WIPER_SPEED", int(base["wiper_speed"])))),
    )


def apply_weather(world: Any, carla_mod: Any, cfg: WeatherConfig) -> None:
    params = carla_mod.WeatherParameters(
        cloudiness=cfg.cloudiness,
        precipitation=cfg.precipitation,
        precipitation_deposits=cfg.precipitation_deposits,
        wind_intensity=cfg.wind_intensity,
        sun_azimuth_angle=cfg.sun_azimuth_angle,
        sun_altitude_angle=cfg.sun_altitude_angle,
        fog_density=cfg.fog_density,
        fog_distance=cfg.fog_distance,
        wetness=cfg.wetness,
    )
    world.set_weather(params)
    print(f"[weather] applied {cfg.describe()}", flush=True)


def apply_wiper(vehicle: Any, speed: int) -> bool:
    """Best-effort wiper. CARLA versions differ; returns True if a hook worked."""
    speed = max(0, min(2, int(speed)))
    # Newer builds occasionally expose helpers; keep silent fallback.
    for attr in ("set_wiper_speed", "enable_wipers"):
        fn = getattr(vehicle, attr, None)
        if callable(fn):
            try:
                if attr == "enable_wipers":
                    fn(speed > 0)
                else:
                    fn(speed)
                print(f"[weather] wiper via {attr}={speed}", flush=True)
                return True
            except Exception:  # noqa: BLE001
                pass
    # Record intent for labs / future bridge camera; precipitation still hits glass.
    print(
        f"[weather] wiper_speed={speed} (no vehicle API; rain still on windshield)",
        flush=True,
    )
    return False
