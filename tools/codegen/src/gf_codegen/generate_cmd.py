"""gf-codegen generate — types + Proxy/Skeleton headers (P0 B4)."""

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


def _type_includes(fields: list[Any]) -> list[str]:
    incs: list[str] = []
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            continue
        t = str(field.get("type", ""))
        if t.startswith("types."):
            leaf = t.split(".")[-1]
            key = _snake(leaf)
            if key not in seen:
                seen.add(key)
                incs.append(f'#include "gf_gen/types/{key}.hpp"')
    return incs


def _write_types(sor: dict[str, Any], out_dir: Path) -> int:
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
        fields = t.get("fields") or []
        lines = ["#pragma once", "", "#include <cstdint>", ""]
        lines.extend(_type_includes(fields))
        if _type_includes(fields):
            lines.append("")
        lines += ["namespace gf_gen {", "", f"struct {name} {{"]
        for field in fields:
            if not isinstance(field, dict):
                continue
            ft = _cxx_type(str(field.get("type", "uint8_t")))
            fn = field.get("name", "field")
            if "array_size" in field:
                lines.append(f"  {ft} {fn}[{field['array_size']}];")
            else:
                lines.append(f"  {ft} {fn};")
        lines += ["};", "", "}  // namespace gf_gen", ""]
        (types_dir / f"{_snake(name)}.hpp").write_text("\n".join(lines), encoding="utf-8")
        count += 1
    return count


def _service_parts(service_id: str) -> tuple[str, str]:
    """services.semantic.UssZones → (semantic.UssZones, UssZones)."""
    sid = service_id
    if sid.startswith("services."):
        sid = sid[len("services.") :]
    event = sid.split(".")[-1]
    return sid, event


def _write_proxies_skeletons(sor: dict[str, Any], out_dir: Path) -> tuple[int, int]:
    proxy_dir = out_dir / "include" / "gf_gen" / "proxy"
    skel_dir = out_dir / "include" / "gf_gen" / "skeleton"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    skel_dir.mkdir(parents=True, exist_ok=True)

    proxies = 0
    skeletons = 0
    for svc in sor.get("services") or []:
        if not isinstance(svc, dict):
            continue
        if str(svc.get("kind", "event")).lower() != "event":
            continue
        sid = str(svc.get("id") or "")
        type_ref = str(svc.get("type_ref") or "")
        if not sid or not type_ref.startswith("types."):
            continue
        type_name = type_ref.split(".")[-1]
        type_hdr = _snake(type_name)
        service_str, event_str = _service_parts(sid)
        class_base = type_name  # UssZones

        # Skeleton = provider (publish)
        skel_lines = [
            "#pragma once",
            "",
            f'#include "gf_gen/types/{type_hdr}.hpp"',
            '#include "gf_ara/com/binding/iceoryx/event.hpp"',
            '#include "gf_ara/com/service_path.hpp"',
            "",
            "#include <string>",
            "",
            "namespace gf_gen {",
            "",
            f"class {class_base}Skeleton {{",
            " public:",
            f'  static constexpr const char* kService = "{service_str}";',
            f'  static constexpr const char* kEvent = "{event_str}";',
            "",
            "  explicit " + class_base + 'Skeleton(std::string instance = "1")',
            "      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}",
            "",
            f"  gf_ara::core::Result<void> Send(const {class_base}& sample) {{",
            "    return pub_.Publish(sample);",
            "  }",
            "",
            " private:",
            f"  gf_ara::com::binding::iceoryx::EventPublisher<{class_base}> pub_;",
            "};",
            "",
            "}  // namespace gf_gen",
            "",
        ]
        (skel_dir / f"{_snake(class_base)}_skeleton.hpp").write_text(
            "\n".join(skel_lines), encoding="utf-8"
        )
        skeletons += 1

        # Proxy = consumer (subscribe / take)
        proxy_lines = [
            "#pragma once",
            "",
            f'#include "gf_gen/types/{type_hdr}.hpp"',
            '#include "gf_ara/com/binding/iceoryx/event.hpp"',
            '#include "gf_ara/com/service_path.hpp"',
            "",
            "#include <optional>",
            "#include <string>",
            "",
            "namespace gf_gen {",
            "",
            f"class {class_base}Proxy {{",
            " public:",
            f'  static constexpr const char* kService = "{service_str}";',
            f'  static constexpr const char* kEvent = "{event_str}";',
            "",
            "  explicit " + class_base + 'Proxy(std::string instance = "1")',
            "      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}",
            "",
            f"  gf_ara::core::Result<std::optional<{class_base}>> Take() {{",
            "    return sub_.Take();",
            "  }",
            "",
            " private:",
            f"  gf_ara::com::binding::iceoryx::EventSubscriber<{class_base}> sub_;",
            "};",
            "",
            "}  // namespace gf_gen",
            "",
        ]
        (proxy_dir / f"{_snake(class_base)}_proxy.hpp").write_text(
            "\n".join(proxy_lines), encoding="utf-8"
        )
        proxies += 1

    return proxies, skeletons


def generate(sor_path: Path, out_dir: Path) -> int:
    with sor_path.open(encoding="utf-8") as f:
        sor = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    n_types = _write_types(sor, out_dir)
    n_proxy, n_skel = _write_proxies_skeletons(sor, out_dir)

    print(
        f"generate wrote {n_types} type(s), {n_skel} skeleton(s), {n_proxy} proxy(ies) under {out_dir}/include/gf_gen/"
    )
    if n_types == 0:
        print("warning: no struct types in SOR", file=sys.stderr)
    if n_skel == 0:
        print("warning: no event services → no Proxy/Skeleton", file=sys.stderr)
    return 0
