"""Lightweight Franca IDL (.fidl) parser for port candidates / SOR types (P1).

No full Franca grammar — extracts interface / struct / method / broadcast names
and simple struct fields. Sufficient for gf-config import + compose type merge.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_FIDL_TO_SOR = {
    "UInt8": "uint8",
    "UInt16": "uint16",
    "UInt32": "uint32",
    "UInt64": "uint64",
    "Int8": "int8",
    "Int16": "int16",
    "Int32": "int32",
    "Int64": "int64",
    "Boolean": "bool",
    "Float": "float32",
    "Double": "float64",
    "String": "string",
    "ByteBuffer": "bytes",
}


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    text = re.sub(r"<.*?/>", "", text, flags=re.S)  # Franca annotations
    return text


def _map_type(fidl: str) -> str:
    fidl = fidl.strip()
    if fidl in _FIDL_TO_SOR:
        return _FIDL_TO_SOR[fidl]
    # Array / Map wrappers: Array<Type> → keep inner for now
    m = re.match(r"^Array\s*<\s*(\w+)\s*>$", fidl)
    if m:
        return _map_type(m.group(1))
    return fidl


def _extract_balanced_blocks(text: str, keyword: str) -> list[tuple[str, str]]:
    """Return list of (name, body) for `keyword Name { ... }` with brace balance."""
    out: list[tuple[str, str]] = []
    pat = re.compile(rf"\b{keyword}\s+(\w+)\s*\{{", re.M)
    for m in pat.finditer(text):
        name = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        if depth == 0:
            out.append((name, text[start : i - 1]))
    return out


def _parse_struct_fields(body: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    # Type name;  or  Type name[]
    for line in body.split("\n"):
        line = line.strip().rstrip(";").strip()
        if not line or line.startswith("version"):
            continue
        fm = re.match(
            r"^(?:Array\s*<\s*(\w+)\s*>|(\w+(?:\.\w+)*))\s+(\w+)(?:\s*\[\s*(\d+)\s*\])?\s*$",
            line,
        )
        if not fm:
            continue
        typ_raw = fm.group(1) or fm.group(2)
        fname = fm.group(3)
        arr = fm.group(4)
        typ_raw = typ_raw.split(".")[-1]
        entry: dict[str, Any] = {"name": fname, "type": _map_type(typ_raw)}
        if arr is not None:
            entry["array_size"] = int(arr)
        fields.append(entry)
    return fields


def parse_fidl_file(path: Path) -> dict[str, Any]:
    """Parse .fidl → {package, interfaces, structs, methods, broadcasts, candidates}.

    candidates: short names suitable as wiring service / port labels
    (structs + broadcasts + methods + interface names, de-duped, stable order).
    """
    text = _strip_comments(path.read_text(encoding="utf-8"))

    pkg_m = re.search(r"\bpackage\s+([\w.]+)", text)
    package = pkg_m.group(1) if pkg_m else ""

    structs: list[dict[str, Any]] = []
    for name, body in _extract_balanced_blocks(text, "struct"):
        structs.append({"name": name, "fields": _parse_struct_fields(body)})

    interfaces: list[dict[str, Any]] = []
    methods: list[str] = []
    broadcasts: list[str] = []
    for iname, ibody in _extract_balanced_blocks(text, "interface"):
        iface_methods = [n for n, _ in _extract_balanced_blocks(ibody, "method")]
        iface_broadcasts = [n for n, _ in _extract_balanced_blocks(ibody, "broadcast")]
        methods.extend(iface_methods)
        broadcasts.extend(iface_broadcasts)
        interfaces.append(
            {
                "name": iname,
                "methods": iface_methods,
                "broadcasts": iface_broadcasts,
            }
        )

    # typeCollection may nest structs (already collected globally via keyword scan)
    type_collections = [n for n, _ in _extract_balanced_blocks(text, "typeCollection")]

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(n: str) -> None:
        if n and n not in seen:
            seen.add(n)
            candidates.append(n)

    for s in structs:
        _add(s["name"])
    for b in broadcasts:
        _add(b)
    for m in methods:
        _add(m)
    for iface in interfaces:
        _add(iface["name"])

    return {
        "package": package,
        "interfaces": interfaces,
        "structs": structs,
        "methods": methods,
        "broadcasts": broadcasts,
        "type_collections": type_collections,
        "candidates": candidates,
    }


def fidl_structs_to_sor_types(structs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same shape as parse_hpp.structs_to_sor_types."""
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
