"""Emit gf_gen/deploy_config.hpp — compile-frozen SKU deploy (SIL/HIL/SOP).

Authoring stays in gf-config YAML; product runtime reads this header only
(EM Spawn table + Flow debug bools). No .env; no board-side YAML for behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gf_codegen.compose.emit_em_launch import build_product_em_tables
from gf_codegen.compose.emit_iox import iceoryx_enabled
from gf_codegen.compose.observability import live_tap_config, normalize_profile


def _c_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _cxx_bool(v: bool) -> str:
    return "true" if v else "false"


def _ident(name: str) -> str:
    out = []
    for ch in name:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "".join(out) or "proc"


def _log_sinks(platform: dict[str, Any] | None) -> list[str]:
    log = (platform or {}).get("log") if isinstance(platform, dict) else None
    if not isinstance(log, dict):
        return []
    sinks = log.get("sinks") or []
    if not isinstance(sinks, list):
        return []
    return [str(s).strip().lower() for s in sinks if str(s).strip()]


def _doip_enabled(platform: dict[str, Any] | None) -> bool:
    diag = (platform or {}).get("diag") if isinstance(platform, dict) else None
    if not isinstance(diag, dict):
        return False
    doip = diag.get("doip") if isinstance(diag.get("doip"), dict) else {}
    if diag.get("iso_13400_doip") in (True, 1, "true", "True"):
        return bool(doip.get("enabled", True))
    if isinstance(diag.get("standards"), list) and any(
        "13400" in str(x) for x in diag["standards"]
    ):
        return bool(doip.get("enabled", True))
    return bool(doip.get("enabled", False))


def _runtime_modules(req: dict[str, Any]) -> set[str]:
    mods = req.get("runtime_modules") or []
    if not isinstance(mods, list):
        return set()
    return {str(m).strip() for m in mods if str(m).strip()}


def _as_int(v: Any, default: int) -> int:
    if v is None:
        return default
    try:
        return int(str(v), 0)
    except (TypeError, ValueError):
        return default


def normalize_doip_params(platform: dict[str, Any] | None) -> dict[str, Any]:
    """DoIP / UDS timing + OTA transfer params from platform diag."""
    diag = (platform or {}).get("diag") if isinstance(platform, dict) else None
    if not isinstance(diag, dict):
        diag = {}
    doip = diag.get("doip") if isinstance(diag.get("doip"), dict) else {}
    timing = diag.get("timing") if isinstance(diag.get("timing"), dict) else {}
    xfer = diag.get("ota_transfer") if isinstance(diag.get("ota_transfer"), dict) else {}
    mode = str(xfer.get("mode") or "request_file_transfer").strip() or "request_file_transfer"
    return {
        "tcp_port": _as_int(doip.get("tcp_port"), 13400),
        "logical_address": _as_int(doip.get("logical_address"), 0x0E00),
        "tester_address": _as_int(doip.get("tester_address"), 0x0E80),
        "s3_server_ms": _as_int(timing.get("s3_server_ms"), 5000),
        "tester_present_period_ms": _as_int(timing.get("tester_present_period_ms"), 2000),
        "p2_server_ms": _as_int(timing.get("p2_server_ms"), 50),
        "p2_star_server_ms": _as_int(timing.get("p2_star_server_ms"), 5000),
        "security_delay_ms": _as_int(timing.get("security_delay_ms"), 10000),
        "ota_mode": mode,
        "ota_require_prog": bool(xfer.get("require_programming_session", True)),
        "ota_require_security": bool(xfer.get("require_security", True)),
        "ota_max_block": _as_int(xfer.get("max_block_length"), 1024),
    }


def normalize_deploy_flags(
    req: dict[str, Any],
    platform: dict[str, Any] | None,
    *,
    wiring: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bools for EM presence + Flow/GMT debug (not EM spawn)."""
    mods = _runtime_modules(req)
    live_on, _svcs = live_tap_config(req, wiring=wiring)
    profile = normalize_profile(req)
    k_em = "exec" in mods
    k_dlt = ("dlt" in _log_sinks(platform)) and k_em
    k_roudi = iceoryx_enabled(req) and k_em
    return {
        "k_em": k_em,
        "k_dlt": k_dlt,
        "k_roudi": k_roudi,
        "k_live_tap": bool(live_on),
        "k_doip": _doip_enabled(platform),
        "k_inject_built": profile == "vehicle-debug",
        "profile": profile,
        "doip": normalize_doip_params(platform),
    }


# Back-compat alias used by older tests / imports
normalize_sil_runtime = normalize_deploy_flags


def _phm_restart_map(platform: dict[str, Any] | None) -> dict[str, bool]:
    phm = (platform or {}).get("phm") if isinstance(platform, dict) else None
    if not isinstance(phm, dict):
        return {}
    out: dict[str, bool] = {}
    for e in phm.get("entities") or []:
        if not isinstance(e, dict):
            continue
        proc = str(e.get("process") or "").strip()
        if not proc:
            continue
        out[proc] = str(e.get("on_failure") or "").strip() == "restart"
    return out


def emit_deploy_config_hpp(
    flags: dict[str, Any],
    launch_procs: list[dict[str, Any]],
    exec_procs: list[dict[str, Any]],
    *,
    restart_by_process: dict[str, bool],
    out_path: Path,
) -> None:
    deps_by_name = {
        str(p.get("name") or "").strip(): [
            str(d).strip() for d in (p.get("depends_on") or []) if str(d).strip()
        ]
        for p in exec_procs
        if isinstance(p, dict) and str(p.get("name") or "").strip()
    }

    lines: list[str] = [
        "// Generated by gf_codegen.compose — do not edit by hand",
        "// deploy_config: gf-config → compose → rebuild. SIL/HIL/SOP share this freeze.",
        "// EM reads kEmLaunch at runtime (no board YAML). Flow bools are debug hints.",
        "#pragma once",
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace gf_gen::deploy {",
        "",
        f"inline constexpr bool kEm = {_cxx_bool(flags['k_em'])};",
        f"inline constexpr bool kDlt = {_cxx_bool(flags['k_dlt'])};",
        f"inline constexpr bool kRouDi = {_cxx_bool(flags['k_roudi'])};",
        f"inline constexpr bool kLiveTap = {_cxx_bool(flags['k_live_tap'])};",
        f"inline constexpr bool kDoip = {_cxx_bool(flags['k_doip'])};",
        f"inline constexpr bool kInjectBuilt = {_cxx_bool(flags['k_inject_built'])};",
        "",
    ]
    doip = flags.get("doip") if isinstance(flags.get("doip"), dict) else normalize_doip_params(None)
    lines += [
        f"inline constexpr std::uint16_t kDoipTcpPort = {int(doip['tcp_port'])}u;",
        f"inline constexpr std::uint16_t kDoipLogicalAddr = {int(doip['logical_address']):#06x}u;",
        f"inline constexpr std::uint16_t kDoipTesterAddr = {int(doip['tester_address']):#06x}u;",
        f"inline constexpr std::uint32_t kDiagS3ServerMs = {int(doip['s3_server_ms'])}u;",
        f"inline constexpr std::uint32_t kDiagTesterPresentPeriodMs = "
        f"{int(doip['tester_present_period_ms'])}u;",
        f"inline constexpr std::uint32_t kDiagP2ServerMs = {int(doip['p2_server_ms'])}u;",
        f"inline constexpr std::uint32_t kDiagP2StarServerMs = "
        f"{int(doip['p2_star_server_ms'])}u;",
        f"inline constexpr std::uint32_t kDiagSecurityDelayMs = "
        f"{int(doip['security_delay_ms'])}u;",
        f"inline constexpr const char* kOtaTransferMode = {_c_str(str(doip['ota_mode']))};",
        f"inline constexpr bool kOtaRequireProgSession = "
        f"{_cxx_bool(bool(doip['ota_require_prog']))};",
        f"inline constexpr bool kOtaRequireSecurity = "
        f"{_cxx_bool(bool(doip['ota_require_security']))};",
        f"inline constexpr std::uint32_t kOtaMaxBlockLength = {int(doip['ota_max_block'])}u;",
        "",
        "struct EmLaunchEntry {",
        "  const char* name;",
        "  const char* binary;",
        "  const char* const* args;",
        "  std::size_t argc;",
        "  const char* const* depends_on;",
        "  std::size_t ndeps;",
        "  bool restart_enabled;",
        "  std::uint32_t max_restarts;",
        "};",
        "",
    ]

    entry_lines: list[str] = []
    for p in launch_procs:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        ident = _ident(name)
        binary = str(p.get("binary") or "").strip()
        args = [str(a) for a in (p.get("args") or [])]
        deps = deps_by_name.get(name, [])
        try:
            max_r = int(p.get("max_restarts") or 3)
        except (TypeError, ValueError):
            max_r = 3
        restart = bool(restart_by_process.get(name, False))

        if args:
            lines.append(f"inline constexpr const char* kArgs_{ident}[] = {{")
            lines.append("  " + ", ".join(_c_str(a) for a in args) + ",")
            lines.append("};")
            args_ptr = f"kArgs_{ident}"
            argc = str(len(args))
        else:
            args_ptr = "nullptr"
            argc = "0"
        if deps:
            lines.append(f"inline constexpr const char* kDeps_{ident}[] = {{")
            lines.append("  " + ", ".join(_c_str(d) for d in deps) + ",")
            lines.append("};")
            deps_ptr = f"kDeps_{ident}"
            ndeps = str(len(deps))
        else:
            deps_ptr = "nullptr"
            ndeps = "0"
        lines.append("")
        entry_lines.append(
            "  {"
            f"{_c_str(name)}, {_c_str(binary)}, {args_ptr}, {argc}u, "
            f"{deps_ptr}, {ndeps}u, {_cxx_bool(restart)}, {max_r}u"
            "},"
        )

    lines.append("inline constexpr EmLaunchEntry kEmLaunch[] = {")
    lines.extend(entry_lines)
    lines.append("};")
    lines.append("")
    lines.append(
        f"inline constexpr std::size_t kEmLaunchCount = "
        f"sizeof(kEmLaunch) / sizeof(kEmLaunch[0]);"
    )
    lines.append("")
    lines.append("}  // namespace gf_gen::deploy")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def emit_deploy_config(
    req: dict[str, Any],
    platform: dict[str, Any] | None,
    platform_dir: Path,
    gen_dir: Path,
    *,
    wiring: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write deploy_config.hpp + human-readable generated em_launch/exec YAML."""
    import yaml

    flags = normalize_deploy_flags(req, platform, wiring=wiring)
    tables = build_product_em_tables(
        platform_dir,
        k_dlt=bool(flags["k_dlt"]),
        k_roudi=bool(flags["k_roudi"]),
        gateway_forever=True,
    )
    # YAML for compose diff / humans only — EM product path ignores them.
    gen_dir.mkdir(parents=True, exist_ok=True)
    launch_path = gen_dir / "em_launch.yaml"
    exec_path = gen_dir / "exec.yaml"
    launch_path.write_text(
        yaml.safe_dump(tables["launch"], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    exec_path.write_text(
        yaml.safe_dump(tables["exec"], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    hpp = gen_dir / "include" / "gf_gen" / "deploy_config.hpp"
    emit_deploy_config_hpp(
        flags,
        list(tables["launch"].get("processes") or []),
        list(tables["exec"].get("processes") or []),
        restart_by_process=_phm_restart_map(platform),
        out_path=hpp,
    )
    return {
        "hpp": str(hpp),
        "em_launch": str(launch_path),
        "exec": str(exec_path),
        "flags": flags,
    }
