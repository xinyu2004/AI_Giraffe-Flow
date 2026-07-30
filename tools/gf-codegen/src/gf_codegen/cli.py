"""gf-codegen CLI entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gf_codegen import __version__
from gf_codegen.compose.parse_arxml import parse_arxml_file, to_wiring_fragment
from gf_codegen.emit_idl import write_idl
from gf_codegen.generate_cmd import generate
from gf_codegen.lint_cmd import lint_file
from gf_codegen.paths import find_repo_root
from gf_codegen.suggest_cmd import suggest_wiring


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gf-codegen",
        description=(
            "Giraffe Flow host tool: lint / generate / import / emit-idl. "
            "Compose is done in gf-config (Save) or: python -m gf_codegen.compose"
        ),
    )
    parser.add_argument("--version", action="version", version=f"gf-codegen {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_lint = sub.add_parser("lint", help="Validate a gf.sor.json")
    p_lint.add_argument("sor", type=Path)
    p_lint.add_argument("--schema", type=Path, default=None)
    p_lint.add_argument("--repo-root", type=Path, default=None)

    p_suggest = sub.add_parser("suggest", help="Suggest wiring fragments")
    sug_sub = p_suggest.add_subparsers(dest="suggest_what", required=True)
    p_sug_w = sug_sub.add_parser("wiring", help="Suggest bindings from hpp structs")
    p_sug_w.add_argument("--project", type=Path, required=True)
    p_sug_w.add_argument("--repo-root", type=Path, default=None)

    p_gen = sub.add_parser(
        "generate",
        help="Generate types + Proxy/Skeleton C++ headers from SOR",
    )
    p_gen.add_argument("sor", type=Path)
    p_gen.add_argument("--out", type=Path, required=True)

    p_idl = sub.add_parser(
        "emit-idl",
        help="Emit OMG IDL from SOR types (for CycloneDDS idlc)",
    )
    p_idl.add_argument("sor", type=Path)
    p_idl.add_argument("--out", type=Path, required=True, help="Output directory")
    p_idl.add_argument("--module", type=str, default="gf_types")

    p_imp = sub.add_parser("import", help="Import OEM artifacts into fragment JSON")
    imp_sub = p_imp.add_subparsers(dest="import_what", required=True)
    p_arxml = imp_sub.add_parser("arxml", help="ARXML subset (FARACON-compatible)")
    p_arxml.add_argument("path", type=Path)
    p_arxml.add_argument("--out", type=Path, default=None, help="Write fragment JSON")

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

    if args.cmd == "suggest":
        if args.suggest_what == "wiring":
            root = args.repo_root.resolve() if args.repo_root else None
            return suggest_wiring(args.project, repo_root=root)
        return 2

    if args.cmd == "generate":
        return generate(args.sor, args.out)

    if args.cmd == "emit-idl":
        out = write_idl(args.sor, args.out, module=args.module)
        print(f"wrote {out}")
        return 0

    if args.cmd == "import" and args.import_what == "arxml":
        import json

        parsed = parse_arxml_file(args.path)
        frag = to_wiring_fragment(parsed)
        frag["types"] = parsed.get("types") or []
        frag["services"] = parsed.get("services") or []
        frag["candidates"] = parsed.get("candidates") or []
        text = json.dumps(frag, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(text, end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
