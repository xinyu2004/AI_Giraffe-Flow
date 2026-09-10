"""Load/save project inputs and run compose.

Layers (do not reverse dependencies):
  names → validate → ProjectSession (sole YAML + dirty_* writer) →
  gui/pipeline (flush→validate→save/compose) → gui widgets (session APIs only).
  Rebuild/paint paths must not migrate or seed YAML.
"""

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
from gf_config.names import (
    CHANNEL_POLICY_DEFAULTS,
    DEFAULT_CHANNEL_NAMES,
    LEGACY_FLAT_CHANNEL_KEYS,
    canon_service,
    default_publish_spec,
    is_channel_svc,
    normalize_channel_slot,
    short_service,
)
from gf_config.validate import ValidationResult, validate_project

# Re-export naming API (tests / GUI historically import from core).
__all__ = [
    "CHANNEL_POLICY_DEFAULTS",
    "DEFAULT_CHANNEL_NAMES",
    "LEGACY_FLAT_CHANNEL_KEYS",
    "ProjectSession",
    "canon_service",
    "default_publish_spec",
    "is_channel_svc",
    "load_yaml",
    "normalize_channel_slot",
    "short_service",
]


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


@dataclass
class ProjectSession:
    paths: ProjectPaths
    req: dict[str, Any]
    wiring: dict[str, Any]
    ara_cfg: dict[str, dict[str, Any]]
    dirty_req: bool = False
    dirty_wiring: bool = False
    dirty_ara_cfg: set[str] | None = None

    def __post_init__(self) -> None:
        if self.dirty_ara_cfg is None:
            self.dirty_ara_cfg = set()

    @classmethod
    def open(cls, project_file: Path) -> ProjectSession:
        paths = load_project(project_file)
        ara_cfg: dict[str, dict[str, Any]] = {}
        for key, p in (paths.gf_ara_cfg or {}).items():
            if p.is_file():
                ara_cfg[key] = load_yaml(p)
            else:
                ara_cfg[key] = {"schema_version": "0.1"}
        sess = cls(
            paths=paths,
            req=load_yaml(paths.req),
            wiring=load_yaml(paths.wiring),
            ara_cfg=ara_cfg,
        )
        sess.normalize_after_open()
        return sess

    def mark_req_dirty(self) -> None:
        self.dirty_req = True

    def mark_wiring_dirty(self) -> None:
        self.dirty_wiring = True

    def save_req(self) -> None:
        _dump_yaml(self.paths.req, self.req)
        self.dirty_req = False

    def save_wiring(self) -> None:
        _dump_yaml(self.paths.wiring, self.wiring)
        self.dirty_wiring = False

    def save_ara_cfg(self, key: str | None = None) -> None:
        assert self.dirty_ara_cfg is not None
        keys = [key] if key else list(self.dirty_ara_cfg)
        for k in keys:
            path = self.paths.gf_ara_cfg.get(k)
            data = self.ara_cfg.get(k)
            if path is None or data is None:
                continue
            _dump_yaml(path, data)
            self.dirty_ara_cfg.discard(k)

    def mark_ara_cfg_dirty(self, key: str) -> None:
        assert self.dirty_ara_cfg is not None
        self.dirty_ara_cfg.add(key)

    def get_ara_doc(self, key: str) -> dict[str, Any]:
        """Read-only copy of one gf_ara_cfg document."""
        doc = self.ara_cfg.get(key)
        return dict(doc) if isinstance(doc, dict) else {}

    def update_ara_doc(self, key: str, **fields: Any) -> bool:
        """Merge top-level fields into ara_cfg[key] and mark dirty if changed.

        ``None`` values remove the key. Ensures ``schema_version`` exists.
        Returns True if the document changed.
        """
        doc = self.ara_cfg.get(key)
        if not isinstance(doc, dict):
            doc = {"schema_version": "0.1"}
            self.ara_cfg[key] = doc
            changed = True
        else:
            changed = False
        if not doc.get("schema_version"):
            doc["schema_version"] = "0.1"
            changed = True
        for k, v in fields.items():
            if v is None:
                if k in doc:
                    doc.pop(k, None)
                    changed = True
            elif doc.get(k) != v:
                doc[k] = v
                changed = True
        if changed:
            self.mark_ara_cfg_dirty(key)
        return changed

    def is_dirty(self) -> bool:
        assert self.dirty_ara_cfg is not None
        return bool(self.dirty_req or self.dirty_wiring or self.dirty_ara_cfg)

    def topology(self) -> str:
        """SKU topology — single source: req.topology (compose reads req only)."""
        return str(self.req.get("topology") or "ap_only").strip() or "ap_only"

    def set_topology(self, topo: str) -> None:
        topo_n = str(topo or "ap_only").strip() or "ap_only"
        if self.req.get("topology") != topo_n:
            self.req["topology"] = topo_n
            self.mark_req_dirty()
        # Drop legacy dual-write key (silent if already absent).
        if "topology" in self.wiring:
            del self.wiring["topology"]
            self.mark_wiring_dirty()

    def normalize_after_open(self) -> None:
        """One-shot load migrations. Call from open() only — never from rebuild/paint."""
        wir_t = self.wiring.pop("topology", None)
        if wir_t and not self.req.get("topology"):
            self.req["topology"] = str(wir_t)
            self.mark_req_dirty()
        self.migrate_legacy_camera_channel_flows()

    def apply_sku_update(
        self,
        *,
        profile: str,
        variant: str,
        topology: str,
        product: str,
        bindings: list[str],
        observability: dict[str, Any],
        acceptance: dict[str, Any],
        apps: list[Any] | None = None,
    ) -> None:
        """SKU tab (req_editor) — sole writer for these req fields."""
        self.req["profile"] = profile
        self.req["variant"] = variant
        self.req["product"] = product
        self.set_topology(topology)
        self.req["bindings"] = list(bindings)
        self.req["observability"] = dict(observability)
        self.req["acceptance"] = dict(acceptance)
        if apps is not None:
            self.req["apps"] = apps
        self.mark_req_dirty()

    def set_runtime_modules(self, modules: list[str]) -> None:
        """Platform tab — sole writer for req.runtime_modules."""
        cleaned = [str(m).strip() for m in modules if str(m).strip()]
        if self.req.get("runtime_modules") != cleaned:
            self.req["runtime_modules"] = cleaned
            self.mark_req_dirty()

    def set_flow_route(
        self, flow: dict[str, Any], route: dict[str, Any] | None
    ) -> None:
        """Persist or clear an edge route bend (dataflow / channel_flow dict in wiring)."""
        if route is None:
            if "route" in flow:
                flow.pop("route", None)
                self.mark_wiring_dirty()
        else:
            if flow.get("route") != route:
                flow["route"] = dict(route)
                self.mark_wiring_dirty()

    def validate(self) -> ValidationResult:
        """In-memory gate (open / save). Does not write disk."""
        return validate_project(
            self.req,
            self.wiring,
            self.ara_cfg,
            project_dir=self.paths.project_dir,
        )

    def save_all(self, *, require_valid: bool = True) -> ValidationResult:
        """Persist dirty slices only when validation passes (default).

        When require_valid is False, writes unconditionally (tests / recovery only).
        """
        result = self.validate()
        if require_valid and not result.ok:
            return result
        if self.dirty_req:
            self.save_req()
        if self.dirty_wiring:
            self.save_wiring()
        assert self.dirty_ara_cfg is not None
        if self.dirty_ara_cfg:
            self.save_ara_cfg()
        return result

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

    def compose(self) -> tuple[int, str, ValidationResult]:
        """Validate → persist → compose_project. Disk unchanged if validation fails."""
        result = self.save_all(require_valid=True)
        if not result.ok:
            return 1, result.format_errors(), result
        rc = compose_project(self.paths.project_file, repo_root=self.paths.repo_root)
        report = ""
        if self.paths.lineage_report.is_file():
            report = self.paths.lineage_report.read_text(encoding="utf-8")
        return rc, report, result

    def generate(self, out_dir: Path | None = None) -> tuple[int, str, ValidationResult]:
        """Validate+persist+compose, then generate Proxy/Skeleton under generated/."""
        from gf_codegen.generate_cmd import generate as generate_cmd

        rc, report, result = self.compose()
        if rc != 0:
            return rc, report, result
        sor = self.paths.out_sor
        if not sor.is_file():
            return 1, report, result
        out = out_dir or (self.paths.project_dir / "generated")
        gen_rc = generate_cmd(sor, out)
        return gen_rc, report, result

    def dataflows(self) -> list[dict[str, Any]]:
        return list(self.wiring.get("dataflows") or [])

    def deployments(self) -> list[dict[str, Any]]:
        return list(self.wiring.get("deployments") or [])

    def provided_service_shorts(self) -> list[str]:
        """SOA Out short names across deployments (channel slots excluded). Order = first seen."""
        out: list[str] = []
        seen: set[str] = set()
        for d in self.deployments():
            for p in d.get("provides") or []:
                if is_channel_svc(str(p)):
                    continue
                s = short_service(canon_service(str(p)))
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)
        return out

    def channel_policy_names(self) -> list[str]:
        """GfChannel logical names for publish_policy.channels (from frame_ingest + existing)."""
        names: list[str] = []
        seen: set[str] = set()
        fi = self.req.get("frame_ingest") if isinstance(self.req.get("frame_ingest"), dict) else {}
        ch = fi.get("channels") if isinstance(fi.get("channels"), dict) else {}
        for k in ch:
            n = str(k).strip()
            if n and n not in seen:
                seen.add(n)
                names.append(n)
        raw = self.req.get("publish_policy")
        if isinstance(raw, dict):
            nested = raw.get("channels")
            if isinstance(nested, dict):
                for k in nested:
                    n = str(k).strip()
                    if n and n not in seen:
                        seen.add(n)
                        names.append(n)
        return names

    def publish_policy_services(self) -> dict[str, dict[str, Any]]:
        raw = self.req.get("publish_policy")
        if not isinstance(raw, dict):
            return {}
        nested = raw.get("services")
        out: dict[str, dict[str, Any]] = {}
        if isinstance(nested, dict):
            for k, v in nested.items():
                if isinstance(v, dict):
                    out[short_service(str(k))] = dict(v)
            return out
        for k, v in raw.items():
            if k in ("services", "channels") or not isinstance(v, dict):
                continue
            ks = str(k).strip()
            if ks.startswith("services.") or ks.startswith("semantic.") or "." not in ks:
                # Heuristic: channel-like keys stay out; treat bare semantic shorts as services
                if ks in LEGACY_FLAT_CHANNEL_KEYS:
                    continue
                out[short_service(ks)] = dict(v)
        return out

    def publish_policy_channels(self) -> dict[str, dict[str, Any]]:
        raw = self.req.get("publish_policy")
        if not isinstance(raw, dict):
            return {}
        nested = raw.get("channels")
        out: dict[str, dict[str, Any]] = {}
        if isinstance(nested, dict):
            for k, v in nested.items():
                if isinstance(v, dict):
                    out[str(k).strip()] = dict(v)
        return out

    def service_publish_spec(self, short: str) -> dict[str, Any]:
        s = short_service(short)
        return dict(self.publish_policy_services().get(s) or default_publish_spec())

    def apply_out_publish_policies(self, policies: dict[str, dict[str, Any]]) -> None:
        """Merge per-Out publish specs (keyed by short name). Shared across providers."""
        pp = self.req.get("publish_policy")
        if not isinstance(pp, dict):
            pp = {}
            self.req["publish_policy"] = pp
        services = pp.get("services")
        if not isinstance(services, dict):
            services = {}
            pp["services"] = services
        for short, spec in policies.items():
            s = short_service(short)
            if not s or not isinstance(spec, dict):
                continue
            services[s] = dict(spec)
        self.mark_req_dirty()

    def apply_channel_publish_policies(self, policies: dict[str, dict[str, Any]]) -> None:
        """Replace publish_policy.channels from frame_ingest dialog (authoritative)."""
        pp = self.req.get("publish_policy")
        if not isinstance(pp, dict):
            pp = {}
            self.req["publish_policy"] = pp
        cleaned: dict[str, dict[str, Any]] = {}
        for name, spec in policies.items():
            n = str(name).strip()
            if not n or not isinstance(spec, dict):
                continue
            cleaned[n] = dict(spec)
        pp["channels"] = cleaned
        self.mark_req_dirty()

    def prune_orphan_publish_policies(self) -> None:
        """Drop service policy entries with no provider Out left."""
        live = set(self.provided_service_shorts())
        pp = self.req.get("publish_policy")
        if not isinstance(pp, dict):
            return
        services = pp.get("services")
        if not isinstance(services, dict):
            return
        drop = [k for k in list(services) if short_service(str(k)) not in live]
        if not drop:
            return
        for k in drop:
            del services[k]
        self.mark_req_dirty()

    def modules(self) -> list[dict[str, Any]]:
        return list(self.wiring.get("modules") or [])

    def set_dataflows(self, flows: list[dict[str, Any]]) -> None:
        self.wiring["dataflows"] = flows
        self.mark_wiring_dirty()

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
        # Video contract lives on canvas + req.frame_ingest / EM inject — never deployments.
        if self.is_frame_ingest_process(process=process):
            self.scrub_frame_ingest_from_deployments()
            return
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
        self.mark_wiring_dirty()

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
        self.mark_wiring_dirty()

    def canvas(self) -> dict[str, Any]:
        """Ensure wiring.canvas exists (mutates structure; call only from writers)."""
        c = self.wiring.get("canvas")
        if not isinstance(c, dict):
            c = {}
            self.wiring["canvas"] = c
        nodes = c.get("nodes")
        if not isinstance(nodes, dict):
            c["nodes"] = {}
        return c

    def get_node_ui(self, process: str) -> dict[str, Any]:
        """Read-only copy of canvas node UI. Never creates entries."""
        c = self.wiring.get("canvas")
        if not isinstance(c, dict):
            return {}
        nodes = c.get("nodes")
        if not isinstance(nodes, dict):
            return {}
        ui = nodes.get(process)
        return dict(ui) if isinstance(ui, dict) else {}

    def node_ui(self, process: str) -> dict[str, Any]:
        """Compat alias for get_node_ui (read-only; does not create canvas keys)."""
        return self.get_node_ui(process)

    def _ensure_node_ui(self, process: str) -> dict[str, Any]:
        nodes = self.canvas().setdefault("nodes", {})
        assert isinstance(nodes, dict)
        ui = nodes.get(process)
        if not isinstance(ui, dict):
            ui = {}
            nodes[process] = ui
        return ui

    def set_node_ui(self, process: str, **fields: Any) -> None:
        """Patch canvas node UI. ``None`` values are skipped (never delete).

        To remove keys, call ``clear_node_ui_keys``.
        """
        ui = self._ensure_node_ui(process)
        changed = False
        for k, v in fields.items():
            if v is None:
                continue
            if ui.get(k) != v:
                ui[k] = v
                changed = True
        if changed:
            self.mark_wiring_dirty()

    def clear_node_ui_keys(self, process: str, *keys: str) -> None:
        ui = self.get_node_ui(process)
        if not ui:
            return
        live = self._ensure_node_ui(process)
        changed = False
        for k in keys:
            if k in live:
                live.pop(k, None)
                changed = True
        if changed:
            self.mark_wiring_dirty()

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
        self.prune_orphan_publish_policies()
        self.mark_wiring_dirty()

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

    def camera_slots(self) -> list[dict[str, Any]]:
        fi = self.req.get("frame_ingest")
        if not isinstance(fi, dict):
            return []
        slots = fi.get("camera_slots")
        return [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else []

    def set_camera_slots(self, slots: list[dict[str, Any]]) -> None:
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
            try:
                fps = int(s.get("fps") or 0)
            except (TypeError, ValueError):
                fps = 0
            if fps > 0:
                entry["fps"] = fps
            cleaned.append(entry)
        fi["camera_slots"] = cleaned
        self.mark_req_dirty()

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
        self.mark_req_dirty()

    def upsert_camera_slot(self, slot: dict[str, Any]) -> None:
        sid = str(slot.get("id") or "").strip()
        if not sid:
            raise ValueError("camera_slot id required")
        slots = self.camera_slots()
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
        self.set_camera_slots(slots)

    def remove_camera_slot(self, slot_id: str) -> None:
        sid = (slot_id or "").strip()
        self.set_camera_slots([s for s in self.camera_slots() if str(s.get("id")) != sid])

    def channel_flows(self) -> list[dict[str, Any]]:
        raw = self.wiring.get("channel_flows")
        return [f for f in raw if isinstance(f, dict)] if isinstance(raw, list) else []

    def set_channel_flows(self, flows: list[dict[str, Any]]) -> None:
        self.wiring["channel_flows"] = list(flows)
        self.mark_wiring_dirty()

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
                self.mark_wiring_dirty()
        self.scrub_channel_ports_from_deployments()
        self.scrub_frame_ingest_from_deployments()

    def scrub_frame_ingest_from_deployments(self) -> None:
        """host.frame_ingest must not appear in deployments (canvas / EM only)."""
        ingest = self.FRAME_INGEST_PROCESS
        deps = list(self.wiring.get("deployments") or [])
        cleaned = [
            d
            for d in deps
            if isinstance(d, dict)
            and not self.is_frame_ingest_process(process=str(d.get("process") or ""))
        ]
        if len(cleaned) != len(deps):
            self.wiring["deployments"] = cleaned
            self.mark_wiring_dirty()
        # Drop any accidental SOA dataflows involving ingest
        flows = self.dataflows()
        kept = [
            f
            for f in flows
            if str(f.get("from") or "") != ingest and str(f.get("to") or "") != ingest
        ]
        if len(kept) != len(flows):
            self.set_dataflows(kept)

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
            self.mark_wiring_dirty()

    def seed_default_channel_flows(self) -> None:
        """front → perception.fcm; other camera_slots → perception.surround when present."""
        ingest = self.FRAME_INGEST_PROCESS
        deps = {str(d.get("process")) for d in self.deployments()}
        has_fcm = "perception.fcm" in deps
        has_sur = "perception.surround" in deps
        if not has_fcm and not has_sur:
            return
        for s in self.camera_slots():
            sid = str(s.get("id") or "").strip()
            if not sid:
                continue
            slot = self.gf_channel_slot_name(sid)
            if sid == "front" and has_fcm:
                to = "perception.fcm"
            elif sid != "front" and has_sur:
                to = "perception.surround"
            else:
                continue
            self.add_channel_flow(ingest, to, slot=slot)

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
                    self.mark_wiring_dirty()
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
        """Remove optional video-contract node: camera_slots + channel_flows + canvas."""
        ingest = self.FRAME_INGEST_PROCESS
        self.update_frame_ingest(active_source="none")
        self.set_camera_slots([])
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
                    self.mark_wiring_dirty()

    def remove_camera_node(self, process: str) -> None:
        """Compat: per-lane camera.* → strip that camera_slot; ingest node uses remove_frame_ingest_node."""
        process = process.strip()
        if self.is_frame_ingest_process(process=process) and not process.startswith("camera."):
            self.remove_frame_ingest_node()
            return
        sid = self.slot_id_from_camera_process(process)
        self.remove_camera_slot(sid)
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
            self.mark_wiring_dirty()

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
        self.mark_wiring_dirty()

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
