"""Load and validate against gf.sor.schema.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from gf_codegen.paths import find_repo_root


def default_schema_path(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    return root / "schemas" / "gf.sor.schema.json"


def load_schema(schema_path: Path) -> dict[str, Any]:
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_sor(sor: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Return a list of error messages (empty if ok)."""
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in sorted(validator.iter_errors(sor), key=lambda e: list(e.path))]
