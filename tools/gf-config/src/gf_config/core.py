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


def normalize_channel_slot(s: str) -> str | None:
    """Return canonical gf.channel.* or None if not a GfChannel slot name."""
    raw = (s or "").strip()
    if not raw:
        return None
    if raw.startswith("gf.channel."):
        return raw
    # Polluted SOA form: services.semantic.gf.channel.front
    marker = "gf.channel."
    idx = raw.find(marker)
    if idx >= 0:
        return raw[idx:]
    return None


def is_channel_svc(s: str) -> bool:
    return normalize_channel_slot(s) is not None


def canon_service(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    ch = normalize_channel_slot(s)
    if ch:
        return ch
    if s.startswith("services."):
        return s
    if s.startswith("semantic."):
        return f"services.{s}"
    return f"services.semantic.{s}"


def short_service(svc: str) -> str:
    ch = normalize_channel_slot(svc or "")
    if ch:
        return ch
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

    def wiring_service_names(self) -> list[str]:
        """Canonical service names from deployments + dataflows (SKU pickers)."""
        out: set[str] = set()
        for d in self.deployments():
            if not isinstance(d, dict):
                continue
            for s in list(d.get("provides") or []) + list(d.get("requires") or []):
                name = str(s).strip()
                if name:
                    out.add(canon_service(name))
        for f in self.dataflows():
            if not isinstance(f, dict):
                continue
            name = str(f.get("service") or "").strip()
            if name:
                out.add(canon_service(name))
        return sorted(out)

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
            found["provides"] = [
                canon_service(x)
                for x in provides
                if str(x).strip() and not is_channel_svc(str(x))
            ]
        if requires is not None:
            found["requires"] = [
                canon_service(x)
                for x in requires
                if str(x).strip() and not is_channel_svc(str(x))
            ]
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

    def set_ports(
        self,
        process: str,
        provides: list[str],
        requires: list[str],
        *,
        prune_flows: bool = True,
    ) -> None:
        # GfChannel slots never belong in deployments (canvas / channel_flows only).
        soa_prov = [x for x in provides if not is_channel_svc(x)]
        soa_req = [x for x in requires if not is_channel_svc(x)]
        self.upsert_deployment(
            process,
            provides=[canon_service(x) for x in soa_prov],
            requires=[canon_service(x) for x in soa_req],
        )
        if prune_flows:
            # drop dataflows that no longer match ports
            provides_set = {short_service(canon_service(x)) for x in soa_prov}
            requires_by = {
                process: {short_service(canon_service(x)) for x in soa_req}
            }
            new_flows: list[dict[str, Any]] = []
            for f in self.dataflows():
                frm = str(f.get("from") or "")
                to = str(f.get("to") or "")
                svc = short_service(str(f.get("service") or ""))
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

    # --- GfChannel / frame_ingest (canvas UX; freeze in req.frame_ingest) ---

    FRAME_INGEST_PROCESS = "host.frame_ingest"

    @classmethod
    def frame_ingest_process_name(cls) -> str:
        return cls.FRAME_INGEST_PROCESS

    @staticmethod
    def is_frame_ingest_process(*, kind: str = "", process: str = "") -> bool:
        p = (process or "").strip()
        k = (kind or "").strip()
        if k == "frame_ingest":
            return True
        if p in ("host.frame_ingest", "frame_ingest"):
            return True
        # Legacy Round-B CameraSource nodes
        return k == "camera_source" or p.startswith("camera.")

    @staticmethod
    def camera_process_name(slot_id: str) -> str:
        """Deprecated alias — lanes are Out ports on host.frame_ingest."""
        sid = (slot_id or "front").strip() or "front"
        return f"camera.{sid}"

    @staticmethod
    def slot_id_from_camera_process(process: str) -> str:
        p = (process or "").strip()
        if p.startswith("camera."):
            return p[len("camera.") :] or "front"
        return p or "front"

    @staticmethod
    def gf_channel_slot_name(slot_id: str) -> str:
        sid = (slot_id or "front").strip() or "front"
        return f"gf.channel.{sid}"

    @staticmethod
    def slot_id_from_channel(slot: str) -> str:
        s = (slot or "").strip()
        if s.startswith("gf.channel."):
            return s[len("gf.channel.") :] or "front"
        return s or "front"

    def tip_slots(self) -> list[dict[str, Any]]:
        fi = self.req.get("frame_ingest")
        if not isinstance(fi, dict):
            return []
        slots = fi.get("tip_slots")
        return [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else []

    def set_tip_slots(self, slots: list[dict[str, Any]]) -> None:
        fi = self.req.get("frame_ingest")
        if not isinstance(fi, dict):
            fi = {}
            self.req["frame_ingest"] = fi
        # Authoring: id/w/h (+ optional pixel); no mount / buffers in GUI contract
        cleaned: list[dict[str, Any]] = []
        for s in slots:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id") or "").strip()
            if not sid:
                continue
            entry: dict[str, Any] = {
                "id": sid,
                "w": int(s.get("w") or 640),
                "h": int(s.get("h") or 480),
            }
            pix = str(s.get("pixel_format") or "").strip()
            if pix:
                entry["pixel_format"] = pix
            cleaned.append(entry)
        fi["tip_slots"] = cleaned
        self.dirty_req = True

    def frame_ingest_cfg(self) -> dict[str, Any]:
        fi = self.req.get("frame_ingest")
        return fi if isinstance(fi, dict) else {}

    def update_frame_ingest(self, **fields: Any) -> None:
        fi = self.req.get("frame_ingest")
        if not isinstance(fi, dict):
            fi = {}
            self.req["frame_ingest"] = fi
        for k, v in fields.items():
            if v is None:
                fi.pop(k, None)
            else:
                fi[k] = v
        self.dirty_req = True

    def upsert_tip_slot(self, slot: dict[str, Any]) -> None:
        sid = str(slot.get("id") or "").strip()
        if not sid:
            raise ValueError("tip_slot id required")
        slots = self.tip_slots()
        found = None
        for s in slots:
            if str(s.get("id")) == sid:
                found = s
                break
        if found is None:
            slots.append(dict(slot))
        else:
            found.update(slot)
            found["id"] = sid
        self.set_tip_slots(slots)

    def remove_tip_slot(self, slot_id: str) -> None:
        sid = (slot_id or "").strip()
        self.set_tip_slots([s for s in self.tip_slots() if str(s.get("id")) != sid])

    def channel_flows(self) -> list[dict[str, Any]]:
        raw = self.wiring.get("channel_flows")
        return [f for f in raw if isinstance(f, dict)] if isinstance(raw, list) else []

    def set_channel_flows(self, flows: list[dict[str, Any]]) -> None:
        self.wiring["channel_flows"] = list(flows)
        self.dirty_wiring = True

    def migrate_legacy_camera_channel_flows(self) -> None:
        """Rewrite camera.* → host.frame_ingest; scrub GfChannel out of deployments."""
        ingest = self.FRAME_INGEST_PROCESS
        changed = False
        flows: list[dict[str, Any]] = []
        for f in self.channel_flows():
            frm = str(f.get("from") or "")
            entry = dict(f)
            if frm.startswith("camera."):
                entry["from"] = ingest
                if not str(entry.get("slot") or "").strip():
                    entry["slot"] = self.gf_channel_slot_name(
                        self.slot_id_from_camera_process(frm)
                    )
                changed = True
            slot = normalize_channel_slot(str(entry.get("slot") or ""))
            if slot and str(entry.get("slot") or "") != slot:
                entry["slot"] = slot
                changed = True
            flows.append(entry)
        if changed:
            self.set_channel_flows(flows)
        nodes = self.canvas().get("nodes")
        if isinstance(nodes, dict):
            drop = [k for k in list(nodes.keys()) if str(k).startswith("camera.")]
            for k in drop:
                del nodes[k]
            if drop:
                self.dirty_wiring = True
        self.scrub_channel_ports_from_deployments()

    def scrub_channel_ports_from_deployments(self) -> None:
        """Remove polluted gf.channel.* entries from deployments provides/requires."""
        deps = list(self.wiring.get("deployments") or [])
        dirty = False
        for d in deps:
            if not isinstance(d, dict):
                continue
            for key in ("provides", "requires"):
                raw = d.get(key)
                if not isinstance(raw, list):
                    continue
                cleaned = [x for x in raw if not is_channel_svc(str(x))]
                if cleaned != list(raw):
                    d[key] = cleaned
                    dirty = True
        if dirty:
            self.wiring["deployments"] = deps
            self.dirty_wiring = True

    def add_channel_flow(self, frm: str, to: str, *, slot: str = "") -> bool:
        """Append GfChannel edge (not iceoryx dataflow)."""
        frm = frm.strip()
        to = to.strip()
        if not frm or not to:
            return False
        if frm.startswith("camera."):
            if not slot:
                slot = self.gf_channel_slot_name(self.slot_id_from_camera_process(frm))
            frm = self.FRAME_INGEST_PROCESS
        slot_n = normalize_channel_slot(slot or "") or (slot or "").strip()
        flows = self.channel_flows()
        for f in flows:
            if str(f.get("from")) == frm and str(f.get("to")) == to:
                existing = str(f.get("slot") or "")
                if slot_n and existing and existing != slot_n:
                    continue
                if slot_n and not existing:
                    f["slot"] = slot_n
                    self.dirty_wiring = True
                return False
            # Same slot already wired from ingest to this consumer
            if (
                str(f.get("from")) == frm
                and slot_n
                and str(f.get("slot") or "") == slot_n
                and str(f.get("to")) == to
            ):
                return False
        entry: dict[str, Any] = {"from": frm, "to": to, "kind": "gf_channel"}
        if slot_n:
            entry["slot"] = slot_n
        flows.append(entry)
        self.set_channel_flows(flows)
        return True

    def remove_channel_flow_match(self, frm: str, to: str, *, slot: str = "") -> None:
        if frm.startswith("camera."):
            frm = self.FRAME_INGEST_PROCESS
        slot_n = (slot or "").strip()
        flows = []
        for f in self.channel_flows():
            if str(f.get("from")) == frm and str(f.get("to")) == to:
                if slot_n and str(f.get("slot") or "") not in ("", slot_n):
                    flows.append(f)
                    continue
                continue
            flows.append(f)
        self.set_channel_flows(flows)

    def remove_frame_ingest_node(self) -> None:
        """Remove optional video-contract node: tip_slots + channel_flows + canvas."""
        ingest = self.FRAME_INGEST_PROCESS
        self.update_frame_ingest(active_source="none")
        self.set_tip_slots([])
        flows = [
            f
            for f in self.channel_flows()
            if str(f.get("from")) != ingest
            and str(f.get("to")) != ingest
            and not str(f.get("from") or "").startswith("camera.")
        ]
        self.set_channel_flows(flows)
        nodes = self.canvas().get("nodes")
        if isinstance(nodes, dict):
            for key in list(nodes.keys()):
                ui = nodes.get(key) if isinstance(nodes.get(key), dict) else {}
                if self.is_frame_ingest_process(
                    process=str(key), kind=str(ui.get("kind") or "")
                ):
                    del nodes[key]
                    self.dirty_wiring = True

    def remove_camera_node(self, process: str) -> None:
        """Compat: per-lane camera.* → strip that tip_slot; ingest node uses remove_frame_ingest_node."""
        process = process.strip()
        if self.is_frame_ingest_process(process=process) and not process.startswith("camera."):
            self.remove_frame_ingest_node()
            return
        sid = self.slot_id_from_camera_process(process)
        self.remove_tip_slot(sid)
        slot = self.gf_channel_slot_name(sid)
        flows = []
        for f in self.channel_flows():
            if str(f.get("from")) == process:
                continue
            if str(f.get("slot") or "") == slot and str(f.get("from")) in (
                self.FRAME_INGEST_PROCESS,
                process,
            ):
                continue
            flows.append(f)
        self.set_channel_flows(flows)
        nodes = self.canvas().get("nodes")
        if isinstance(nodes, dict) and process in nodes:
            del nodes[process]
            self.dirty_wiring = True

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
