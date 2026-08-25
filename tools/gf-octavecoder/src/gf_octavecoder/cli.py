from __future__ import annotations

import argparse
from pathlib import Path

from gf_octavecoder.generate import generate_sku


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="gf-octavecoder",
        description="Generate planning oct_gen/ from octave_planning/*.m (narrow subset).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Write oct_gen under SKU planning app")
    g.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: discover from this package)",
    )
    g.add_argument(
        "--sku",
        required=True,
        choices=("afc", "adc"),
        help="SKU id (octave_planning/<sku> + projects/<sku>/...)",
    )
    g.add_argument(
        "--force",
        action="store_true",
        help="Ignore mtime; rewrite oct_gen",
    )

    args = p.parse_args(argv)
    if args.cmd == "generate":
        root = args.repo_root
        if root is None:
            # tools/gf-octavecoder/src/gf_octavecoder → repo root = parents[4]
            root = Path(__file__).resolve().parents[4]
        return generate_sku(repo_root=root.resolve(), sku=args.sku, force=args.force)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
