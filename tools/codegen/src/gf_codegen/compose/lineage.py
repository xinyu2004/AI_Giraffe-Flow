"""Signal lineage checks (P0 minimal)."""

from __future__ import annotations

from typing import Any


def _canon(s: str) -> str:
    s = s.strip()
    if s.startswith("services."):
        return s
    if s.startswith("semantic."):
        return f"services.{s}"
    return f"services.semantic.{s}"


def run_lineage(sor: dict[str, Any], req: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    deployments = [d for d in (sor.get("deployments") or []) if isinstance(d, dict)]
    processes = {d.get("process") for d in deployments}

    provided: set[str] = set()
    required: dict[str, list[str]] = {}
    for d in deployments:
        proc = d.get("process")
        for p in d.get("provides") or []:
            provided.add(_canon(p))
        for r in d.get("requires") or []:
            required.setdefault(_canon(r), []).append(proc)

    # 1) requires have provider
    missing = sorted(svc for svc in required if svc not in provided)
    if missing:
        for svc in missing:
            errors.append(f"no provider for required service: {svc} (needed by {required[svc]})")
        checks.append({"id": "requires_have_provider", "status": "fail", "missing": missing})
    else:
        checks.append({"id": "requires_have_provider", "status": "pass"})

    # 2) dataflow endpoints
    bad_flows: list[str] = []
    for i, flow in enumerate(sor.get("dataflows") or []):
        if not isinstance(flow, dict):
            bad_flows.append(f"[{i}] not an object")
            continue
        fr, to = flow.get("from"), flow.get("to")
        if fr not in processes:
            bad_flows.append(f"[{i}] unknown from={fr}")
        if to not in processes:
            bad_flows.append(f"[{i}] unknown to={to}")
    if bad_flows:
        errors.extend(f"dataflow: {x}" for x in bad_flows)
        checks.append({"id": "dataflow_endpoints", "status": "fail", "detail": bad_flows})
    else:
        checks.append({"id": "dataflow_endpoints", "status": "pass"})

    # 3) required_services from req
    acceptance = (req or {}).get("acceptance") or {}
    if not acceptance:
        meta = sor.get("imports_meta") or {}
        if isinstance(meta, dict):
            acceptance = meta.get("acceptance") or {}
    req_svcs = [_canon(x) for x in (acceptance.get("required_services") or [])]
    service_ids = {
        _canon(s["id"])
        for s in (sor.get("services") or [])
        if isinstance(s, dict) and s.get("id")
    }
    missing_req = [s for s in req_svcs if s not in service_ids]
    if missing_req:
        errors.append(f"required_services missing from SOR: {missing_req}")
        checks.append(
            {"id": "required_services_present", "status": "fail", "missing": missing_req}
        )
    else:
        checks.append({"id": "required_services_present", "status": "pass"})

    # 4) module_owned not on gateway
    meta = sor.get("imports_meta") if isinstance(sor.get("imports_meta"), dict) else {}
    module_owned = meta.get("module_owned") or []
    gateway_provides = {_canon(x) for x in (meta.get("gateway_provides") or [])}
    conflicts = []
    for m in module_owned:
        sem = m.get("semantic")
        if sem and _canon(sem) in gateway_provides:
            conflicts.append(sem)
    if conflicts:
        errors.append(f"module_owned semantic also on gateway: {conflicts}")
        checks.append(
            {"id": "module_owned_not_on_gateway", "status": "fail", "conflicts": conflicts}
        )
    else:
        checks.append({"id": "module_owned_not_on_gateway", "status": "pass"})

    return {
        "project_id": (sor.get("product_variants") or [{}])[0].get("id")
        if sor.get("product_variants")
        else None,
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
