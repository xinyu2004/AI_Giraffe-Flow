"""Authored Giraffe types (cfg/types.yaml) — compose input, not C headers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gf_codegen.compose.parse_hpp import parse_hpp_file, structs_to_sor_types
from gf_codegen.paths import resolve_path


def types_yaml_path(project_dir: Path) -> Path:
    return project_dir / "cfg" / "types.yaml"


def mappings_yaml_path(project_dir: Path) -> Path:
    return project_dir / "cfg" / "mappings.yaml"


def load_types_yaml(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    out: list[dict[str, Any]] = []
    for t in data.get("types") or []:
        if isinstance(t, dict) and t.get("id"):
            out.append(t)
    return out


def load_mappings_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def save_mappings_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = dict(data)
    doc.setdefault("schema_version", "0.1")
    path.write_text(
        yaml.safe_dump(doc, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def save_types_yaml(
    path: Path,
    types: list[dict[str, Any]],
    *,
    imported_from: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {"schema_version": "0.1", "types": list(types)}
    if imported_from:
        doc["imported_from"] = imported_from
    path.write_text(
        yaml.safe_dump(doc, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def merge_type_lists(
    base: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    overwrite: bool = True,
) -> list[dict[str, Any]]:
    order: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for t in base:
        tid = str(t.get("id") or "")
        if not tid:
            continue
        if tid not in by_id:
            order.append(tid)
        by_id[tid] = t
    for t in incoming:
        tid = str(t.get("id") or "")
        if not tid:
            continue
        if tid not in by_id:
            order.append(tid)
            by_id[tid] = t
            continue
        if overwrite:
            by_id[tid] = t
        elif not (by_id[tid].get("fields") or []) and (t.get("fields") or []):
            by_id[tid] = t
    return [by_id[i] for i in order]


def merge_types_into_sor(sor: dict[str, Any], types: list[dict[str, Any]]) -> None:
    sor["types"] = merge_type_lists(list(sor.get("types") or []), types, overwrite=True)


def hpp_files_from_wiring(wiring: dict[str, Any]) -> list[str]:
    rels: list[str] = []
    for mod in wiring.get("modules") or []:
        if not isinstance(mod, dict):
            continue
        hpp = mod.get("hpp")
        if isinstance(hpp, str):
            rels.append(hpp)
        elif isinstance(hpp, list):
            rels.extend(str(x) for x in hpp if x)
    return rels


def parse_hpp_to_types(path: Path) -> list[dict[str, Any]]:
    return structs_to_sor_types(parse_hpp_file(path))


def ingest_hpp_into_types(
    project_dir: Path,
    hpp_path: Path,
) -> list[dict[str, Any]]:
    """Parse a vendor header once and merge structs into cfg/types.yaml."""
    incoming = parse_hpp_to_types(hpp_path)
    path = types_yaml_path(project_dir)
    merged = merge_type_lists(load_types_yaml(path), incoming, overwrite=True)
    save_types_yaml(path, merged, imported_from=str(hpp_path))
    return incoming


def ingest_dbc_into_mappings(
    project_dir: Path,
    dbc_path: Path,
    *,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Digest DBC into cfg/mappings.yaml (adapter_mappings only)."""
    from gf_codegen.compose.import_oem import import_oem

    overlay = import_oem(dbc_path, manifest_path)
    path = mappings_yaml_path(project_dir)
    existing = load_mappings_yaml(path)
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for m in list(existing.get("adapter_mappings") or []) + list(
        overlay.get("adapter_mappings") or []
    ):
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "")
        if not mid:
            continue
        if mid not in by_id:
            order.append(mid)
        by_id[mid] = m
    existing["adapter_mappings"] = [by_id[i] for i in order]
    save_mappings_yaml(path, existing)
    return overlay


def bootstrap_types_from_wiring(
    project_dir: Path,
    *,
    repo_root: Path,
    wiring: dict[str, Any],
) -> list[dict[str, Any]]:
    """One-shot digest of module headers listed in wiring. Callers then persist YAML."""
    merged: list[dict[str, Any]] = []
    for rel in hpp_files_from_wiring(wiring):
        hpp_path = resolve_path(project_dir, rel, repo_root=repo_root)
        if not hpp_path.is_file():
            continue
        merged = merge_type_lists(merged, parse_hpp_to_types(hpp_path), overwrite=True)
    return merged
