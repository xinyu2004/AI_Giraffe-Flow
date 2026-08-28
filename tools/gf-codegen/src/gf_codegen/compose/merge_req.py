"""Merge req.yaml into SOR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


from gf_codegen.compose.publish_policy import apply_publish_policy


def merge_req(sor: dict[str, Any], req_path: Path) -> list[str]:
    with req_path.open(encoding="utf-8") as f:
        req = yaml.safe_load(f) or {}
    if not isinstance(req, dict):
        req = {}

    if req.get("topology"):
        sor["topology"] = req["topology"]

    variant = {
        "id": req.get("variant") or req.get("product") or "default",
        "topology": req.get("topology") or sor.get("topology") or "ap_only",
        "runtime_modules": list(req.get("runtime_modules") or []),
        "bindings": list(req.get("bindings") or []),
        "capabilities": list(req.get("capabilities") or []),
    }
    if req.get("product"):
        variant["product"] = req["product"]

    sor["product_variants"] = [variant]

    # Keep acceptance for lineage; also stash under imports_meta
    if req.get("acceptance"):
        meta = sor.setdefault("imports_meta", {})
        if not isinstance(meta, dict):
            meta = {}
            sor["imports_meta"] = meta
        meta["acceptance"] = req["acceptance"]

    # Ensure compute_domains for ap_only
    if not sor.get("compute_domains"):
        sor["compute_domains"] = [
            {"id": "ap_linux", "runtime": "gf_full", "hosts_gf_code": True}
        ]

    return apply_publish_policy(sor, req)
