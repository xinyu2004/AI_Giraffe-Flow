"""Load platform/*.yaml, validate process refs, merge into SOR platform_manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gf_codegen.compose.load_project import PLATFORM_KEYS, ProjectPaths
from gf_codegen.compose.mem_budget import estimate_mem_budget

# runtime_modules that unlock each platform file
_MODULE_UNLOCK: dict[str, frozenset[str]] = {
    "exec": frozenset({"exec", "sm"}),
    # OS EM daemon launch map (binaries); unlocked with exec
    "em_launch": frozenset({"exec"}),
    "phm": frozenset({"phm"}),
    "diag": frozenset({"diag"}),
    "log": frozenset({"log"}),
    "ucm": frozenset({"ucm"}),
    "collector": frozenset({"collector", "phm", "diag"}),
    # bounds always load when any boundable module is on
    "bounds": frozenset({"log", "collector", "diag", "com", "per"}),
    "tsync": frozenset({"tsync"}),
}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def wiring_ap_processes(wiring: dict[str, Any] | None = None, *, sor: dict[str, Any] | None = None) -> set[str]:
    """Process names eligible for exec/phm (non-external). Prefer wiring, else SOR deployments."""
    names: set[str] = set()
    deps: list[Any] = []
    if wiring and isinstance(wiring.get("deployments"), list):
        deps = wiring["deployments"]
    elif sor and isinstance(sor.get("deployments"), list):
        deps = sor["deployments"]
    for d in deps:
        if not isinstance(d, dict):
            continue
        name = str(d.get("process") or "").strip()
        if not name or name.startswith("external."):
            continue
        names.add(name)
    return names


def _enabled_keys(runtime_modules: list[str], platform_paths: dict[str, Path]) -> list[str]:
    mods = {str(m) for m in runtime_modules}
    out: list[str] = []
    for key in PLATFORM_KEYS:
        if key not in platform_paths:
            continue
        unlock = _MODULE_UNLOCK.get(key, frozenset())
        if mods & unlock:
            out.append(key)
    return out


def validate_platform(
    loaded: dict[str, dict[str, Any]],
    *,
    ap_processes: set[str],
    req: dict[str, Any] | None = None,
    project_dir: Path | None = None,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Return (errors, warnings, checks)."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    if "exec" in loaded:
        exec_data = loaded["exec"]
        bad: list[str] = []
        unknown_deps: list[str] = []
        fg_ids = {
            str(fg.get("id"))
            for fg in (exec_data.get("function_groups") or [])
            if isinstance(fg, dict) and fg.get("id")
        }
        for i, proc in enumerate(exec_data.get("processes") or []):
            if not isinstance(proc, dict):
                bad.append(f"processes[{i}] not an object")
                continue
            name = str(proc.get("name") or "").strip()
            if not name:
                bad.append(f"processes[{i}] missing name")
                continue
            if name.startswith("external."):
                bad.append(f"exec process must not be external: {name}")
            elif name not in ap_processes:
                bad.append(f"exec process not in wiring (non-external): {name}")
            fg = str(proc.get("function_group") or "").strip()
            if fg and fg_ids and fg not in fg_ids:
                warnings.append(f"exec process {name}: unknown function_group {fg}")
            for dep in proc.get("depends_on") or []:
                dep_s = str(dep).strip()
                if dep_s and dep_s not in ap_processes:
                    unknown_deps.append(f"{name} depends_on {dep_s}")
        if bad:
            errors.extend(f"platform.exec: {x}" for x in bad)
            checks.append({"id": "platform_exec_processes", "status": "fail", "detail": bad})
        else:
            checks.append({"id": "platform_exec_processes", "status": "pass"})
        if unknown_deps:
            warnings.extend(f"platform.exec: {x}" for x in unknown_deps)

    if "em_launch" in loaded:
        bad_em: list[str] = []
        for i, proc in enumerate(loaded["em_launch"].get("processes") or []):
            if not isinstance(proc, dict):
                bad_em.append(f"processes[{i}] not an object")
                continue
            name = str(proc.get("name") or "").strip()
            binary = str(proc.get("binary") or "").strip()
            if not name:
                bad_em.append(f"processes[{i}] missing name")
                continue
            if name.startswith("external."):
                bad_em.append(f"em_launch process must not be external: {name}")
            elif name not in ap_processes:
                bad_em.append(f"em_launch process not in wiring (non-external): {name}")
            if not binary:
                bad_em.append(f"em_launch process {name}: missing binary")
        if bad_em:
            errors.extend(f"platform.em_launch: {x}" for x in bad_em)
            checks.append({"id": "platform_em_launch", "status": "fail", "detail": bad_em})
        else:
            checks.append({"id": "platform_em_launch", "status": "pass"})

    if "phm" in loaded:
        bad_phm: list[str] = []
        seen_ids: set[str] = set()
        seen_procs: set[str] = set()
        for i, ent in enumerate(loaded["phm"].get("entities") or []):
            if not isinstance(ent, dict):
                bad_phm.append(f"entities[{i}] not an object")
                continue
            eid = str(ent.get("id") or "").strip()
            if not eid:
                bad_phm.append(f"entities[{i}]: missing id")
                continue
            if eid in seen_ids:
                bad_phm.append(f"duplicate entity id: {eid}")
            else:
                seen_ids.add(eid)
            name = str(ent.get("process") or "").strip()
            if not name:
                bad_phm.append(f"entity {eid}: missing process")
                continue
            if name.startswith("external."):
                bad_phm.append(f"entity {eid}: process must not be external: {name}")
            elif name not in ap_processes:
                bad_phm.append(f"entity {eid}: process not in wiring (non-external): {name}")
            elif name in seen_procs:
                bad_phm.append(f"duplicate process: {name}")
            else:
                seen_procs.add(name)
        if bad_phm:
            errors.extend(f"platform.phm: {x}" for x in bad_phm)
            checks.append({"id": "platform_phm_processes", "status": "fail", "detail": bad_phm})
        else:
            checks.append({"id": "platform_phm_processes", "status": "pass"})

    if "log" in loaded:
        bad_log: list[str] = []
        seen_ctx: set[str] = set()
        for i, ctx in enumerate(loaded["log"].get("contexts") or []):
            if not isinstance(ctx, dict):
                bad_log.append(f"contexts[{i}] not an object")
                continue
            cid = str(ctx.get("id") or "").strip()
            if not cid:
                bad_log.append(f"contexts[{i}]: missing id")
                continue
            if cid in seen_ctx:
                bad_log.append(f"duplicate context id: {cid}")
            else:
                seen_ctx.add(cid)
        if bad_log:
            errors.extend(f"platform.log: {x}" for x in bad_log)
            checks.append({"id": "platform_log_contexts", "status": "fail", "detail": bad_log})
        else:
            checks.append({"id": "platform_log_contexts", "status": "pass"})

    # BL-MEM-BOUND / BL-MEM-ROUDI static estimate (formulas in mem_budget.py)
    report_path = (
        (project_dir / "generated" / "iox_shm_report.json") if project_dir else None
    )
    est = estimate_mem_budget(loaded, req=req, shm_report_path=report_path)
    for e in est.get("errors") or []:
        errors.append(f"platform.mem_budget: {e}")
    for w in est.get("warnings") or []:
        warnings.append(f"platform.mem_budget: {w}")
    checks.append(
        {
            "id": "platform_mem_budget",
            "status": "fail" if est.get("errors") else "pass",
            "total_ram_bytes": est.get("total_ram_bytes"),
            "total_disk_bytes": est.get("total_disk_bytes"),
            "total_shm_bytes": est.get("total_shm_bytes"),
            "lines": est.get("lines"),
            "constants": est.get("constants"),
            "formula_doc": est.get("formula_doc"),
            "iceoryx_enabled": est.get("iceoryx_enabled"),
            "roudi_mgmt_status": est.get("roudi_mgmt_status"),
            "detail": est.get("errors") or est.get("warnings") or [],
        }
    )

    return errors, warnings, checks


def build_platform_manifest(loaded: dict[str, dict[str, Any]]) -> dict[str, Any]:
    manifest: dict[str, Any] = {"schema_version": "0.1"}
    for key in PLATFORM_KEYS:
        if key in loaded:
            # drop nested schema_version noise; keep body
            body = dict(loaded[key])
            body.pop("schema_version", None)
            manifest[key] = body
    return manifest


def merge_platform(
    sor: dict[str, Any],
    paths: ProjectPaths,
    req: dict[str, Any],
    *,
    wiring: dict[str, Any] | None = None,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """
    Load enabled platform YAMLs into sor['platform_manifest'].
    Returns (errors, warnings, checks) for lineage.
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    if not paths.platform:
        checks.append({"id": "platform_present", "status": "skip", "detail": "no project.platform"})
        return errors, warnings, checks

    runtime_modules = [str(x) for x in (req.get("runtime_modules") or [])]
    enabled = _enabled_keys(runtime_modules, paths.platform)
    if not enabled:
        checks.append(
            {
                "id": "platform_present",
                "status": "skip",
                "detail": "no platform modules in runtime_modules",
            }
        )
        # still clear stale? leave absent
        return errors, warnings, checks

    loaded: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for key in enabled:
        path = paths.platform[key]
        if not path.is_file():
            missing.append(f"{key}: {path}")
            continue
        loaded[key] = _load_yaml(path)

    if missing:
        errors.extend(f"platform file missing: {m}" for m in missing)
        checks.append({"id": "platform_files", "status": "fail", "missing": missing})
    else:
        checks.append({"id": "platform_files", "status": "pass", "loaded": list(loaded.keys())})

    ap = wiring_ap_processes(wiring, sor=sor)
    v_err, v_warn, v_checks = validate_platform(
        loaded,
        ap_processes=ap,
        req=req,
        project_dir=paths.project_dir,
    )
    errors.extend(v_err)
    warnings.extend(v_warn)
    checks.extend(v_checks)

    if loaded and not missing and not v_err:
        sor["platform_manifest"] = build_platform_manifest(loaded)
    else:
        sor.pop("platform_manifest", None)

    return errors, warnings, checks
