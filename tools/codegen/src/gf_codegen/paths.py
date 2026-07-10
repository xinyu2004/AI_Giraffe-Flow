"""Path helpers: repo root and project-relative resolution."""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward until a directory containing both schemas/ and projects/."""
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "schemas").is_dir() and (p / "projects").is_dir():
            return p
    raise FileNotFoundError(
        "Cannot find repo root (expected schemas/ and projects/). "
        "Pass --repo-root or run from the monorepo."
    )


def resolve_path(base: Path, maybe_relative: str, *, repo_root: Path | None = None) -> Path:
    """Resolve a path that may be absolute, repo-relative (projects/...), or base-relative."""
    raw = Path(maybe_relative)
    if raw.is_absolute():
        return raw
    text = maybe_relative.replace("\\", "/")
    if text.startswith("projects/") or text.startswith("schemas/") or text.startswith("Requirement/"):
        root = repo_root or find_repo_root(base)
        return (root / text).resolve()
    return (base / raw).resolve()
