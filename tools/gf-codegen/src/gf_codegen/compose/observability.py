"""Resolve profile + observability allowlists for compose / CMake."""

from __future__ import annotations

from typing import Any

PROFILE_DEBUG = "vehicle-debug"
PROFILE_RELEASE = "production-release"
VALID_PROFILES = frozenset({PROFILE_DEBUG, PROFILE_RELEASE})
TAP_APP = "debug_bridge/iox_obs_tap"
INJECT_APP = "debug_bridge/iox_obs_inject"

# live_tap.mode
MODE_EXPLICIT = "explicit"  # req whitelist
MODE_WIRING_ALL = "wiring_all"  # all services appearing in wiring dataflows
VALID_LIVE_MODES = frozenset({MODE_EXPLICIT, MODE_WIRING_ALL})


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


def live_tap_mode(req: dict[str, Any]) -> str:
    """Return explicit|wiring_all (default explicit for backward compat)."""
    obs = req.get("observability") if isinstance(req.get("observability"), dict) else {}
    live = obs.get("live_tap") if isinstance(obs.get("live_tap"), dict) else {}
    mode = str(live.get("mode") or MODE_EXPLICIT).strip() or MODE_EXPLICIT
    return mode if mode in VALID_LIVE_MODES else MODE_EXPLICIT


def services_from_wiring(wiring: dict[str, Any] | None) -> list[str]:
    """Unique short service names from wiring.dataflows (order preserved)."""
    if not isinstance(wiring, dict):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for flow in wiring.get("dataflows") or []:
        if not isinstance(flow, dict):
            continue
        s = _short(str(flow.get("service") or ""))
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _dedupe(services: list[str]) -> list[str]:
    seen: set[str] = set()
    uniq: list[str] = []
    for s in services:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def live_tap_config(
    req: dict[str, Any],
    *,
    wiring: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Return (enabled_effective, short_service_names).

    mode=wiring_all → services from wiring dataflows (ceiling for GMT filter).
    mode=explicit → services from live_tap.services whitelist.
    """
    profile = normalize_profile(req)
    obs = req.get("observability") if isinstance(req.get("observability"), dict) else {}
    live = obs.get("live_tap") if isinstance(obs.get("live_tap"), dict) else {}
    mode = live_tap_mode(req)

    if mode == MODE_WIRING_ALL:
        uniq = services_from_wiring(wiring)
    else:
        uniq = _dedupe(
            [_short(x) for x in (live.get("services") or []) if str(x).strip()]
        )

    enabled = bool(live.get("enabled")) and bool(uniq) and profile == PROFILE_DEBUG
    if profile == PROFILE_RELEASE:
        enabled = False
    return enabled, uniq


def record_config(req: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (mode, short_service_names). production-release → mode off."""
    profile = normalize_profile(req)
    obs = req.get("observability") if isinstance(req.get("observability"), dict) else {}
    mode = "minimal"
    services: list[str] = []
    rec = obs.get("record")
    if isinstance(rec, dict):
        mode = str(rec.get("mode") or "minimal").strip() or "minimal"
        services = [_short(x) for x in (rec.get("services") or []) if str(x).strip()]
    elif isinstance(rec, str):
        mode = rec.strip() or "minimal"
        services = []
    if profile == PROFILE_RELEASE:
        mode = "off"
    return mode, _dedupe(services)


def effective_apps(
    req: dict[str, Any],
    *,
    wiring: dict[str, Any] | None = None,
) -> list[str]:
    """Apps list for GF_APPS: strip/add iox_obs_tap; add inject on vehicle-debug."""
    apps = [str(x).strip() for x in (req.get("apps") or []) if str(x).strip()]
    apps = [a for a in apps if a not in {TAP_APP, INJECT_APP}]
    enabled, _svcs = live_tap_config(req, wiring=wiring)
    if enabled:
        apps.append(TAP_APP)
    if normalize_profile(req) == PROFILE_DEBUG:
        apps.append(INJECT_APP)
    return apps


def validate_observability(
    req: dict[str, Any],
    *,
    wiring: dict[str, Any] | None = None,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
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
    mode = live_tap_mode(req)
    live_en, live_svcs = live_tap_config(req, wiring=wiring)
    obs = req.get("observability") if isinstance(req.get("observability"), dict) else {}
    live_raw = obs.get("live_tap") if isinstance(obs.get("live_tap"), dict) else {}
    want_live = profile == PROFILE_DEBUG and bool(live_raw.get("enabled"))

    raw_mode = str(live_raw.get("mode") or "").strip()
    if raw_mode and raw_mode not in VALID_LIVE_MODES:
        errors.append(
            f"live_tap.mode={raw_mode!r} invalid; use {MODE_EXPLICIT}|{MODE_WIRING_ALL}"
        )
        checks.append({"id": "live_tap_mode", "status": "fail", "mode": raw_mode})
    else:
        checks.append({"id": "live_tap_mode", "status": "pass", "mode": mode})

    if want_live and not live_svcs:
        if mode == MODE_WIRING_ALL:
            errors.append(
                "live_tap.mode=wiring_all but wiring.dataflows has no services"
            )
        else:
            errors.append("live_tap.enabled but services whitelist is empty")
        checks.append({"id": "live_tap_whitelist", "status": "fail", "mode": mode})
    else:
        checks.append(
            {
                "id": "live_tap_whitelist",
                "status": "pass",
                "enabled": live_en,
                "mode": mode,
                "services": live_svcs,
            }
        )

    if mode == MODE_WIRING_ALL and live_raw.get("services"):
        warnings.append(
            "live_tap.mode=wiring_all ignores live_tap.services "
            "(ceiling comes from wiring dataflows; GMT may filter further)"
        )

    rec_mode, rec_svcs = record_config(req)
    if rec_mode not in ("off", "minimal", "sampled", "full"):
        warnings.append(
            f"record.mode={rec_mode!r} unusual; expected off|minimal|sampled|full"
        )
    if rec_mode != "off" and not rec_svcs:
        errors.append(
            f"observability.record.mode={rec_mode!r} requires non-empty record.services whitelist"
        )
        checks.append({"id": "record_whitelist", "status": "fail", "mode": rec_mode})
    else:
        checks.append(
            {
                "id": "record_whitelist",
                "status": "pass",
                "mode": rec_mode,
                "services": rec_svcs,
            }
        )

    return errors, warnings, checks
