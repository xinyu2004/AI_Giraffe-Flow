"""gf-codegen generate — types + Proxy/Skeleton headers (P0 B4)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def _iter_events(sor: dict[str, Any]) -> list[tuple[str, str, str, list[Any]]]:
    type_by_id: dict[str, dict[str, Any]] = {}
    for t in sor.get("types") or []:
        if isinstance(t, dict) and t.get("id"):
            type_by_id[str(t["id"])] = t
    events: list[tuple[str, str, str, list[Any]]] = []
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
        short = sid.split(".")[-1]
        tdef = type_by_id.get(type_ref) or {}
        events.append((short, type_name, _snake(type_name), list(tdef.get("fields") or [])))
    return events

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


_SCALAR_PRINTF: dict[str, tuple[str, str]] = {
    # sor type → (printf cast expr template with {v}, json-ish)
    "uint8": ("static_cast<unsigned>({v})", "%u"),
    "uint16": ("static_cast<unsigned>({v})", "%u"),
    "uint32": ("static_cast<unsigned long>({v})", "%lu"),
    "uint64": ("static_cast<unsigned long long>({v})", "%llu"),
    "int8": ("static_cast<int>({v})", "%d"),
    "int16": ("static_cast<int>({v})", "%d"),
    "int32": ("static_cast<long>({v})", "%ld"),
    "int64": ("static_cast<long long>({v})", "%lld"),
    "float32": ("static_cast<double>({v})", "%.6g"),
    "float64": ("static_cast<double>({v})", "%.6g"),
    "bool": ("static_cast<int>({v} ? 1 : 0)", "%d"),
}

# Fat vendor blobs (e.g. FCM gold Out) must NOT dump every nested field into
# the live NDJSON pipe — that stalls tap→Foxglove (camera still works via shm).
_OBS_TAP_FIELD_ALLOW: dict[str, frozenset[str]] = {
    "Perception_MESSAGE_Out_St": frozenset(
        {
            "Perception_DYN_OBJ_Out",
            "Perception_LH_Out",
            "Perception_LA_Out",
            "Perception_DSTSR_Out",
            "Perception_STATIC_OBJ_Out",
        }
    ),
    "Perception_Dyn_OBJ_Out_St": frozenset(
        {
            "m_frame_id",
            "m_time_stamp",
            "m_OBJ_VD_Count",
            "m_OBJ_Ped_Count",
            "m_OBJ_VD_CIPV_ID",
            "m_Obj_item",
        }
    ),
    "Dyn_OBJ_Item_St": frozenset(
        {
            "m_OBJ_ID",
            "m_OBJ_Object_Class",
            "m_OBJ_Long_Distance",
            "m_OBJ_Lat_Distance",
            "m_OBJ_Relative_Long_Velocity",
            "m_OBJ_Relative_Lat_Velocity",
            "m_OBJ_Lane_Assignment",
            "m_OBJ_Width",
            "m_OBJ_Length",
            "m_OBJ_Heading",
        }
    ),
    "Perception_LH_Out_St": frozenset(
        {
            "m_frame_id",
            "m_time_stamp",
            "m_hostline_num",
            "m_LH_Estimated_Width",
            "m_hostline",
        }
    ),
    "HostLine_St": frozenset(
        {
            "m_LH_Side",
            "m_LH_Confidence",
            "m_LH_Availability_State",
            "m_LH_First_VR_Start",
            "m_LH_First_VR_End",
            "m_LH_Line_First_C0",
            "m_LH_Line_First_C1",
            "m_LH_Line_First_C2",
            "m_LH_Line_First_C3",
            "m_LH_Lanemark_Type",
        }
    ),
    "Perception_LA_Out_St": frozenset(
        {
            "m_frame_id",
            "m_time_stamp",
            "m_adj_line_num",
            "m_adj_line",
        }
    ),
    "LA_Line_St": frozenset(
        {
            "m_LA_Confidence",
            "m_LA_Availability_State",
            "m_LA_Line_Side",
            "m_LA_View_Range_Start",
            "m_LA_View_Range_End",
            "m_LA_Line_C0",
            "m_LA_Line_C1",
            "m_LA_Line_C2",
            "m_LA_Line_C3",
            "m_LA_Lanemark_Type",
        }
    ),
    # Slim TSR + static for Live plots (red-light / stop-line vs turtle speed).
    # LRE still omitted. Full gold Out stays on iceoryx.
    # ME: plot by m_DSTSR_ID / Relevancy / Sign_Name scan — never Sign_Name[0] alone.
    # Process curves prefer Trajectory.D_see_m / s_stop_m / cipv_* / v_sign_*.
    # cipv_long_m / cipv_rel_v (semantic scalars), not Obj[0].
    "Perception_DSTSR_Out_St": frozenset(
        {
            "m_frame_id",
            "m_time_stamp",
            "m_tsr_num",
            "m_TSR_Item",
        }
    ),
    "TSR_Item_St": frozenset(
        {
            "m_DSTSR_ID",
            "m_DSTSR_Sign_Name",
            "m_DSTSR_Sign_Long_Distance",
            "m_DSTSR_Sign_Lat_Distance",
            "m_DSTSR_Relevancy",
            "m_DSTSR_Confidence",
        }
    ),
    "Perception_Static_Obj_Out_St": frozenset(
        {
            "m_frame_id",
            "m_time_stamp",
            "m_Static_OBJ_Count",
            "STAT_OBJ_Static_CIPV_ID",
            "m_Obj_item",
        }
    ),
    "Static_OBJ_Item_St": frozenset(
        {
            "m_OBJ_ID",
            "m_OBJ_Object_Class",
            "m_OBJ_Long_Distance",
            "m_OBJ_Lat_Distance",
            "m_OBJ_Length",
            "m_OBJ_Heading",
            "m_OBJ_Lane_Assignment",
        }
    ),
}


def _filter_fields_for_obs(
    type_leaf: str | None, fields: list[Any]
) -> list[Any]:
    if not type_leaf:
        return fields
    allow = _OBS_TAP_FIELD_ALLOW.get(type_leaf)
    if allow is None:
        return fields
    out: list[Any] = []
    for f in fields:
        if isinstance(f, dict) and str(f.get("name") or "") in allow:
            out.append(f)
    return out


def _emit_fields_printf(
    lines: list[str],
    fields: list[Any],
    type_by_id: dict[str, dict[str, Any]],
    *,
    expr_prefix: str,
    depth: int,
    first_flag_name: str,
    owner_type_leaf: str | None = None,
) -> None:
    """Append printf statements for scalar / nested / array fields into ``lines``."""
    if depth > 3:
        return
    fields = _filter_fields_for_obs(owner_type_leaf, fields)
    for field in fields:
        if not isinstance(field, dict):
            continue
        fname = str(field.get("name") or "")
        ftype = str(field.get("type") or "")
        asize = field.get("array_size")
        if not fname:
            continue
        expr = f"{expr_prefix}.{fname}" if expr_prefix else fname
        nested_leaf = ftype.split(".")[-1] if ftype.startswith("types.") else None
        # Nested struct (no array)
        if asize is None and ftype.startswith("types."):
            nested = type_by_id.get(ftype) or {}
            nested_fields = list(nested.get("fields") or [])
            if not nested_fields:
                continue
            lines.append("  {")
            lines.append(f'    if (!{first_flag_name}) std::printf(", ");')
            lines.append(f'    std::printf("\\"{fname}\\":{{");')
            lines.append("    bool nest_first = true;")
            _emit_fields_printf(
                lines,
                nested_fields,
                type_by_id,
                expr_prefix=expr,
                depth=depth + 1,
                first_flag_name="nest_first",
                owner_type_leaf=nested_leaf,
            )
            lines.append('    std::printf("}");')
            lines.append(f"    {first_flag_name} = false;")
            lines.append("  }")
            continue
        # Array of nested structs — dyn objects: up to 8 (BEV ID palette); else cap 2
        if asize is not None and ftype.startswith("types."):
            nested = type_by_id.get(ftype) or {}
            nested_fields = list(nested.get("fields") or [])
            if not nested_fields:
                continue
            if nested_leaf == "Dyn_OBJ_Item_St":
                nmax = min(int(asize), 8)
            elif nested_leaf == "LA_Line_St":
                nmax = min(int(asize), 4)
            elif nested_leaf == "HostLine_St":
                nmax = min(int(asize), 2)
            elif nested_leaf in ("TSR_Item_St", "Static_OBJ_Item_St"):
                nmax = min(int(asize), 6)
            else:
                nmax = min(int(asize), 2)
            lines.append("  {")
            lines.append(f'    if (!{first_flag_name}) std::printf(", ");')
            lines.append(f'    std::printf("\\"{fname}\\":[");')
            if nested_leaf == "Dyn_OBJ_Item_St":
                parent = expr.rsplit(".", 1)[0]
                lines.append(
                    f"    const int n = std::min({nmax}, "
                    f"static_cast<int>({parent}.m_OBJ_VD_Count));"
                )
            elif nested_leaf == "LA_Line_St":
                parent = expr.rsplit(".", 1)[0]
                lines.append(
                    f"    const int n = std::min({nmax}, "
                    f"static_cast<int>({parent}.m_adj_line_num));"
                )
            elif nested_leaf == "TSR_Item_St":
                parent = expr.rsplit(".", 1)[0]
                lines.append(
                    f"    const int n = std::min({nmax}, "
                    f"static_cast<int>({parent}.m_tsr_num));"
                )
            elif nested_leaf == "Static_OBJ_Item_St":
                parent = expr.rsplit(".", 1)[0]
                lines.append(
                    f"    const int n = std::min({nmax}, "
                    f"static_cast<int>({parent}.m_Static_OBJ_Count));"
                )
            else:
                lines.append(f"    const int n = {nmax};")
            lines.append("    for (int i = 0; i < n; ++i) {")
            lines.append('      if (i) std::printf(",");')
            lines.append('      std::printf("{");')
            lines.append("      bool item_first = true;")
            _emit_fields_printf(
                lines,
                nested_fields,
                type_by_id,
                expr_prefix=f"{expr}[i]",
                depth=depth + 1,
                first_flag_name="item_first",
                owner_type_leaf=nested_leaf,
            )
            lines.append('      std::printf("}");')
            lines.append("    }")
            lines.append('    std::printf("]");')
            lines.append(f"    {first_flag_name} = false;")
            lines.append("  }")
            continue
        # Scalar array
        if asize is not None:
            if ftype not in _SCALAR_PRINTF:
                continue
            cast, fmt = _SCALAR_PRINTF[ftype]
            lines.append("  {")
            lines.append(f'    if (!{first_flag_name}) std::printf(", ");')
            lines.append(
                f"    int n = {int(asize)} < kMaxArrayExport ? {int(asize)} : kMaxArrayExport;"
            )
            lines.append(f'    std::printf("\\"{fname}\\":[");')
            lines.append("    for (int i = 0; i < n; ++i) {")
            lines.append('      if (i) std::printf(",");')
            lines.append(f'      std::printf("{fmt}", {cast.format(v=f"{expr}[i]")});')
            lines.append("    }")
            lines.append('    std::printf("]");')
            lines.append(f"    {first_flag_name} = false;")
            lines.append("  }")
            continue
        # Scalar
        if ftype not in _SCALAR_PRINTF:
            continue
        cast, fmt = _SCALAR_PRINTF[ftype]
        lines.append("  {")
        lines.append(f'    if (!{first_flag_name}) std::printf(", ");')
        lines.append(
            f'    std::printf("\\"{fname}\\":{fmt}", {cast.format(v=expr)});'
        )
        lines.append(f"    {first_flag_name} = false;")
        lines.append("  }")


def _write_obs_tap(sor: dict[str, Any], out_dir: Path) -> int:
    """Generate src/obs_tap_main.cpp — subscribe all SOR event services → NDJSON.

    Runtime filter: GF_OBS_LIVE_SERVICES (comma-separated short names; empty = all).
    Hand-maintained tools/gmt_board/iox_obs_tap/src/main.cpp is fallback only.
    Nested structs (e.g. FCM gold Out) are flattened into JSON objects/arrays.
    """
    type_by_id: dict[str, dict[str, Any]] = {}
    for t in sor.get("types") or []:
        if isinstance(t, dict) and t.get("id"):
            type_by_id[str(t["id"])] = t

    events: list[tuple[str, str, str, list[Any]]] = []
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
        short = sid.split(".")[-1]
        tdef = type_by_id.get(type_ref) or {}
        events.append((short, type_name, _snake(type_name), list(tdef.get("fields") or [])))

    src_dir = out_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    out_path = src_dir / "obs_tap_main.cpp"

    lines: list[str] = [
        "// Generated by gf-codegen generate — do not edit by hand",
        "// iceoryx observability tap: SOR event services → NDJSON stdout",
        "// Env GF_OBS_LIVE_SERVICES: comma-separated short names (empty = all generated)",
        "",
        '#include "gf_ara/com/binding/iceoryx/runtime.hpp"',
    ]
    for _s, _tn, hdr, _f in events:
        lines.append(f'#include "gf_gen/proxy/{hdr}_proxy.hpp"')
    lines += [
        "",
        '#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"',
        "",
        "#include <chrono>",
        "#include <cstdint>",
        "#include <cstdio>",
        "#include <cstdlib>",
        "#include <algorithm>",
        "#include <iostream>",
        "#include <set>",
        "#include <string>",
        "#include <thread>",
        "",
        "namespace {",
        "",
        "constexpr int kMaxArrayExport = 16;",
        "",
        "std::uint64_t now_ns() {",
        "  // Wall clock — Foxglove timeline; steady_clock lands near 1970 and looks empty.",
        "  return static_cast<std::uint64_t>(",
        "      std::chrono::duration_cast<std::chrono::nanoseconds>(",
        "          std::chrono::system_clock::now().time_since_epoch())",
        "          .count());",
        "}",
        "",
        "std::set<std::string> parse_allowlist() {",
        '  const char* env = std::getenv("GF_OBS_LIVE_SERVICES");',
        "  std::set<std::string> out;",
        "  if (!env || !*env) {",
        "    return out;",
        "  }",
        "  std::string raw = env;",
        "  std::string cur;",
        "  auto flush = [&]() {",
        "    if (cur.empty()) return;",
        '    const std::string pref = "services.semantic.";',
        "    if (cur.rfind(pref, 0) == 0) cur = cur.substr(pref.size());",
        "    out.insert(cur);",
        "    cur.clear();",
        "  };",
        "  for (char c : raw) {",
        "    if (c == ',' || c == ';' || c == ' ') flush();",
        "    else cur.push_back(c);",
        "  }",
        "  flush();",
        "  return out;",
        "}",
        "",
        "bool want(const std::set<std::string>& allow, const char* name) {",
        "  return allow.empty() || allow.count(name) > 0;",
        "}",
        "",
    ]

    for short, type_name, _hdr, fields in events:
        lines.append(f"void emit_{_snake(type_name)}(const gf_gen::{type_name}& s) {{")
        has_ts = any(isinstance(f, dict) and f.get("name") == "timestamp_ns" for f in fields)
        if has_ts:
            lines.append(
                "  const std::uint64_t t_ns = s.timestamp_ns ? s.timestamp_ns : now_ns();"
            )
        else:
            lines.append("  const std::uint64_t t_ns = now_ns();")

        lines.append(
            f'  std::printf("{{\\"t_ns\\":%llu,\\"topic\\":\\"/gf/{short}\\",\\"data\\":{{",'
        )
        lines.append("             static_cast<unsigned long long>(t_ns));")
        lines.append("  bool first = true;")
        _emit_fields_printf(
            lines,
            fields,
            type_by_id,
            expr_prefix="s",
            depth=0,
            first_flag_name="first",
            owner_type_leaf=type_name,
        )
        lines += [
            '  std::printf("}}\\n");',
            "  std::fflush(stdout);",
            "}",
            "",
        ]

    lines += ["}  // namespace", "", "int main() {"]
    if not events:
        lines += [
            '  std::cerr << "gf-iox-obs-tap: no event services in SOR\\n";',
            "  return EXIT_FAILURE;",
            "}",
            "",
        ]
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return 0

    lines += [
        "  const auto allow = parse_allowlist();",
        "  bool any = false;",
    ]
    for short, _tn, _hdr, _f in events:
        sn = _snake(short)
        lines.append(f'  const bool want_{sn} = want(allow, "{short}");')
        lines.append(f"  any = any || want_{sn};")
    lines += [
        "  if (!any) {",
        '    std::cerr << "gf-iox-obs-tap: GF_OBS_LIVE_SERVICES matched nothing\\n";',
        "    return EXIT_FAILURE;",
        "  }",
        "",
        '  gf_ara::com::binding::iceoryx::InitRuntime("gf-iox-obs-tap");',
        "",
    ]
    for short, type_name, _hdr, _f in events:
        lines.append(f"  gf_gen::{type_name}Proxy sub_{_snake(short)}{{}};")
    lines += [
        '  std::cerr << "gf-iox-obs-tap: codegen start → NDJSON stdout\\n";',
        "",
        "  while (!iox::posix::hasTerminationRequested()) {",
    ]
    for short, type_name, _hdr, _f in events:
        sn = _snake(short)
        lines += [
            f"    if (want_{sn}) {{",
            f"      auto taken = sub_{sn}.Take();",
            "      if (taken && taken.Value().has_value()) {",
            f"        emit_{_snake(type_name)}(*taken.Value());",
            "      }",
            "    }",
        ]
    lines += [
        "    std::this_thread::sleep_for(std::chrono::milliseconds(10));",
        "  }",
        "  return 0;",
        "}",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return len(events)


def _write_obs_foxglove(sor: dict[str, Any], out_dir: Path) -> int:
    """Generate src/obs_foxglove_main.cpp — iceoryx subscribe → Foxglove WS :8765."""
    type_by_id: dict[str, dict[str, Any]] = {}
    for t in sor.get("types") or []:
        if isinstance(t, dict) and t.get("id"):
            type_by_id[str(t["id"])] = t
    events = _iter_events(sor)

    src_dir = out_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    out_path = src_dir / "obs_foxglove_main.cpp"

    lines: list[str] = [
        "// Generated by gf-codegen generate — do not edit by hand",
        "// iceoryx → Foxglove WebSocket (gf_foxglove_ws). Env GF_WS_PORT / GF_OBS_LIVE_SERVICES.",
        "",
        '#include "gf_ara/com/binding/iceoryx/runtime.hpp"',
        '#include "gf_foxglove/bev_compose.hpp"',
        '#include "gf_foxglove/bev_ingest.hpp"',
        '#include "gf_foxglove/camera.hpp"',
        '#include "gf_foxglove/ws_hub.hpp"',
    ]
    for _s, _tn, hdr, _f in events:
        lines.append(f'#include "gf_gen/proxy/{hdr}_proxy.hpp"')
    lines += [
        "",
        '#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"',
        "",
        "#include <chrono>",
        "#include <cstdint>",
        "#include <cstdio>",
        "#include <cstdlib>",
        "#include <algorithm>",
        "#include <iostream>",
        "#include <set>",
        "#include <string>",
        "#include <thread>",
        "#include <vector>",
        "",
        "namespace {",
        "",
        "constexpr int kMaxArrayExport = 16;",
        "",
        "std::uint64_t now_ns() {",
        "  return static_cast<std::uint64_t>(",
        "      std::chrono::duration_cast<std::chrono::nanoseconds>(",
        "          std::chrono::system_clock::now().time_since_epoch())",
        "          .count());",
        "}",
        "",
        "int env_int(const char* k, int def) {",
        "  const char* v = std::getenv(k);",
        "  if (!v || !*v) return def;",
        "  return std::atoi(v);",
        "}",
        "",
        "bool env_on(const char* k, bool def) {",
        "  const char* v = std::getenv(k);",
        "  if (!v || !*v) return def;",
        "  return !(v[0] == '0' && v[1] == '\\0');",
        "}",
        "",
        "std::set<std::string> parse_allowlist() {",
        '  const char* env = std::getenv("GF_OBS_LIVE_SERVICES");',
        "  std::set<std::string> out;",
        "  if (!env || !*env) return out;",
        "  std::string raw = env;",
        "  std::string cur;",
        "  auto flush = [&]() {",
        "    if (cur.empty()) return;",
        '    const std::string pref = "services.semantic.";',
        "    if (cur.rfind(pref, 0) == 0) cur = cur.substr(pref.size());",
        "    out.insert(cur);",
        "    cur.clear();",
        "  };",
        "  for (char c : raw) {",
        "    if (c == ',' || c == ';' || c == ' ') flush();",
        "    else cur.push_back(c);",
        "  }",
        "  flush();",
        "  return out;",
        "}",
        "",
        "bool want(const std::set<std::string>& allow, const char* name) {",
        "  return allow.empty() || allow.count(name) > 0;",
        "}",
        "",
        "std::string capture_json(void (*fn)(FILE*, const void*), const void* sample) {",
        "  char* ptr = nullptr;",
        "  std::size_t sz = 0;",
        "  FILE* fp = open_memstream(&ptr, &sz);",
        "  if (!fp) return \"{}\";",
        "  fn(fp, sample);",
        "  std::fclose(fp);",
        "  std::string out(ptr ? ptr : \"\", sz);",
        "  std::free(ptr);",
        "  return out;",
        "}",
        "",
    ]

    for short, type_name, _hdr, fields in events:
        fn = f"write_{_snake(type_name)}"
        lines.append(f"void {fn}(FILE* fp, const void* sample) {{")
        lines.append(f"  const auto& s = *static_cast<const gf_gen::{type_name}*>(sample);")
        lines.append('  std::fprintf(fp, "{");')
        lines.append("  bool first = true;")
        field_lines: list[str] = []
        _emit_fields_printf(
            field_lines,
            fields,
            type_by_id,
            expr_prefix="s",
            depth=0,
            first_flag_name="first",
            owner_type_leaf=type_name,
        )
        for ln in field_lines:
            lines.append(ln.replace("std::printf(", "std::fprintf(fp, "))
        lines += [
            '  std::fprintf(fp, "}");',
            "}",
            "",
        ]

    lines += ["}  // namespace", "", "int main() {"]
    if not events:
        lines += [
            '  std::cerr << "gf-foxglove-ws: no event services in SOR\\n";',
            "  return EXIT_FAILURE;",
            "}",
            "",
        ]
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return 0

    lines += [
        "  const auto allow = parse_allowlist();",
        "  bool any = false;",
    ]
    for short, _tn, _hdr, _f in events:
        sn = _snake(short)
        lines.append(f'  const bool want_{sn} = want(allow, "{short}");')
        lines.append(f"  any = any || want_{sn};")
    lines += [
        "  if (!any) {",
        '    std::cerr << "gf-foxglove-ws: GF_OBS_LIVE_SERVICES matched nothing\\n";',
        "    return EXIT_FAILURE;",
        "  }",
        "",
        '  const char* host = std::getenv("GF_WS_HOST");',
        '  if (!host || !*host) host = "0.0.0.0";',
        "  const std::uint16_t port = static_cast<std::uint16_t>(env_int(\"GF_WS_PORT\", 8765));",
        '  const bool synth_bev = env_on("GF_SYNTH_BEV", true);',
        '  const bool cam_on = env_on("GF_CAMERA_PUBLISH", true);',
        "",
        "  gf_foxglove::WsHub hub;",
        "  if (!hub.listen(host, port)) return EXIT_FAILURE;",
        "",
        "  std::vector<std::string> topics;",
    ]
    for short, _tn, _hdr, _f in events:
        sn = _snake(short)
        lines.append(f'  if (want_{sn}) topics.push_back("/gf/{short}");')
    lines += [
        '  if (synth_bev) topics.push_back("/gf/driving/bev/compressed");',
        '  if (cam_on) topics.push_back("/gf/driving/camera/front/compressed");',
        "  hub.advertise(topics);",
        "",
        '  gf_ara::com::binding::iceoryx::InitRuntime("gf-foxglove-ws");',
        "",
    ]
    for short, type_name, _hdr, _f in events:
        lines.append(f"  gf_gen::{type_name}Proxy sub_{_snake(short)}{{}};")
    lines += [
        "",
        "  gf_foxglove::LiveBevState bev;",
        '  const char* slot = std::getenv("GF_CAMERA_SLOT");',
        '  const char* frame = std::getenv("GF_CAMERA_FRAME");',
        '  gf_foxglove::CameraPub cam(slot && *slot ? slot : "gf.channel.front",',
        "                             frame && *frame ? frame : \"\");",
        '  std::cerr << "gf-foxglove-ws: codegen start topics=" << topics.size() << "\\n";',
        "  auto last_bev = std::chrono::steady_clock::now();",
        "",
        "  while (!iox::posix::hasTerminationRequested()) {",
        "    hub.poll();",
    ]
    for short, type_name, _hdr, _f in events:
        sn = _snake(short)
        write_fn = f"write_{_snake(type_name)}"
        lines += [
            f"    if (want_{sn}) {{",
            f"      auto taken = sub_{sn}.Take();",
            "      if (taken && taken.Value().has_value()) {",
            f"        const auto& s = *taken.Value();",
            f"        const std::string js = capture_json({write_fn}, &s);",
        ]
        has_ts = any(isinstance(f, dict) and f.get("name") == "timestamp_ns" for f in _f)
        if has_ts:
            lines.append(
                "        const std::uint64_t t_ns = s.timestamp_ns ? s.timestamp_ns : now_ns();"
            )
        else:
            lines.append("        const std::uint64_t t_ns = now_ns();")
        lines += [
            f'        hub.publish_json("/gf/{short}", t_ns, js);',
            f'        gf_foxglove::apply_sample(bev, "{short}", &s);',
            "      }",
            "    }",
        ]
    lines += [
        "    const auto now = std::chrono::steady_clock::now();",
        "    if (synth_bev && now - last_bev >= std::chrono::milliseconds(33)) {",
        "      last_bev = now;",
        "      const auto png = gf_foxglove::render_ego_bev_png(bev);",
        "      const std::uint64_t t = bev.t_ns ? bev.t_ns : now_ns();",
        '      hub.publish_json("/gf/driving/bev/compressed", t,',
        '                       gf_foxglove::compressed_image_json(t, png, "front"));',
        "    }",
        "    if (cam_on) {",
        "      std::uint64_t t = 0;",
        "      const std::string img = cam.poll(&t);",
        '      if (!img.empty()) hub.publish_json("/gf/driving/camera/front/compressed", t, img);',
        "    }",
        "    std::this_thread::sleep_for(std::chrono::milliseconds(10));",
        "  }",
        "  return 0;",
        "}",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return len(events)


def generate(sor_path: Path, out_dir: Path) -> int:
    with sor_path.open(encoding="utf-8") as f:
        sor = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    n_types = _write_types(sor, out_dir)
    n_proxy, n_skel = _write_proxies_skeletons(sor, out_dir)
    n_tap = _write_obs_tap(sor, out_dir)
    n_fox = _write_obs_foxglove(sor, out_dir)

    print(
        f"generate wrote {n_types} type(s), {n_skel} skeleton(s), {n_proxy} proxy(ies), "
        f"{n_tap} obs-tap / {n_fox} foxglove service(s) under {out_dir}/"
    )
    if n_types == 0:
        print("warning: no struct types in SOR", file=sys.stderr)
    if n_skel == 0:
        print("warning: no event services → no Proxy/Skeleton", file=sys.stderr)
    return 0
