"""Minimal AUTOSAR ARXML subset parser (P1 Track A).

Consumes hand-written or FARACON-produced .arxml. No Artop / IoNAS.
Extracts SHORT-NAME of sender-receiver interfaces and implementation data types
→ service / type candidates + imports_meta fragment.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _find_short_name(elem: ET.Element) -> str | None:
    for child in elem:
        if _local(child.tag) == "SHORT-NAME" and child.text:
            return child.text.strip()
    return None


def parse_arxml_file(path: Path) -> dict[str, Any]:
    """Parse ARXML subset → interfaces / data_types / candidates."""
    tree = ET.parse(path)
    root = tree.getroot()

    interfaces: list[str] = []
    data_types: list[str] = []

    for elem in root.iter():
        local = _local(elem.tag)
        name = _find_short_name(elem)
        if not name:
            continue
        if local in {
            "SENDER-RECEIVER-INTERFACE",
            "CLIENT-SERVER-INTERFACE",
            "SERVICE-INTERFACE",
        }:
            interfaces.append(name)
        elif local in {
            "IMPLEMENTATION-DATA-TYPE",
            "APPLICATION-PRIMITIVE-DATA-TYPE",
            "APPLICATION-RECORD-DATA-TYPE",
            "STD-CPP-IMPLEMENTATION-DATA-TYPE",
        }:
            data_types.append(name)

    # de-dup preserve order
    def _uniq(xs: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    interfaces = _uniq(interfaces)
    data_types = _uniq(data_types)
    candidates = _uniq(data_types + interfaces)

    types = [
        {"id": f"types.{n}", "kind": "struct", "fields": [], "source": "arxml"}
        for n in data_types
    ]
    services = [
        {
            "id": f"services.semantic.{n}",
            "type_ref": f"types.{n}" if n in data_types else f"types.{n}",
            "kind": "event",
            "source": "arxml",
        }
        for n in interfaces
    ]

    return {
        "file": str(path),
        "interfaces": interfaces,
        "data_types": data_types,
        "candidates": candidates,
        "types": types,
        "services": services,
        "imports_meta": {
            "sources": [
                {
                    "file": path.name,
                    "import": "gf-codegen import arxml",
                    "kind": "arxml_subset",
                }
            ]
        },
    }


def to_wiring_fragment(parsed: dict[str, Any]) -> dict[str, Any]:
    """Optional overlay fragment for docs / merge hints."""
    return {
        "arxml_import": {
            "interfaces": parsed.get("interfaces") or [],
            "data_types": parsed.get("data_types") or [],
            "candidates": parsed.get("candidates") or [],
        },
        "imports_meta": parsed.get("imports_meta") or {},
    }
