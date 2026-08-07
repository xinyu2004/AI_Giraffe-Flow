"""Emit product em_launch + exec overlays: EM-managed optional dlt/RouDi; gateway forever."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

HOST_DLT = "host.dlt_daemon"
HOST_ROUDI = "host.iox_roudi"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _filter_depends(deps: list[Any], drop: set[str]) -> list[str]:
    out: list[str] = []
    for d in deps or []:
        s = str(d).strip()
        if s and s not in drop:
            out.append(s)
    return out


def build_product_em_tables(
    platform_dir: Path,
    *,
    k_dlt: bool,
    k_roudi: bool,
    gateway_forever: bool = True,
) -> dict[str, Any]:
    """Build frozen launch/exec tables (no I/O). Used by deploy_config.hpp + YAML dumps."""
    launch = _load_yaml(platform_dir / "em_launch.yaml")
    exec_doc = _load_yaml(platform_dir / "exec.yaml")

    drop: set[str] = set()
    if not k_dlt:
        drop.add(HOST_DLT)
    if not k_roudi:
        drop.add(HOST_ROUDI)

    # --- em_launch ---
    procs_in = launch.get("processes") if isinstance(launch.get("processes"), list) else []
    procs_out: list[dict[str, Any]] = []
    for p in procs_in:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if not name or name in drop:
            continue
        entry = dict(p)
        if gateway_forever and name == "adapter.vehicle_can_gateway":
            entry["args"] = ["0"]
        if name == HOST_ROUDI:
            entry["args"] = ["-c", "$GF_IOX_TOML"]
        procs_out.append(entry)

    names = {str(p.get("name")) for p in procs_out}
    if k_dlt and HOST_DLT not in names:
        procs_out.insert(
            0,
            {
                "name": HOST_DLT,
                "binary": "_dep-manifest/dlt-daemon/src/daemon/dlt-daemon",
                "args": [],
                "max_restarts": 3,
            },
        )
    if k_roudi and HOST_ROUDI not in names:
        idx = 1 if k_dlt else 0
        procs_out.insert(
            idx,
            {
                "name": HOST_ROUDI,
                "binary": "iox-roudi",
                "args": ["-c", "$GF_IOX_TOML"],
                "max_restarts": 3,
            },
        )

    launch_out = {
        "schema_version": str(launch.get("schema_version") or "0.1"),
        "processes": procs_out,
    }

    # --- exec ---
    eprocs_in = exec_doc.get("processes") if isinstance(exec_doc.get("processes"), list) else []
    eprocs_out: list[dict[str, Any]] = []
    for p in eprocs_in:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if not name or name in drop:
            continue
        entry = dict(p)
        deps = _filter_depends(list(entry.get("depends_on") or []), drop)
        if name.startswith("adapter.") or name.startswith("perception.") or name.startswith(
            "planning."
        ) or name.startswith("sensing."):
            if k_roudi and HOST_ROUDI not in deps:
                deps = [HOST_ROUDI] + deps
            elif k_dlt and HOST_DLT not in deps and not k_roudi:
                deps = [HOST_DLT] + deps
        if name == HOST_ROUDI and k_dlt and HOST_DLT not in deps:
            deps = [HOST_DLT] + deps
        entry["depends_on"] = deps
        if name.startswith("host."):
            entry["execution_client"] = False
        eprocs_out.append(entry)

    enames = {str(p.get("name")) for p in eprocs_out}
    if k_dlt and HOST_DLT not in enames:
        eprocs_out.insert(
            0,
            {
                "name": HOST_DLT,
                "function_group": "MachineFG",
                "depends_on": [],
                "execution_client": False,
            },
        )
    if k_roudi and HOST_ROUDI not in enames:
        eprocs_out.insert(
            1 if k_dlt else 0,
            {
                "name": HOST_ROUDI,
                "function_group": "MachineFG",
                "depends_on": [HOST_DLT] if k_dlt else [],
                "execution_client": False,
            },
        )

    exec_out = {
        "schema_version": str(exec_doc.get("schema_version") or "0.1"),
        "function_groups": exec_doc.get("function_groups")
        or [{"id": "MachineFG", "initial": "Running"}],
        "processes": eprocs_out,
    }
    return {"launch": launch_out, "exec": exec_out}


def emit_product_em_assets(
    platform_dir: Path,
    gen_dir: Path,
    *,
    k_dlt: bool,
    k_roudi: bool,
    gateway_forever: bool = True,
) -> dict[str, str]:
    """Write generated/em_launch.yaml + generated/exec.yaml (human/diff only).

    Product EM path reads deploy_config.hpp; YAML is not behavior truth on board.
    """
    tables = build_product_em_tables(
        platform_dir,
        k_dlt=k_dlt,
        k_roudi=k_roudi,
        gateway_forever=gateway_forever,
    )
    gen_dir.mkdir(parents=True, exist_ok=True)
    launch_path = gen_dir / "em_launch.yaml"
    exec_path = gen_dir / "exec.yaml"
    launch_path.write_text(
        yaml.safe_dump(tables["launch"], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    exec_path.write_text(
        yaml.safe_dump(tables["exec"], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {"em_launch": str(launch_path), "exec": str(exec_path)}
