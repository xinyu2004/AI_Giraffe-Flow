"""Load and validate against gf.sor.schema.json (lives under tools/gf-codegen/schemas/)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from gf_codegen.paths import SCHEMA_REL, find_repo_root


def packaged_schema_path() -> Path:
    """Schema next to this package: tools/gf-codegen/schemas/gf.sor.schema.json."""
    return Path(__file__).resolve().parents[2] / "schemas" / "gf.sor.schema.json"


def default_schema_path(repo_root: Path | None = None) -> Path:
    packaged = packaged_schema_path()
    if packaged.is_file():
        return packaged
    root = repo_root or find_repo_root()
    return root / SCHEMA_REL / "gf.sor.schema.json"


def load_schema(schema_path: Path) -> dict[str, Any]:
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_sor(sor: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Return a list of error messages (empty if ok)."""
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in sorted(validator.iter_errors(sor), key=lambda e: list(e.path))]
