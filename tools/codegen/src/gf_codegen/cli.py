"""gf-codegen CLI entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gf_codegen import __version__
from gf_codegen.compose.pipeline import compose_project
from gf_codegen.generate_cmd import generate
from gf_codegen.lint_cmd import lint_file
from gf_codegen.paths import find_repo_root
from gf_codegen.suggest_cmd import suggest_wiring


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gf-codegen",
        description="Giraffe Flow SOR compose / lint / generate (host tool)",
    )
    parser.add_argument("--version", action="version", version=f"gf-codegen {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_lint = sub.add_parser("lint", help="Validate a gf.sor.json")
    p_lint.add_argument("sor", type=Path)
    p_lint.add_argument("--schema", type=Path, default=None)
    p_lint.add_argument("--repo-root", type=Path, default=None)

    p_compose = sub.add_parser("compose", help="Compose SOR from a project.yaml")
    p_compose.add_argument("--project", type=Path, required=True)
    p_compose.add_argument("--out", type=Path, default=None)
    p_compose.add_argument("--repo-root", type=Path, default=None)

    p_suggest = sub.add_parser("suggest", help="Suggest wiring fragments")
    sug_sub = p_suggest.add_subparsers(dest="suggest_what", required=True)
    p_sug_w = sug_sub.add_parser("wiring", help="Suggest bindings from hpp structs")
    p_sug_w.add_argument("--project", type=Path, required=True)
    p_sug_w.add_argument("--repo-root", type=Path, default=None)

    p_gen = sub.add_parser("generate", help="Generate minimal C++ headers from SOR")
    p_gen.add_argument("sor", type=Path)
    p_gen.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.cmd == "lint":
        root = args.repo_root
        if root is None:
            try:
                root = find_repo_root(args.sor.parent)
            except FileNotFoundError:
                root = None
        schema = args.schema
        if schema is None and root is not None:
            schema = root / "schemas" / "gf.sor.schema.json"
        return lint_file(args.sor, schema_path=schema)

    if args.cmd == "compose":
        root = args.repo_root.resolve() if args.repo_root else None
        return compose_project(args.project, repo_root=root, out=args.out)

    if args.cmd == "suggest":
        if args.suggest_what == "wiring":
            root = args.repo_root.resolve() if args.repo_root else None
            return suggest_wiring(args.project, repo_root=root)
        return 2

    if args.cmd == "generate":
        return generate(args.sor, args.out)

    return 2


if __name__ == "__main__":
    sys.exit(main())
