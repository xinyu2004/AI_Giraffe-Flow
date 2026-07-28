#!/usr/bin/env python3
"""Generate Phase-0 ADAS demo scenarios (ACC / AEB / lane-change) as session JSONL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "gmt" / "src"))

from gf_gmt.adas_scenarios import SCENARIO_GENERATORS, generate_all, write_scenario_jsonl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "projects" / "oem_a" / "afc_with_uss" / "scenarios",
        help="Output directory for *.jsonl",
    )
    ap.add_argument(
        "--only",
        choices=sorted(SCENARIO_GENERATORS.keys()),
        default=None,
        help="Generate a single scenario (default: all three)",
    )
    args = ap.parse_args()
    out_dir: Path = args.out_dir
    if args.only:
        gen = SCENARIO_GENERATORS[args.only]
        path = out_dir / f"{args.only}.jsonl"
        n = write_scenario_jsonl(path, gen())
        print(f"wrote {path} ({n} rows)")
        return 0
    written = generate_all(out_dir)
    for name, path in written.items():
        print(f"wrote {path}")
    print(f"done: {len(written)} scenarios → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
