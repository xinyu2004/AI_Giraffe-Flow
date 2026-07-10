"""Write SOR JSON and lineage YAML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def write_sor(path: Path, sor: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(sor, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_lineage(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f, sort_keys=False, allow_unicode=True)
