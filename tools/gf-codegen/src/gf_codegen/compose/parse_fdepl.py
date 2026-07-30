"""Lightweight Franca .fdepl reader for SOME/IP IDs (P1 B staged / optional).

Does not replace req.bindings. Maps common CommonAPI SOME/IP deployment
properties into a plain dict for docs / future vsomeip config emit.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return text


def parse_fdepl_file(path: Path) -> dict[str, Any]:
    """Parse a minimal SOME/IP-oriented .fdepl.

    Returns:
      {
        "deployments": [
          {"interface": "...", "SomeIpServiceID": 0x1234, "SomeIpInstanceID": 1, ...}
        ],
        "raw_properties": {dotted_key: value_str}
      }
    """
    text = _strip_comments(path.read_text(encoding="utf-8"))
    raw: dict[str, str] = {}
    # property assignments: SomeIpServiceID = 1234  or  0x1234
    for m in re.finditer(
        r"\b(SomeIp(?:Service|Instance|Method|Event|EventGroup)ID)\s*=\s*(0x[0-9A-Fa-f]+|\d+)\b",
        text,
    ):
        key = m.group(1)
        val = m.group(2)
        raw[key] = val

    deployments: list[dict[str, Any]] = []
    # define pkg.Iface someip { ... }  or  interface Name { ... }
    for m in re.finditer(
        r"\b(?:define\s+([\w.]+)\s+\w+|interface\s+([\w.]+))\s*\{([^}]*)\}",
        text,
        flags=re.S,
    ):
        name = m.group(1) or m.group(2)
        body = m.group(3)
        entry: dict[str, Any] = {"interface": name}
        for pm in re.finditer(
            r"\b(SomeIp(?:Service|Instance|Method|Event|EventGroup)ID)\s*=\s*(0x[0-9A-Fa-f]+|\d+)\b",
            body,
        ):
            k, v = pm.group(1), pm.group(2)
            entry[k] = int(v, 0)
        if len(entry) > 1:
            deployments.append(entry)

    # If no nested blocks, surface file-level IDs as one deployment
    if not deployments and raw:
        entry = {"interface": path.stem}
        for k, v in raw.items():
            entry[k] = int(v, 0)
        deployments.append(entry)

    return {"deployments": deployments, "raw_properties": raw}


def deployments_to_yaml_dict(parsed: dict[str, Any]) -> dict[str, Any]:
    """Shape suitable for wiring extension / docs dump."""
    return {
        "someip_from_fdepl": {
            "deployments": parsed.get("deployments") or [],
        }
    }
