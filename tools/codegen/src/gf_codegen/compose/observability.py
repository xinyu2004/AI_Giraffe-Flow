"""Resolve profile + observability allowlists for compose / CMake."""

from __future__ import annotations

from typing import Any

PROFILE_DEBUG = "vehicle-debug"
PROFILE_RELEASE = "production-release"
VALID_PROFILES = frozenset({PROFILE_DEBUG, PROFILE_RELEASE})
TAP_APP = "tools/iox_obs_tap"


def _short(svc: str) -> str:
    s = str(svc).strip()
    if s.startswith("services.semantic."):
        return s[len("services.semantic.") :]
    if s.startswith("services."):
        return s.split(".")[-1]
    return s


def normalize_profile(req: dict[str, Any]) -> str:
    p = str(req.get("profile") or PROFILE_DEBUG).strip()
    return p if p in VALID_PROFILES else PROFILE_DEBUG


def live_tap_config(req: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (enabled_effective, short_service_names)."""
    profile = normalize_profile(req)
    obs = req.get("observability") if isinstance(req.get("observability"), dict) else {}
    live = obs.get("live_tap") if isinstance(obs.get("live_tap"), dict) else {}
    services = [_short(x) for x in (live.get("services") or []) if str(x).strip()]
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in services:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    enabled = bool(live.get("enabled")) and bool(uniq) and profile == PROFILE_DEBUG
    if profile == PROFILE_RELEASE:
        enabled = False
    return enabled, uniq


def record_config(req: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (mode, short_service_names). production-release → mode off."""
    profile = normalize_profile(req)
    obs = req.get("observability") if isinstance(req.get("observability"), dict) else {}
    # legacy: observability.record was a string mode
    mode = "minimal"
    services: list[str] = []
    rec = obs.get("record")
    if isinstance(rec, dict):
        mode = str(rec.get("mode") or "minimal").strip() or "minimal"
        services = [_short(x) for x in (rec.get("services") or []) if str(x).strip()]
    elif isinstance(rec, str):
        mode = rec.strip() or "minimal"
        # legacy string record without whitelist → treat as needing migrate
        services = []
    if profile == PROFILE_RELEASE:
        mode = "off"
    seen: set[str] = set()
    uniq: list[str] = []
    for s in services:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return mode, uniq


def effective_apps(req: dict[str, Any]) -> list[str]:
    """Apps list for GF_APPS: strip/add iox_obs_tap by live_tap + profile."""
    apps = [str(x).strip() for x in (req.get("apps") or []) if str(x).strip()]
    apps = [a for a in apps if a != TAP_APP]
    enabled, _svcs = live_tap_config(req)
    if enabled:
        apps.append(TAP_APP)
    return apps


def validate_observability(req: dict[str, Any]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Return (errors, warnings, checks) for lineage."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    raw_profile = str(req.get("profile") or PROFILE_DEBUG).strip()
    if raw_profile and raw_profile not in VALID_PROFILES:
        errors.append(f"unknown profile={raw_profile!r}; use {PROFILE_DEBUG}|{PROFILE_RELEASE}")
        checks.append({"id": "profile_valid", "status": "fail", "profile": raw_profile})
    else:
        checks.append({"id": "profile_valid", "status": "pass", "profile": normalize_profile(req)})

    profile = normalize_profile(req)
    live_en, live_svcs = live_tap_config(req)
    obs = req.get("observability") if isinstance(req.get("observability"), dict) else {}
    live_raw = obs.get("live_tap") if isinstance(obs.get("live_tap"), dict) else {}
    if profile == PROFILE_DEBUG and bool(live_raw.get("enabled")) and not live_svcs:
        errors.append("live_tap.enabled but services whitelist is empty")
        checks.append({"id": "live_tap_whitelist", "status": "fail"})
    else:
        checks.append(
            {
                "id": "live_tap_whitelist",
                "status": "pass",
                "enabled": live_en,
                "services": live_svcs,
            }
        )

    mode, rec_svcs = record_config(req)
    if mode not in ("off", "minimal", "sampled", "full"):
        warnings.append(f"record.mode={mode!r} unusual; expected off|minimal|sampled|full")
    if mode != "off" and not rec_svcs:
        errors.append(
            f"observability.record.mode={mode!r} requires non-empty record.services whitelist"
        )
        checks.append({"id": "record_whitelist", "status": "fail", "mode": mode})
    else:
        checks.append(
            {"id": "record_whitelist", "status": "pass", "mode": mode, "services": rec_svcs}
        )

    return errors, warnings, checks
