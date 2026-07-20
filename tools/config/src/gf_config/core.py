"""Load/save project inputs and run compose."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from gf_codegen.compose.load_project import ProjectPaths, load_project
from gf_codegen.compose.parse_fidl import parse_fidl_file
from gf_codegen.compose.parse_hpp import parse_hpp_file
from gf_codegen.compose.pipeline import compose_project
from gf_codegen.paths import resolve_path


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    path.write_text(text, encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def canon_service(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if s.startswith("services."):
        return s
    if s.startswith("semantic."):
        return f"services.{s}"
    return f"services.semantic.{s}"


def short_service(svc: str) -> str:
    return (svc or "").split(".")[-1] if svc else ""


@dataclass
class ProjectSession:
    paths: ProjectPaths
    req: dict[str, Any]
    wiring: dict[str, Any]
    platform: dict[str, dict[str, Any]]
    dirty_req: bool = False
    dirty_wiring: bool = False
    dirty_platform: set[str] | None = None

    def __post_init__(self) -> None:
        if self.dirty_platform is None:
            self.dirty_platform = set()

    @classmethod
    def open(cls, project_file: Path) -> ProjectSession:
        paths = load_project(project_file)
        platform: dict[str, dict[str, Any]] = {}
        for key, p in (paths.platform or {}).items():
            if p.is_file():
                platform[key] = load_yaml(p)
            else:
                platform[key] = {"schema_version": "0.1"}
        return cls(
            paths=paths,
            req=load_yaml(paths.req),
            wiring=load_yaml(paths.wiring),
            platform=platform,
        )

    def save_req(self) -> None:
        _dump_yaml(self.paths.req, self.req)
        self.dirty_req = False

    def save_wiring(self) -> None:
        _dump_yaml(self.paths.wiring, self.wiring)
        self.dirty_wiring = False

    def save_platform(self, key: str | None = None) -> None:
        assert self.dirty_platform is not None
        keys = [key] if key else list(self.dirty_platform)
        for k in keys:
            path = self.paths.platform.get(k)
            data = self.platform.get(k)
            if path is None or data is None:
                continue
            _dump_yaml(path, data)
            self.dirty_platform.discard(k)

    def mark_platform_dirty(self, key: str) -> None:
        assert self.dirty_platform is not None
        self.dirty_platform.add(key)

    def is_dirty(self) -> bool:
        assert self.dirty_platform is not None
        return bool(self.dirty_req or self.dirty_wiring or self.dirty_platform)

    def save_all(self) -> None:
        if self.dirty_req:
            self.save_req()
        if self.dirty_wiring:
            self.save_wiring()
        assert self.dirty_platform is not None
        if self.dirty_platform:
            self.save_platform()

    def wiring_process_names(self, *, include_external: bool = False) -> list[str]:
        """Process names from wiring.deployments for platform dropdowns."""
        names: list[str] = []
        for d in self.deployments():
            name = str(d.get("process") or "").strip()
            if not name:
                continue
            if not include_external and name.startswith("external."):
                continue
            if name not in names:
                names.append(name)
        return names

    def compose(self) -> tuple[int, str]:
        self.save_all()
        rc = compose_project(self.paths.project_file, repo_root=self.paths.repo_root)
        report = ""
        if self.paths.lineage_report.is_file():
            report = self.paths.lineage_report.read_text(encoding="utf-8")
        return rc, report

    def generate(self, out_dir: Path | None = None) -> tuple[int, str]:
        """Compose if needed, then generate Proxy/Skeleton under project generated/."""
        from gf_codegen.generate_cmd import generate as generate_cmd

        rc, report = self.compose()
        if rc != 0:
            return rc, report
        sor = self.paths.out_sor
        if not sor.is_file():
            return 1, report
        out = out_dir or (self.paths.project_dir / "generated")
        gen_rc = generate_cmd(sor, out)
        return gen_rc, report

    def dataflows(self) -> list[dict[str, Any]]:
        return list(self.wiring.get("dataflows") or [])

    def deployments(self) -> list[dict[str, Any]]:
        return list(self.wiring.get("deployments") or [])

    def modules(self) -> list[dict[str, Any]]:
        return list(self.wiring.get("modules") or [])

    def set_dataflows(self, flows: list[dict[str, Any]]) -> None:
        self.wiring["dataflows"] = flows
        self.dirty_wiring = True

    def set_list_field(self, key: str, values: list[str]) -> None:
        self.req[key] = values
        self.dirty_req = True

    def upsert_deployment(
        self,
        process: str,
        *,
        compute_domain: str = "ap_linux",
        provides: list[str] | None = None,
        requires: list[str] | None = None,
    ) -> None:
        process = process.strip()
        if not process:
            raise ValueError("process name required")
        deps = list(self.wiring.get("deployments") or [])
        found = None
        for d in deps:
            if str(d.get("process")) == process:
                found = d
                break
        if found is None:
            found = {
                "process": process,
                "compute_domain": compute_domain,
                "provides": [],
                "requires": [],
            }
            deps.append(found)
            self.wiring["deployments"] = deps
        else:
            found["compute_domain"] = compute_domain or found.get("compute_domain") or "ap_linux"
        if provides is not None:
            found["provides"] = [canon_service(x) for x in provides if str(x).strip()]
        if requires is not None:
            found["requires"] = [canon_service(x) for x in requires if str(x).strip()]
        self.dirty_wiring = True

    def remove_deployment(self, process: str) -> None:
        process = process.strip()
        deps = [
            d
            for d in (self.wiring.get("deployments") or [])
            if str(d.get("process")) != process
        ]
        self.wiring["deployments"] = deps
        flows = [
            f
            for f in (self.wiring.get("dataflows") or [])
            if str(f.get("from")) != process and str(f.get("to")) != process
        ]
        self.wiring["dataflows"] = flows
        self.dirty_wiring = True

    def canvas(self) -> dict[str, Any]:
        c = self.wiring.get("canvas")
        if not isinstance(c, dict):
            c = {}
            self.wiring["canvas"] = c
        nodes = c.get("nodes")
        if not isinstance(nodes, dict):
            c["nodes"] = {}
        return c

    def node_ui(self, process: str) -> dict[str, Any]:
        nodes = self.canvas().setdefault("nodes", {})
        assert isinstance(nodes, dict)
        ui = nodes.get(process)
        if not isinstance(ui, dict):
            ui = {}
            nodes[process] = ui
        return ui

    def set_node_ui(self, process: str, **fields: Any) -> None:
        ui = self.node_ui(process)
        changed = False
        for k, v in fields.items():
            if v is None:
                if k in ui:
                    ui.pop(k, None)
                    changed = True
            elif ui.get(k) != v:
                ui[k] = v
                changed = True
        if changed:
            self.dirty_wiring = True

    def set_ports(self, process: str, provides: list[str], requires: list[str]) -> None:
        self.upsert_deployment(
            process,
            provides=[canon_service(x) for x in provides],
            requires=[canon_service(x) for x in requires],
        )
        # drop dataflows that no longer match ports
        provides_set = {short_service(canon_service(x)) for x in provides}
        requires_by = {process: {short_service(canon_service(x)) for x in requires}}
        # also keep map for other processes unchanged — only filter flows involving this process
        new_flows: list[dict[str, Any]] = []
        for f in self.dataflows():
            frm, to, svc = str(f.get("from") or ""), str(f.get("to") or ""), short_service(str(f.get("service") or ""))
            if frm == process and svc not in provides_set:
                continue
            if to == process and svc not in requires_by[process]:
                continue
            new_flows.append(f)
        self.wiring["dataflows"] = new_flows
        self.dirty_wiring = True

    def add_dataflow(self, frm: str, service: str, to: str) -> bool:
        """Append dataflow if not duplicate. Returns False if already present."""
        svc = canon_service(service)
        flows = self.dataflows()
        for f in flows:
            if (
                str(f.get("from")) == frm
                and str(f.get("to")) == to
                and short_service(str(f.get("service") or "")) == short_service(svc)
            ):
                return False
        flows.append({"from": frm, "service": svc, "to": to})
        self.set_dataflows(flows)
        return True

    def remove_dataflow_at(self, index: int) -> None:
        flows = self.dataflows()
        if 0 <= index < len(flows):
            flows.pop(index)
            self.set_dataflows(flows)

    def remove_dataflow_match(self, frm: str, service: str, to: str) -> None:
        svc = short_service(canon_service(service))
        flows = [
            f
            for f in self.dataflows()
            if not (
                str(f.get("from")) == frm
                and str(f.get("to")) == to
                and short_service(str(f.get("service") or "")) == svc
            )
        ]
        self.set_dataflows(flows)

    def upsert_module(
        self,
        module_id: str,
        hpp_rel: str = "",
        package: str = "",
        *,
        fidl_rel: str = "",
    ) -> None:
        modules = list(self.wiring.get("modules") or [])
        found = None
        for m in modules:
            if str(m.get("id")) == module_id:
                found = m
                break
        if found is None:
            entry: dict[str, Any] = {"id": module_id}
            if hpp_rel:
                entry["hpp"] = hpp_rel
            if fidl_rel:
                entry["fidl"] = fidl_rel
            if package:
                entry["package"] = package
            modules.append(entry)
            self.wiring["modules"] = modules
        else:
            if hpp_rel:
                found["hpp"] = hpp_rel
            if fidl_rel:
                found["fidl"] = fidl_rel
            if package:
                found["package"] = package
        self.dirty_wiring = True

    def resolve_hpp(self, hpp_rel: str) -> Path:
        return resolve_path(
            self.paths.project_dir,
            hpp_rel,
            repo_root=self.paths.repo_root,
        )

    def resolve_interface(self, rel: str) -> Path:
        return resolve_path(
            self.paths.project_dir,
            rel,
            repo_root=self.paths.repo_root,
        )

    def parse_hpp_candidates(self, hpp_path: Path) -> list[str]:
        """Struct names from header → service short-name candidates."""
        structs = parse_hpp_file(hpp_path)
        return [str(s["name"]) for s in structs if s.get("name")]

    def parse_fidl_candidates(self, fidl_path: Path) -> list[str]:
        """Struct / broadcast / method / interface names from .fidl."""
        parsed = parse_fidl_file(fidl_path)
        return list(parsed.get("candidates") or [])

    def module_hpp_for_process(self, process: str) -> Path | None:
        for m in self.modules():
            if str(m.get("id")) == process and m.get("hpp"):
                p = self.resolve_hpp(str(m["hpp"]))
                if p.is_file():
                    return p
        return None

    def relpath_from_repo(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.paths.repo_root.resolve()))
        except ValueError:
            return str(path)
