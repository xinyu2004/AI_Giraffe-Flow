"""gf-codegen generate — minimal C++ type headers (P0)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SOR_TO_CXX = {
    "uint8": "uint8_t",
    "uint16": "uint16_t",
    "uint32": "uint32_t",
    "uint64": "uint64_t",
    "int8": "int8_t",
    "int16": "int16_t",
    "int32": "int32_t",
    "int64": "int64_t",
    "float32": "float",
    "float64": "double",
    "bool": "bool",
}


def _cxx_type(t: str) -> str:
    if t.startswith("types."):
        return t.split(".")[-1]
    return _SOR_TO_CXX.get(t, t)


def _snake(name: str) -> str:
    name = name.split(".")[-1]
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def generate(sor_path: Path, out_dir: Path) -> int:
    with sor_path.open(encoding="utf-8") as f:
        sor = json.load(f)

    types_dir = out_dir / "include" / "gf_gen" / "types"
    types_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for t in sor.get("types") or []:
        if not isinstance(t, dict) or t.get("kind") != "struct":
            continue
        tid = t.get("id") or ""
        name = tid.split(".")[-1]
        if not name:
            continue
        lines = [
            "#pragma once",
            "",
            "#include <cstdint>",
            "",
            "namespace gf_gen {",
            "",
            f"struct {name} {{",
        ]
        for field in t.get("fields") or []:
            if not isinstance(field, dict):
                continue
            ft = _cxx_type(str(field.get("type", "uint8_t")))
            fn = field.get("name", "field")
            if "array_size" in field:
                lines.append(f"  {ft} {fn}[{field['array_size']}];")
            else:
                lines.append(f"  {ft} {fn};")
        lines += ["};", "", "}  // namespace gf_gen", ""]
        out_file = types_dir / f"{_snake(name)}.hpp"
        out_file.write_text("\n".join(lines), encoding="utf-8")
        count += 1

    print(f"generate wrote {count} type header(s) under {types_dir}")
    if count == 0:
        print("warning: no struct types in SOR", file=sys.stderr)
    return 0
