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


def _write_obs_tap(sor: dict[str, Any], out_dir: Path) -> int:
    """Generate src/obs_tap_main.cpp — subscribe all SOR event services → NDJSON.

    Runtime filter: GF_OBS_LIVE_SERVICES (comma-separated short names; empty = all).
    Hand-maintained apps/tools/iox_obs_tap/src/main.cpp is fallback only.
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
        "  return static_cast<std::uint64_t>(",
        "      std::chrono::duration_cast<std::chrono::nanoseconds>(",
        "          std::chrono::steady_clock::now().time_since_epoch())",
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

        count_field = None
        for f in fields:
            if isinstance(f, dict) and str(f.get("name") or "") in ("point_count", "count"):
                count_field = str(f["name"])
                break

        lines.append(
            f'  std::printf("{{\\"t_ns\\":%llu,\\"topic\\":\\"/gf/{short}\\",\\"data\\":{{",'
        )
        lines.append("             static_cast<unsigned long long>(t_ns));")

        first = True
        for field in fields:
            if not isinstance(field, dict):
                continue
            fname = str(field.get("name") or "")
            ftype = str(field.get("type") or "")
            asize = field.get("array_size")
            if not fname or ftype.startswith("types."):
                continue
            sep = "" if first else ", "
            if asize is not None:
                if ftype not in _SCALAR_PRINTF:
                    continue
                cast, fmt = _SCALAR_PRINTF[ftype]
                lines.append("  {")
                if count_field:
                    lines.append(f"    int n = static_cast<int>(s.{count_field});")
                    lines.append("    if (n < 0) n = 0;")
                    lines.append(f"    if (n > {int(asize)}) n = {int(asize)};")
                    lines.append("    if (n > kMaxArrayExport) n = kMaxArrayExport;")
                else:
                    lines.append(
                        f"    int n = {int(asize)} < kMaxArrayExport ? {int(asize)} : kMaxArrayExport;"
                    )
                lines.append(f'    std::printf("{sep}\\"{fname}\\":[");')
                lines.append("    for (int i = 0; i < n; ++i) {")
                lines.append('      if (i) std::printf(",");')
                lines.append(f'      std::printf("{fmt}", {cast.format(v=f"s.{fname}[i]")});')
                lines.append("    }")
                lines.append('    std::printf("]");')
                lines.append("  }")
                first = False
                continue
            if ftype not in _SCALAR_PRINTF:
                continue
            cast, fmt = _SCALAR_PRINTF[ftype]
            lines.append(
                f'  std::printf("{sep}\\"{fname}\\":{fmt}", {cast.format(v=f"s.{fname}")});'
            )
            first = False

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



def generate(sor_path: Path, out_dir: Path) -> int:
    with sor_path.open(encoding="utf-8") as f:
        sor = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    n_types = _write_types(sor, out_dir)
    n_proxy, n_skel = _write_proxies_skeletons(sor, out_dir)
    n_tap = _write_obs_tap(sor, out_dir)

    print(
        f"generate wrote {n_types} type(s), {n_skel} skeleton(s), {n_proxy} proxy(ies), "
        f"{n_tap} obs-tap service(s) under {out_dir}/"
    )
    if n_types == 0:
        print("warning: no struct types in SOR", file=sys.stderr)
    if n_skel == 0:
        print("warning: no event services → no Proxy/Skeleton", file=sys.stderr)
    return 0
