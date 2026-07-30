"""Import OEM DBC + manifest into SOR fragments."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

import cantools
import yaml


def _message_included(name: str, include: list[str], exclude_patterns: list[str]) -> bool:
    for pat in exclude_patterns:
        if fnmatch.fnmatch(name, pat):
            return False
    if include:
        return name in include
    return True


def import_oem(dbc_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Return overlay dict: imports_meta, adapter_mappings, types (partial)."""
    with manifest_path.open(encoding="utf-8") as f:
        manifest = yaml.safe_load(f) or {}

    db = cantools.database.load_file(str(dbc_path))
    extraction = (manifest.get("extraction") or {}).get("dbc") or {}
    include = list(extraction.get("include_messages") or [])
    exclude = list(extraction.get("exclude_name_patterns") or [])
    module_owned = list(extraction.get("module_owned") or [])

    sources = manifest.get("sources") or []
    gateway_provides: list[str] = []
    for src in sources:
        gw = (src or {}).get("gateway") or {}
        gateway_provides.extend(gw.get("provides") or [])

    owned_patterns = [m.get("pattern") for m in module_owned if m.get("pattern")]

    imported_msgs: list[str] = []
    adapter_mappings: list[dict[str, Any]] = []
    types: list[dict[str, Any]] = []

    for msg in db.messages:
        if not _message_included(msg.name, include, exclude):
            continue
        # skip if module-owned by pattern
        if any(fnmatch.fnmatch(msg.name, pat) for pat in owned_patterns):
            continue
        imported_msgs.append(msg.name)

        # P_VEHICLE_INFO → EgoMotion mapping (gateway)
        if msg.name == "P_VEHICLE_INFO" and "services.semantic.EgoMotion" in gateway_provides:
            fields = []
            for sig in msg.signals:
                fields.append(
                    {
                        "semantic": sig.name,
                        "source_signal": sig.name,
                    }
                )
            adapter_mappings.append(
                {
                    "id": "map.ego_motion_from_can",
                    "source": {
                        "protocol": "can",
                        "message": msg.name,
                        "frame_id": hex(msg.frame_id),
                    },
                    "semantic_type": "types.EgoMotion",
                    "fields": fields,
                }
            )

    imports_meta: dict[str, Any] = {
        "sources": [
            {
                "file": str(dbc_path).replace("\\", "/"),
                "role": "vehicle_can",
                "message_count": len(imported_msgs),
                "imported_messages": imported_msgs,
                "import": "gf-codegen compose import oem",
            }
        ],
        "manifest": str(manifest_path).replace("\\", "/"),
        "module_owned": module_owned,
        "gateway_provides": gateway_provides,
    }

    return {
        "imports_meta": imports_meta,
        "adapter_mappings": adapter_mappings,
        "types": types,
    }
