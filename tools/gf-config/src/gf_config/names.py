"""Service / GfChannel naming helpers (pure; no session I/O)."""

from __future__ import annotations

from typing import Any

# Flat publish_policy keys that are channels (not SOA services) in legacy docs.
LEGACY_FLAT_CHANNEL_KEYS: frozenset[str] = frozenset(
    {"vehicle_cmd", "vehicle_state", "fake_perc", "surround_world"}
)

# Default channel publish policies (frame_ingest dialog + seeds).
CHANNEL_POLICY_DEFAULTS: dict[str, dict[str, Any]] = {
    "vehicle_cmd": {"trigger": "period", "period_ms": 10},
    "vehicle_state": {"trigger": "on_change"},
    "fake_perc": {"trigger": "on_change"},
    "surround_world": {"trigger": "on_change"},
}

DEFAULT_CHANNEL_NAMES: tuple[str, ...] = (
    "vehicle_cmd",
    "vehicle_state",
    "fake_perc",
)


def normalize_channel_slot(s: str) -> str | None:
    """Return canonical gf.channel.* or None if not a GfChannel slot name."""
    raw = (s or "").strip()
    if not raw:
        return None
    if raw.startswith("gf.channel."):
        return raw
    # Polluted SOA form: services.semantic.gf.channel.front
    marker = "gf.channel."
    idx = raw.find(marker)
    if idx >= 0:
        return raw[idx:]
    return None


def is_channel_svc(s: str) -> bool:
    return normalize_channel_slot(s) is not None


def canon_service(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    ch = normalize_channel_slot(s)
    if ch:
        return ch
    if s.startswith("services."):
        return s
    if s.startswith("semantic."):
        return f"services.{s}"
    return f"services.semantic.{s}"


def short_service(svc: str) -> str:
    ch = normalize_channel_slot(svc or "")
    if ch:
        return ch
    return (svc or "").split(".")[-1] if svc else ""


def default_publish_spec(*, trigger: str = "on_change") -> dict[str, Any]:
    if trigger == "period":
        return {"trigger": "period", "period_ms": 10}
    return {"trigger": "on_change"}
