"""SKU publish_policy: per-topic trigger from req.yaml → SOR + generated hpp.

period → period_ms (timer / hold-last).
on_change → expect_fps (budget / warn band; not a send clock; no freeze).
Unknown trigger (including retired on_camera) → unspecified + warning. No migrate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

KNOWN_TRIGGERS = ("period", "on_change")

# Short name → full service id
_SERVICE_ALIASES = {
    "EgoMotion": "services.semantic.EgoMotion",
    "Perception_In_St": "services.semantic.Perception_In_St",
    "Perception_MESSAGE_Out_St": "services.semantic.Perception_MESSAGE_Out_St",
    "Trajectory": "services.semantic.Trajectory",
    "VehicleBus": "services.semantic.VehicleBus",
}

_OUT_SHORT = "Perception_MESSAGE_Out_St"


def _canon_service_id(key: str) -> str:
    k = str(key).strip()
    if k in _SERVICE_ALIASES:
        return _SERVICE_ALIASES[k]
    if k.startswith("services."):
        return k
    if k.startswith("semantic."):
        return f"services.{k}"
    return f"services.semantic.{k}"


def _short_id(service_id: str) -> str:
    return str(service_id).rsplit(".", 1)[-1]


def _as_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    try:
        n = int(str(v), 0)
    except (TypeError, ValueError):
        return default
    return n if n >= 0 else default


def camera_fps_ceiling(req: dict[str, Any] | None) -> int:
    """Min authored camera_slots[].fps (>0). 0 = unspecified."""
    fi = (req or {}).get("frame_ingest") if isinstance(req, dict) else None
    if not isinstance(fi, dict):
        return 0
    vals: list[int] = []
    top = _as_int(fi.get("fps"), 0)
    if top > 0:
        vals.append(top)
    slots = fi.get("camera_slots") or fi.get("channel_slots")
    if isinstance(slots, list):
        for s in slots:
            if isinstance(s, dict):
                n = _as_int(s.get("fps"), 0)
                if n > 0:
                    vals.append(n)
    return min(vals) if vals else 0


def normalize_policy(req: dict[str, Any] | None) -> dict[str, Any]:
    """Return {services: {short: spec}, channels: {name: spec}}."""
    raw = (req or {}).get("publish_policy")
    services: dict[str, dict[str, Any]] = {}
    channels: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return {"services": services, "channels": channels}
    nested_s = raw.get("services")
    nested_c = raw.get("channels")
    if isinstance(nested_s, dict) or isinstance(nested_c, dict):
        if isinstance(nested_s, dict):
            for k, v in nested_s.items():
                if isinstance(v, dict):
                    services[_short_id(_canon_service_id(str(k)))] = dict(v)
        if isinstance(nested_c, dict):
            for k, v in nested_c.items():
                if isinstance(v, dict):
                    channels[str(k).strip()] = dict(v)
        return {"services": services, "channels": channels}
    for k, v in raw.items():
        if k in ("services", "channels") or not isinstance(v, dict):
            continue
        ks = str(k).strip()
        if ks in _SERVICE_ALIASES or ks.startswith("services.") or ks.startswith("semantic."):
            services[_short_id(_canon_service_id(ks))] = dict(v)
        else:
            channels[ks] = dict(v)
    return {"services": services, "channels": channels}


def _expect_fps_of(spec: dict[str, Any]) -> int:
    fps = _as_int(spec.get("expect_fps"), 0)
    if fps > 0:
        return fps
    return _as_int(spec.get("expect_hz"), 0)


def apply_publish_policy(sor: dict[str, Any], req: dict[str, Any] | None) -> list[str]:
    """Stamp trigger/period_ms/expect_fps onto sor['services']. Drop invented period_ms=50."""
    warnings: list[str] = []
    policy = normalize_policy(req if isinstance(req, dict) else {})
    svc_map = policy["services"]
    for svc in sor.get("services") or []:
        if not isinstance(svc, dict):
            continue
        sid = str(svc.get("id") or "")
        short = _short_id(sid)
        spec = svc_map.get(short)
        svc.pop("period_ms", None)
        svc.pop("expect_hz", None)
        svc.pop("expect_fps", None)
        if not spec:
            svc["trigger"] = "unspecified"
            continue
        trigger = str(spec.get("trigger") or "").strip() or "unspecified"
        if trigger not in KNOWN_TRIGGERS:
            warnings.append(f"publish_policy: {short} unknown trigger={trigger!r}")
            trigger = "unspecified"
        svc["trigger"] = trigger
        if trigger == "period":
            period = _as_int(spec.get("period_ms"), 0)
            if period <= 0:
                warnings.append(f"publish_policy: {short} period trigger missing period_ms")
            else:
                svc["period_ms"] = period
        elif trigger == "on_change":
            fps = _expect_fps_of(spec)
            if fps > 0:
                svc["expect_fps"] = fps
                spec["expect_fps"] = fps
                spec.pop("expect_hz", None)
            elif short == _OUT_SHORT:
                warnings.append(
                    f"publish_policy: {short} on_change missing expect_fps "
                    "(budget / warn band, not a send clock)"
                )
    cam = camera_fps_ceiling(req if isinstance(req, dict) else {})
    for short, spec in svc_map.items():
        if not isinstance(spec, dict):
            continue
        if str(spec.get("trigger") or "") != "on_change":
            continue
        fps = _expect_fps_of(spec)
        if fps <= 0:
            continue
        if cam <= 0:
            warnings.append(
                f"publish_policy: {short} expect_fps={fps} but camera fps unspecified "
                "(set frame_ingest.camera_slots[].fps)"
            )
        elif fps > cam:
            warnings.append(
                f"publish_policy: {short} expect_fps={fps} > camera fps={cam} (must be ≤ camera)"
            )
    sor["publish_policy"] = {
        "services": svc_map,
        "channels": policy["channels"],
    }
    return warnings


def _c_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def emit_publish_policy_hpp(req: dict[str, Any] | None, out_path: Path) -> None:
    policy = normalize_policy(req if isinstance(req, dict) else {})
    lines = [
        "// Generated by gf_codegen.compose — do not edit by hand",
        "// Authoring: req.yaml publish_policy (gf-config tab 1). Not PHM alive_period.",
        "// period_ms = timer; expect_fps = on_change budget/warn band (not a send clock).",
        "#pragma once",
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "#include <cstring>",
        "",
        "namespace gf_gen::publish_policy {",
        "",
        "struct TopicPolicy {",
        "  const char* id;",
        "  const char* trigger;  // period | on_change | unspecified",
        "  std::uint32_t period_ms;   // 0 if not period",
        "  std::uint32_t expect_fps;  // 0 if unset; on_change budget / warn band",
        "};",
        "",
        "inline constexpr TopicPolicy kServices[] = {",
    ]
    for short, spec in sorted(policy["services"].items()):
        trigger = str(spec.get("trigger") or "unspecified")
        if trigger not in KNOWN_TRIGGERS:
            trigger = "unspecified"
        period = _as_int(spec.get("period_ms"), 0) if trigger == "period" else 0
        fps = _expect_fps_of(spec) if trigger == "on_change" else 0
        lines.append(
            f"    {{{_c_str(short)}, {_c_str(trigger)}, {period}u, {fps}u}},"
        )
    if not policy["services"]:
        lines.append("    {\"\", \"unspecified\", 0u, 0u},")
    lines += [
        "};",
        "",
        "inline constexpr TopicPolicy kChannels[] = {",
    ]
    for name, spec in sorted(policy["channels"].items()):
        trigger = str(spec.get("trigger") or "unspecified")
        if trigger not in KNOWN_TRIGGERS:
            trigger = "unspecified"
        period = _as_int(spec.get("period_ms"), 0) if trigger == "period" else 0
        fps = _expect_fps_of(spec) if trigger == "on_change" else 0
        lines.append(
            f"    {{{_c_str(name)}, {_c_str(trigger)}, {period}u, {fps}u}},"
        )
    if not policy["channels"]:
        lines.append("    {\"\", \"unspecified\", 0u, 0u},")
    lines += [
        "};",
        "",
        "inline constexpr std::size_t kServicesSize =",
        "    sizeof(kServices) / sizeof(kServices[0]);",
        "inline constexpr std::size_t kChannelsSize =",
        "    sizeof(kChannels) / sizeof(kChannels[0]);",
        "",
        "inline const TopicPolicy* FindService(const char* id) {",
        "  if (!id) {",
        "    return nullptr;",
        "  }",
        "  for (std::size_t i = 0; i < kServicesSize; ++i) {",
        "    if (kServices[i].id[0] && std::strcmp(kServices[i].id, id) == 0) {",
        "      return &kServices[i];",
        "    }",
        "  }",
        "  return nullptr;",
        "}",
        "",
        "inline const TopicPolicy* FindChannel(const char* id) {",
        "  if (!id) {",
        "    return nullptr;",
        "  }",
        "  for (std::size_t i = 0; i < kChannelsSize; ++i) {",
        "    if (kChannels[i].id[0] && std::strcmp(kChannels[i].id, id) == 0) {",
        "      return &kChannels[i];",
        "    }",
        "  }",
        "  return nullptr;",
        "}",
        "",
        "}  // namespace gf_gen::publish_policy",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def emit_publish_policy(req: dict[str, Any] | None, gen_dir: Path) -> dict[str, str]:
    hpp = gen_dir / "include" / "gf_gen" / "publish_policy.hpp"
    emit_publish_policy_hpp(req, hpp)
    return {"hpp": str(hpp)}
