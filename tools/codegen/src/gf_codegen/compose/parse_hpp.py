"""Minimal C/C++ header parser for io_types / io_ports (no libclang)."""

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
    "boolean": "bool",
    # vendor demo aliases (FAPA/FCM headers)
    "uint8_demo": "uint8",
    "uint16_demo": "uint16",
    "uint32_demo": "uint32",
    "uint64_demo": "uint64",
    "float32_demo": "float32",
    "float64_demo": "float64",
    "boolean_demo": "bool",
    "real_T": "float64",
    "real32_T": "float32",
}

# 对接会上用的「粗端口」名（整包）；导入时可默认只勾这些
_FAT_PORT_EXACT = {
    "EgoMotion",
    "UssZones",
    "Trajectory",
    "FrontObjectList",
    "ApaStatus",
    "ApaSlotList",
    "FcmObjectList",
    "Perception_In_St",
    "Perception_Init_St",
    "Perception_MESSAGE_Out_St",
    "IPC_ADC_Perception_Out_St",
    "IPC_CanInfo_10ms_St",
    "IPC_CanInfo_20ms_St",
    "IPC_CanInfo_100ms_St",
    "VehicleBus",
}


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return text


def _map_type(cxx: str) -> str:
    cxx = cxx.strip()
    if cxx in _CXX_TO_SOR:
        return _CXX_TO_SOR[cxx]
    return cxx


def is_fat_port_name(name: str) -> bool:
    """True for meeting-level bundles; False for Item/line fragments."""
    if name in _FAT_PORT_EXACT:
        return True
    if re.search(r"Item|_Line_St$|HostLine|TSR_Item|FCF_VD|FCF_VRU|FCF_CV", name):
        return False
    if re.search(
        r"(Perception_.*_(In|Out)_St|Perception_MESSAGE_|IPC_CanInfo_|IPC_ADC_|"
        r"IPC_APA_.*Output|EgoMotion|UssZones|Trajectory|ObjectList|SlotList)",
        name,
    ):
        return True
    return False


def parse_hpp_file(path: Path) -> list[dict[str, Any]]:
    """Return list of {name, fields:[{name,type,array_size?}]}."""
    text = _strip_comments(path.read_text(encoding="utf-8"))
    # drop enum / enum class blocks (keep type names usable as opaque uint8 later)
    text = re.sub(r"enum\s+(?:class\s+)?\w+[^{]*\{[^}]*\}", ";", text, flags=re.S)

    structs: list[dict[str, Any]] = []
    seen: set[str] = set()

    # typedef struct [Tag] { ... } Name;
    for m in re.finditer(
        r"typedef\s+struct(?:\s+(\w+))?\s*\{([^}]*)\}\s*(\w+)\s*;",
        text,
        flags=re.S,
    ):
        tag, body, name = m.group(1), m.group(2), m.group(3)
        _append_struct(structs, seen, name or tag or "", body)

    # struct Name { ... };  (C++)
    for m in re.finditer(r"struct\s+(\w+)\s*\{([^}]*)\}", text, flags=re.S):
        name, body = m.group(1), m.group(2)
        _append_struct(structs, seen, name, body)

    return structs


def _append_struct(
    structs: list[dict[str, Any]],
    seen: set[str],
    name: str,
    body: str,
) -> None:
    if not name or name in seen:
        return
    seen.add(name)
    fields: list[dict[str, Any]] = []
    for line in body.split(";"):
        line = line.strip()
        if not line:
            continue
        # Type a, b, c;  → expand
        fm = re.match(
            r"^(?:const\s+)?(\w+(?:::\w+)*)\s+(.+)$",
            line,
        )
        if not fm:
            continue
        typ_raw = fm.group(1).split("::")[-1]
        rest = fm.group(2)
        for part in rest.split(","):
            part = part.strip()
            pm = re.match(r"^(\w+)(?:\s*\[\s*(\d+)\s*\])?\s*$", part)
            if not pm:
                continue
            fname, arr = pm.group(1), pm.group(2)
            entry: dict[str, Any] = {
                "name": fname,
                "type": _map_type(typ_raw),
            }
            if arr is not None:
                entry["array_size"] = int(arr)
            fields.append(entry)
    structs.append({"name": name, "fields": fields})


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
