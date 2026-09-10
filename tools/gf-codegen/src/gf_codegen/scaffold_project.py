"""Scaffold a new Giraffe SKU project (giraffe.yaml + cfg/)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gf_codegen.compose.load_project import GF_ARA_CFG_KEYS, GIRAFFE_YAML

_MIN_ARA: dict[str, Any] = {"schema_version": "0.1"}

_MIN_EXEC: dict[str, Any] = {
    "schema_version": "0.1",
    "function_groups": [{"id": "MachineFG", "initial": "Running"}],
    "processes": [],
}

_MIN_REQ: dict[str, Any] = {
    "schema_version": "0.1",
    "variant": "new_sku",
    "topology": "ap_only",
    "product": "NEW",
    "capabilities": [],
    "runtime_modules": [
        "core",
        "com",
        "osal",
        "exec",
        "sm",
        "phm",
        "log",
        "diag",
        "ucm",
        "collector",
        "bounds",
    ],
    "bindings": ["iceoryx"],
    "observability": {},
    "apps": [],
    "acceptance": {"lineage_required": False},
}

_MIN_WIRING: dict[str, Any] = {
    "schema_version": "0.1",
    "modules": [],
    "deployments": [],
    "dataflows": [],
    "bindings": [],
    "channel_flows": [],
    "canvas": {"nodes": {}},
}


def _dump(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def scaffold_project(
    project_dir: Path,
    *,
    project_id: str,
    product: str = "NEW",
    customer_id: str = "oem",
    fail_on_error: bool = False,
    base_sor: str = "tools/gf-codegen/schemas/examples/desktop_ap_only.sor.json",
) -> Path:
    """
    Create a minimal Giraffe project tree. Returns path to giraffe.yaml.

    Layout:
      giraffe.yaml
      cfg/req.yaml
      cfg/wiring.yaml
      cfg/gf_ara_cfg/{exec,em_launch,...}.yaml
      oem/ (placeholder note)
      reports/
      generated/
    """
    project_dir = project_dir.resolve()
    if (project_dir / GIRAFFE_YAML).exists():
        raise FileExistsError(f"already a Giraffe project: {project_dir / GIRAFFE_YAML}")

    cfg = project_dir / "cfg"
    ara = cfg / "gf_ara_cfg"
    ara.mkdir(parents=True, exist_ok=True)
    (project_dir / "reports").mkdir(parents=True, exist_ok=True)
    (project_dir / "generated").mkdir(parents=True, exist_ok=True)
    oem = project_dir / "oem"
    oem.mkdir(parents=True, exist_ok=True)
    (oem / "README.md").write_text(
        "# OEM import\n\nPlace `oem_import.dbc` and `oem_import.yaml` here "
        "(or update paths in giraffe.yaml).\n",
        encoding="utf-8",
    )

    req = dict(_MIN_REQ)
    req["variant"] = project_id
    req["product"] = product
    _dump(cfg / "req.yaml", req)
    _dump(cfg / "wiring.yaml", dict(_MIN_WIRING))

    for key in GF_ARA_CFG_KEYS:
        if key == "exec":
            _dump(ara / f"{key}.yaml", dict(_MIN_EXEC))
        else:
            _dump(ara / f"{key}.yaml", dict(_MIN_ARA))

    giraffe: dict[str, Any] = {
        "schema_version": "0.1",
        "project_id": project_id,
        "customer_id": customer_id,
        "product": product,
        "base": base_sor,
        "out": "gf.sor.json",
        "oem": {
            "dbc": "oem/oem_import.dbc",
            "manifest": "oem/oem_import.yaml",
        },
        "delivery": {"req": "cfg/req.yaml"},
        "integration": {"wiring": "cfg/wiring.yaml"},
        "gf_ara_cfg": {
            key: f"cfg/gf_ara_cfg/{key}.yaml" for key in GF_ARA_CFG_KEYS
        },
        "lineage": {
            "report": "reports/signal_lineage_report.yaml",
            "fail_on_error": fail_on_error,
        },
    }
    entry = project_dir / GIRAFFE_YAML
    header = (
        "# Giraffe 工程入口索引 — 不含业务细节\n"
        "# 作者源在 cfg/：req · wiring · gf_ara_cfg/*\n"
        "# gf_ara_cfg = 中间件运行时作者树（gf-config 页 2），≠ 全部 gf-config 输出\n"
    )
    body = yaml.safe_dump(
        giraffe,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    entry.write_text(header + body, encoding="utf-8")
    return entry
