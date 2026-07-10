"""gf-codegen lint."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from gf_codegen.paths import find_repo_root
from gf_codegen.schema_load import default_schema_path, load_schema, validate_sor


def _extra_checks(sor: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    services = sor.get("services") or []
    if isinstance(services, list):
        ids = [s.get("id") for s in services if isinstance(s, dict)]
        if len(ids) != len(set(ids)):
            errors.append("services[].id must be unique")

    deployments = sor.get("deployments") or []
    if isinstance(deployments, list):
        procs = [d.get("process") for d in deployments if isinstance(d, dict)]
        if len(procs) != len(set(procs)):
            errors.append("deployments[].process must be unique")

    for i, flow in enumerate(sor.get("dataflows") or []):
        if not isinstance(flow, dict):
            errors.append(f"dataflows[{i}] must be an object")
            continue
        for key in ("from", "to", "service"):
            if key not in flow:
                errors.append(f"dataflows[{i}] missing '{key}'")
    return errors


def lint_file(sor_path: Path, schema_path: Path | None = None) -> int:
    sor_path = sor_path.resolve()
    if not sor_path.is_file():
        print(f"error: file not found: {sor_path}", file=sys.stderr)
        return 2

    try:
        with sor_path.open(encoding="utf-8") as f:
            sor = json.load(f)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON: {e}", file=sys.stderr)
        return 2

    if schema_path is None:
        try:
            schema_path = default_schema_path(find_repo_root(sor_path.parent))
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    schema = load_schema(schema_path)
    errors = validate_sor(sor, schema) + _extra_checks(sor)
    if errors:
        print(f"lint FAILED: {sor_path}", file=sys.stderr)
        for msg in errors:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    print(f"lint OK: {sor_path}")
    return 0
