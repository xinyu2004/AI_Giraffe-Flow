"""Apply wiring.yaml onto SOR dict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gf_codegen.compose.parse_fidl import fidl_structs_to_sor_types, parse_fidl_file
from gf_codegen.compose.parse_hpp import parse_hpp_file, structs_to_sor_types
from gf_codegen.paths import resolve_path


def _canon_service(s: str) -> str:
    s = s.strip()
    if s.startswith("services."):
        return s
    if s.startswith("semantic."):
        return f"services.{s}"
    return f"services.semantic.{s}"


def _short_semantic(s: str) -> str:
    s = _canon_service(s)
    if s.startswith("services."):
        return s[len("services.") :]
    return s


def _ensure_type(sor: dict[str, Any], type_id: str, fields: list[dict[str, Any]] | None = None) -> None:
    types = sor.setdefault("types", [])
    if any(isinstance(t, dict) and t.get("id") == type_id for t in types):
        return
    types.append({"id": type_id, "kind": "struct", "fields": fields or []})


def _ensure_service(sor: dict[str, Any], service_id: str, type_ref: str, period_ms: int = 50) -> None:
    services = sor.setdefault("services", [])
    if any(isinstance(s, dict) and s.get("id") == service_id for s in services):
        return
    services.append(
        {
            "id": service_id,
            "type_ref": type_ref,
            "kind": "event",
            "period_ms": period_ms,
        }
    )
    sem = sor.setdefault("semantic_services", [])
    short = _short_semantic(service_id)
    if not any(isinstance(x, dict) and x.get("id") == short for x in sem):
        sem.append({"id": short})


def apply_wiring(
    sor: dict[str, Any],
    wiring_path: Path,
    *,
    repo_root: Path,
    project_dir: Path,
) -> list[str]:
    """Mutate sor in place. Return warnings."""
    warnings: list[str] = []
    with wiring_path.open(encoding="utf-8") as f:
        wiring = yaml.safe_load(f) or {}

    # Parse module hpp / fidl → types
    for mod in wiring.get("modules") or []:
        hpp_rel = mod.get("hpp")
        if hpp_rel:
            hpp_path = resolve_path(project_dir, hpp_rel, repo_root=repo_root)
            if not hpp_path.is_file():
                warnings.append(f"hpp not found: {hpp_path}")
            else:
                structs = parse_hpp_file(hpp_path)
                for t in structs_to_sor_types(structs):
                    _ensure_type(sor, t["id"], t.get("fields"))

        fidl_rel = mod.get("fidl")
        if fidl_rel:
            fidl_path = resolve_path(project_dir, fidl_rel, repo_root=repo_root)
            if not fidl_path.is_file():
                warnings.append(f"fidl not found: {fidl_path}")
            else:
                parsed = parse_fidl_file(fidl_path)
                for t in fidl_structs_to_sor_types(parsed.get("structs") or []):
                    _ensure_type(sor, t["id"], t.get("fields"))

    # Deployments
    deployments = []
    for d in wiring.get("deployments") or []:
        entry = {
            "process": d["process"],
            "compute_domain": d.get("compute_domain", "ap_linux"),
            "provides": [_canon_service(x) for x in (d.get("provides") or [])],
            "requires": [_canon_service(x) for x in (d.get("requires") or [])],
        }
        if d.get("package"):
            entry["package"] = d["package"]
        deployments.append(entry)
        # ensure services exist for provides
        for svc in entry["provides"]:
            short = svc.split(".")[-1]
            type_ref = f"types.{short}"
            if short == "Trajectory":
                # placeholder when no planning hpp
                types = sor.get("types") or []
                existing = next(
                    (t for t in types if isinstance(t, dict) and t.get("id") == type_ref),
                    None,
                )
                if existing is None:
                    _ensure_type(
                        sor,
                        type_ref,
                        [{"name": "point_count", "type": "uint8"}],
                    )
                    warnings.append("placeholder_type: types.Trajectory (no planning hpp)")
                elif not existing.get("fields"):
                    existing["fields"] = [{"name": "point_count", "type": "uint8"}]
                    warnings.append("placeholder_type: types.Trajectory (no planning hpp)")
            _ensure_service(sor, svc, type_ref)

    sor["deployments"] = deployments

    # Bindings → reinforce type_ref from struct names
    for b in wiring.get("bindings") or []:
        for item in list(b.get("inputs") or []) + list(b.get("outputs") or []):
            svc = _canon_service(item.get("service", ""))
            typ = item.get("type")
            if typ:
                type_ref = f"types.{typ}" if not str(typ).startswith("types.") else typ
                _ensure_type(sor, type_ref)
                _ensure_service(sor, svc, type_ref)

    # Dataflows
    flows = []
    for flow in wiring.get("dataflows") or []:
        flows.append(
            {
                "from": flow["from"],
                "service": _canon_service(flow["service"]),
                "to": flow["to"],
            }
        )
    sor["dataflows"] = flows

    # Store wiring-level bindings for reference (optional)
    sor["bindings"] = wiring.get("bindings") or []

    return warnings
