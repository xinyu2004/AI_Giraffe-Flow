"""Minimal C++ header parser for io_types.hpp (P0: no libclang)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_CXX_TO_SOR = {
    "uint8_t": "uint8",
    "uint16_t": "uint16",
    "uint32_t": "uint32",
    "uint64_t": "uint64",
    "int8_t": "int8",
    "int16_t": "int16",
    "int32_t": "int32",
    "int64_t": "int64",
    "float": "float32",
    "double": "float64",
    "bool": "bool",
}


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return text


def _map_type(cxx: str) -> str:
    cxx = cxx.strip()
    if cxx in _CXX_TO_SOR:
        return _CXX_TO_SOR[cxx]
    # nested struct name → types.Name later; keep bare name for now
    return cxx


def parse_hpp_file(path: Path) -> list[dict[str, Any]]:
    """Return list of {name, fields:[{name,type,array_size?}]}."""
    text = _strip_comments(path.read_text(encoding="utf-8"))
    # drop enum class blocks
    text = re.sub(r"enum\s+class\s+\w+[^{]*\{[^}]*\}", ";", text, flags=re.S)

    structs: list[dict[str, Any]] = []
    for m in re.finditer(r"struct\s+(\w+)\s*\{([^}]*)\}", text, flags=re.S):
        name = m.group(1)
        body = m.group(2)
        fields: list[dict[str, Any]] = []
        for line in body.split(";"):
            line = line.strip()
            if not line:
                continue
            # Type name  or  Type name[N]
            fm = re.match(
                r"^(?:const\s+)?(\w+(?:::\w+)*)\s+(\w+)(?:\s*\[\s*(\d+)\s*\])?\s*$",
                line,
            )
            if not fm:
                continue
            typ_raw, fname, arr = fm.group(1), fm.group(2), fm.group(3)
            # skip nested namespace qualifiers in type — take last component
            typ_raw = typ_raw.split("::")[-1]
            entry: dict[str, Any] = {
                "name": fname,
                "type": _map_type(typ_raw),
            }
            if arr is not None:
                entry["array_size"] = int(arr)
                # if element type looks like a struct name, prefix later
            fields.append(entry)
        structs.append({"name": name, "fields": fields})
    return structs


def structs_to_sor_types(structs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert parsed structs to SOR types[] entries; fix nested type refs."""
    known = {s["name"] for s in structs}
    out: list[dict[str, Any]] = []
    for s in structs:
        fields = []
        for f in s["fields"]:
            t = f["type"]
            if t in known:
                t = f"types.{t}"
            item: dict[str, Any] = {"name": f["name"], "type": t}
            if "array_size" in f:
                item["array_size"] = f["array_size"]
            fields.append(item)
        out.append({"id": f"types.{s['name']}", "kind": "struct", "fields": fields})
    return out
