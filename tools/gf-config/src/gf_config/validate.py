"""Pure in-memory project validation (load-gate / save-gate). No disk I/O, no mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gf_codegen.compose.emit_em_launch import gated_host_processes
from gf_codegen.compose.merge_platform import (
    enabled_platform_keys,
    is_host_platform_process,
    validate_platform,
    wiring_ap_processes,
)
from gf_codegen.compose.observability import validate_observability

from gf_config.names import is_channel_svc, short_service

# CMake always-on modules — must be authored in req.runtime_modules (no silent fill).
ALWAYS_ON_MODULES = frozenset({"core", "com", "osal"})


def _soa_short_set(items: list[Any] | None) -> set[str]:
    out: set[str] = set()
    for x in items or []:
        s = str(x or "").strip()
        if not s or is_channel_svc(s):
            continue
        sk = short_service(s)
        if sk:
            out.add(sk)
    return out


def _check_wiring_port_consistency(
    wiring: dict[str, Any],
    *,
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, Any]],
) -> None:
    """dataflow / bindings must match deployments provides|requires.

    Canvas builds In/Out circles from deployments only. A dataflow (or binding)
    for a service the process does not declare causes edges to share one port
    (GUI used to fall back to ports[0]) — catch that at Verify, not by eye.
    """
    dep_map: dict[str, dict[str, Any]] = {}
    for d in wiring.get("deployments") or []:
        if not isinstance(d, dict):
            continue
        name = str(d.get("process") or "").strip()
        if name:
            dep_map[name] = d

    detail: list[str] = []

    for fl in wiring.get("dataflows") or []:
        if not isinstance(fl, dict):
            continue
        frm = str(fl.get("from") or "").strip()
        to = str(fl.get("to") or "").strip()
        svc_raw = str(fl.get("service") or "").strip()
        if not frm or not to or not svc_raw or is_channel_svc(svc_raw):
            continue
        svc = short_service(svc_raw)
        if not svc:
            continue
        src = dep_map.get(frm)
        dst = dep_map.get(to)
        if src is None:
            msg = f"dataflow {svc}: from={frm} has no deployments[] row"
            errors.append(msg)
            detail.append(msg)
            continue
        if dst is None:
            msg = f"dataflow {svc}: to={to} has no deployments[] row"
            errors.append(msg)
            detail.append(msg)
            continue
        if svc not in _soa_short_set(src.get("provides")):
            msg = (
                f"dataflow {svc}: {frm} → {to} but {frm} deployments.provides "
                f"does not list {svc}"
            )
            errors.append(msg)
            detail.append(msg)
        if svc not in _soa_short_set(dst.get("requires")):
            msg = (
                f"dataflow {svc}: {frm} → {to} but {to} deployments.requires "
                f"does not list {svc} (canvas will lack a distinct In port)"
            )
            errors.append(msg)
            detail.append(msg)

    for b in wiring.get("bindings") or []:
        if not isinstance(b, dict):
            continue
        mod = str(b.get("module") or "").strip()
        if not mod:
            continue
        dep = dep_map.get(mod)
        if dep is None:
            # Module may be declared only under modules[] without a process row.
            warnings.append(
                f"bindings module={mod}: no matching deployments.process "
                "(skip provide/require cross-check)"
            )
            continue
        prov = _soa_short_set(dep.get("provides"))
        req = _soa_short_set(dep.get("requires"))
        for inp in b.get("inputs") or []:
            if not isinstance(inp, dict):
                continue
            svc = short_service(str(inp.get("service") or ""))
            if not svc or is_channel_svc(str(inp.get("service") or "")):
                continue
            if svc not in req:
                msg = (
                    f"bindings {mod} input {svc} missing from "
                    f"deployments.requires (add require or drop binding)"
                )
                errors.append(msg)
                detail.append(msg)
        for out in b.get("outputs") or []:
            if not isinstance(out, dict):
                continue
            svc = short_service(str(out.get("service") or ""))
            if not svc or is_channel_svc(str(out.get("service") or "")):
                continue
            if svc not in prov:
                msg = (
                    f"bindings {mod} output {svc} missing from "
                    f"deployments.provides (add provide or drop binding)"
                )
                errors.append(msg)
                detail.append(msg)

    checks.append(
        {
            "id": "wiring_port_consistency",
            "status": "fail" if detail else "pass",
            "detail": detail,
        }
    )


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def format_errors(self, *, limit: int = 40) -> str:
        if not self.errors:
            return ""
        lines = self.errors[:limit]
        extra = len(self.errors) - len(lines)
        text = "\n".join(f"• {e}" for e in lines)
        if extra > 0:
            text += f"\n… (+{extra})"
        return text


def capability_host_flags(
    req: dict[str, Any],
    ara_cfg: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, bool, bool]:
    """(k_dlt, k_roudi, k_frame_ingest) from authored req + log sinks."""
    ara_cfg = ara_cfg or {}
    log = ara_cfg.get("log") or {}
    sinks = {str(s).strip().lower() for s in (log.get("sinks") or [])}
    k_dlt = "dlt" in sinks
    bindings = [str(b).strip().lower() for b in (req.get("bindings") or [])]
    k_roudi = "iceoryx" in bindings
    fi = req.get("frame_ingest")
    if not isinstance(fi, dict):
        fi = {}
    bridge = fi.get("bridge") if isinstance(fi.get("bridge"), dict) else {}
    active = str(fi.get("active_source") or "none").strip().lower()
    k_frame = bool(bridge.get("enabled")) or (active not in ("", "none"))
    return k_dlt, k_roudi, k_frame


def _host_names_in_processes(doc: dict[str, Any] | None) -> set[str]:
    out: set[str] = set()
    if not isinstance(doc, dict):
        return out
    for p in doc.get("processes") or []:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if name and is_host_platform_process(name):
            out.add(name)
    return out


def _check_host_membership(
    *,
    table: str,
    present: set[str],
    wanted: set[str],
    errors: list[str],
    checks: list[dict[str, Any]],
) -> None:
    missing = sorted(wanted - present)
    extra = sorted(present - wanted)
    detail: list[str] = []
    if missing:
        detail.append(f"missing host rows: {', '.join(missing)}")
        for h in missing:
            errors.append(
                f"platform.{table}: capability requires {h} but it is not in the table "
                "(add the row; gf-config does not auto-insert)."
            )
    if extra:
        detail.append(f"extra host rows: {', '.join(extra)}")
        for h in extra:
            errors.append(
                f"platform.{table}: {h} is present but capability is off "
                "(remove the row or enable the capability)."
            )
    checks.append(
        {
            "id": f"platform_{table}_host_capability",
            "status": "fail" if detail else "pass",
            "wanted": sorted(wanted),
            "present": sorted(present),
            "detail": detail,
        }
    )


def validate_project(
    req: dict[str, Any],
    wiring: dict[str, Any],
    ara_cfg: dict[str, dict[str, Any]],
    *,
    project_dir: Path | None = None,
) -> ValidationResult:
    """Validate authored inputs in memory. Does not mutate arguments or touch disk."""
    result = ValidationResult()
    mods = [str(x) for x in (req.get("runtime_modules") or [])]
    missing_on = sorted(ALWAYS_ON_MODULES - set(mods))
    if missing_on:
        result.errors.append(
            "req.runtime_modules missing always-on modules: "
            + ", ".join(missing_on)
            + " (must be authored; open/save will not auto-fill)."
        )
        result.checks.append(
            {
                "id": "runtime_modules_always_on",
                "status": "fail",
                "missing": missing_on,
            }
        )
    else:
        result.checks.append({"id": "runtime_modules_always_on", "status": "pass"})

    enabled = enabled_platform_keys(mods, ara_cfg)
    loaded = {k: ara_cfg[k] for k in enabled if k in ara_cfg}

    k_dlt, k_roudi, k_frame = capability_host_flags(req, ara_cfg)
    wanted = set(
        gated_host_processes(k_dlt=k_dlt, k_roudi=k_roudi, k_frame_ingest=k_frame)
    )
    if "exec" in loaded:
        _check_host_membership(
            table="exec",
            present=_host_names_in_processes(loaded.get("exec")),
            wanted=wanted,
            errors=result.errors,
            checks=result.checks,
        )
    if "em_launch" in loaded:
        _check_host_membership(
            table="em_launch",
            present=_host_names_in_processes(loaded.get("em_launch")),
            wanted=wanted,
            errors=result.errors,
            checks=result.checks,
        )

    ap = wiring_ap_processes(wiring)
    p_err, p_warn, p_checks = validate_platform(
        loaded,
        ap_processes=ap,
        req=req,
        project_dir=project_dir,
    )
    result.errors.extend(p_err)
    result.warnings.extend(p_warn)
    result.checks.extend(p_checks)

    o_err, o_warn, o_checks = validate_observability(req, wiring=wiring)
    result.errors.extend(o_err)
    result.warnings.extend(o_warn)
    result.checks.extend(o_checks)

    _check_wiring_port_consistency(
        wiring,
        errors=result.errors,
        warnings=result.warnings,
        checks=result.checks,
    )

    return result
