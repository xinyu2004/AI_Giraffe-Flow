#!/usr/bin/env python3
"""Play an ADAS scenario JSONL to stdout (NDJSON) with synthetic BEV frames.

Typical:
  python scripts/gen_adas_scenarios.py
  python scripts/play_adas_demo.py projects/oem_a/afc_with_uss/scenarios/aeb_cutin.jsonl \\
    | GMT bridge foxglove --ws --stdin --host 127.0.0.1 --port 8765

GMT GUI (numbers):
  GMT gui --session projects/oem_a/afc_with_uss/scenarios/aeb_cutin.jsonl \\
    --project projects/oem_a/afc_with_uss
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "gmt" / "src"))

from gf_gmt.adas_scenarios import iter_playback_rows  # noqa: E402
from gf_gmt.bridge_foxglove import rows_from_jsonl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", type=Path, help="Scenario session JSONL")
    ap.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback rate (1.0 = realtime)",
    )
    ap.add_argument(
        "--no-bev",
        action="store_true",
        help="Do not synthesize /gf/camera/front/compressed",
    )
    ap.add_argument(
        "--loop",
        action="store_true",
        help="Repeat until Ctrl+C",
    )
    args = ap.parse_args()
    path: Path = args.jsonl
    if not path.is_file():
        print(f"missing scenario: {path}", file=sys.stderr)
        print("run: python scripts/gen_adas_scenarios.py", file=sys.stderr)
        return 1

    rows = rows_from_jsonl(path)
    if not rows:
        print(f"empty scenario: {path}", file=sys.stderr)
        return 1

    speed = max(0.05, float(args.speed))
    print(
        f"[play_adas_demo] {path.name} rows={len(rows)} speed={speed} "
        f"bev={not args.no_bev} → stdout NDJSON",
        file=sys.stderr,
        flush=True,
    )

    try:
        while True:
            t0 = int(rows[0].get("t_ns") or 0)
            wall0 = time.monotonic()
            for out in iter_playback_rows(rows, synth_bev=not args.no_bev):
                t_ns = int(out.get("t_ns") or 0)
                delay = max(
                    0.0,
                    ((t_ns - t0) / 1e9) / speed - (time.monotonic() - wall0),
                )
                if delay > 0:
                    time.sleep(min(delay, 0.5))
                sys.stdout.write(
                    json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
                sys.stdout.flush()
            if not args.loop:
                break
            print("[play_adas_demo] loop", file=sys.stderr, flush=True)
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        print("\n[play_adas_demo] stopped", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
