"""Load platform/*.yaml, validate process refs, merge into SOR platform_manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gf_codegen.compose.load_project import PLATFORM_KEYS, ProjectPaths

# runtime_modules that unlock each platform file
_MODULE_UNLOCK: dict[str, frozenset[str]] = {
    "exec": frozenset({"exec", "sm"}),
    "phm": frozenset({"phm"}),
    "diag": frozenset({"diag"}),
    "log": frozenset({"log"}),
    "ucm": frozenset({"ucm"}),
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

    if "phm" in loaded:
        bad_phm: list[str] = []
        for i, ent in enumerate(loaded["phm"].get("entities") or []):
            if not isinstance(ent, dict):
                bad_phm.append(f"entities[{i}] not an object")
                continue
            eid = str(ent.get("id") or "").strip() or f"[{i}]"
            name = str(ent.get("process") or "").strip()
            if not name:
                bad_phm.append(f"entity {eid}: missing process")
                continue
            if name.startswith("external."):
                bad_phm.append(f"entity {eid}: process must not be external: {name}")
            elif name not in ap_processes:
                bad_phm.append(f"entity {eid}: process not in wiring (non-external): {name}")
        if bad_phm:
            errors.extend(f"platform.phm: {x}" for x in bad_phm)
            checks.append({"id": "platform_phm_processes", "status": "fail", "detail": bad_phm})
        else:
            checks.append({"id": "platform_phm_processes", "status": "pass"})

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
    v_err, v_warn, v_checks = validate_platform(loaded, ap_processes=ap)
    errors.extend(v_err)
    warnings.extend(v_warn)
    checks.extend(v_checks)

    if loaded and not missing and not v_err:
        sor["platform_manifest"] = build_platform_manifest(loaded)
    else:
        sor.pop("platform_manifest", None)

    return errors, warnings, checks
