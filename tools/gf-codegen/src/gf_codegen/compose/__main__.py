"""Headless compose for CI / scripts (not the public gf-codegen CLI).

Usage (repo root, venv active):

  python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml

Authors should prefer gf-config: Save → auto compose; Generate (Ctrl+G) for C++ APIs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gf_codegen.compose.pipeline import compose_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m gf_codegen.compose",
        description="Headless compose (CI). Prefer gf-config Save for authoring.",
    )
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve() if args.repo_root else None
    return compose_project(args.project, repo_root=root, out=args.out)


if __name__ == "__main__":
    sys.exit(main())
