"""Hierarchical manifest.yaml helpers for AFC run_cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent
_AFC_ROOT = (
    _LIB.parent.parent if _LIB.parent.name == "src" else _LIB.parent
)

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore


def load_manifest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    data: dict[str, Any] = {"cases": [], "children": []}
    cur: dict[str, str] = {}
    in_children = False
    for line in text.splitlines():
        raw = line.rstrip()
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if s.startswith("kind:"):
            data["kind"] = s.split(":", 1)[1].strip()
            in_children = False
        elif s.startswith("product:"):
            data["product"] = s.split(":", 1)[1].strip()
            in_children = False
        elif s.startswith("children:"):
            in_children = True
        elif s.startswith("cases:"):
            in_children = False
        elif in_children and s.startswith("- ") and indent <= 2:
            data["children"].append(s[2:].strip().strip("'").strip('"'))
        elif s.startswith("- id:"):
            in_children = False
            if cur:
                data["cases"].append(cur)
            cur = {"id": s.split(":", 1)[1].strip()}
        elif cur and s.startswith("script:"):
            cur["script"] = s.split(":", 1)[1].strip()
        elif cur and s.startswith("status:"):
            cur["status"] = s.split(":", 1)[1].strip()
    if cur:
        data["cases"].append(cur)
    return data


def collect_from_dir(root: Path) -> list[dict[str, Any]]:
    """Recurse suite/cases manifests. Missing manifest.yaml → error."""
    root = root.resolve()
    man_path = root / "manifest.yaml"
    if not man_path.is_file():
        raise FileNotFoundError(f"no manifest.yaml in {root}")
    man = load_manifest(man_path)
    kind = str(man.get("kind") or "").strip().lower()
    children = list(man.get("children") or [])
    if kind == "suite" or (children and not man.get("cases")):
        out: list[dict[str, Any]] = []
        if not children:
            raise ValueError(f"suite manifest has no children: {man_path}")
        for child in children:
            child_path = (root / str(child)).resolve()
            if not child_path.is_dir():
                raise FileNotFoundError(
                    f"child dir missing: {child_path} (from {man_path})"
                )
            out.extend(collect_from_dir(child_path))
        return out

    out = []
    for c in man.get("cases") or []:
        entry = dict(c)
        entry["_dir"] = root
        entry["_manifest"] = str(man_path)
        out.append(entry)
    return out


def default_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "manifest.yaml").is_file():
        return cwd
    if (_AFC_ROOT / "manifest.yaml").is_file():
        return _AFC_ROOT
    raise FileNotFoundError(
        f"no manifest.yaml in cwd={cwd} or package={_AFC_ROOT}"
    )


def resolve_targets(targets: list[str]) -> list[dict[str, Any]]:
    """Build runnable case entries from directory targets only."""
    if not targets:
        return collect_from_dir(default_root())

    out: list[dict[str, Any]] = []
    for raw in targets:
        p = Path(raw)
        if not p.is_absolute():
            cand = Path.cwd() / p
            p = cand if cand.exists() else (_AFC_ROOT / p)
        p = p.resolve()
        if p.is_file() and p.suffix == ".py":
            raise ValueError(
                f"refusing script path {raw!r}: batch multi-case is defined "
                f"in manifest.yaml only. Run a single case with "
                f"'python3 {raw}', or pass a directory that has manifest.yaml"
            )
        if p.is_dir():
            out.extend(collect_from_dir(p))
            continue
        raise FileNotFoundError(f"target not found (directory): {raw}")
    return out
