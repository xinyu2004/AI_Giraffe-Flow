"""Path helpers: repo root and project-relative resolution."""

from __future__ import annotations

from pathlib import Path

# SOR contract + examples live with the tool (not at repo root).
SCHEMA_REL = "tools/gf-codegen/schemas"


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward until a directory containing tools/gf-codegen/ and projects/."""
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "tools" / "gf-codegen").is_dir() and (p / "projects").is_dir():
            return p
    raise FileNotFoundError(
        "Cannot find repo root (expected tools/gf-codegen/ and projects/). "
        "Pass --repo-root or run from the monorepo."
    )


def _repo_rel(text: str) -> str:
    """Map legacy schemas/… to tools/gf-codegen/schemas/…."""
    if text.startswith("schemas/") or text == "schemas":
        return f"tools/gf-codegen/{text}"
    return text


def resolve_path(base: Path, maybe_relative: str, *, repo_root: Path | None = None) -> Path:
    """Resolve a path that may be absolute, repo-relative, or base-relative."""
    raw = Path(maybe_relative)
    if raw.is_absolute():
        return raw
    text = _repo_rel(maybe_relative.replace("\\", "/"))
    if (
        text.startswith("projects/")
        or text.startswith("tools/gf-codegen/")
        or text.startswith("Requirement/")
    ):
        root = repo_root or find_repo_root(base)
        return (root / text).resolve()
    return (base / raw).resolve()
