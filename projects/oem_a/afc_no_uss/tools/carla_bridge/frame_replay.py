#!/usr/bin/env python3
"""Replay recorded tip frames into the live tip path (inject + images).

Reads a frame volume written by carla_bridge (GF_RECORD_FRAMES_DIR):
  stream.json          {"format","w","h"}
  frames.jsonl         {"seq","timestamp_ns","file"}
  NNNNNNNN.bin         planar bytes

Writes the same tip protocol consumers expect (stream + meta + plane).
Mutual exclusion: use with ego_source=inject (gateway Ego off).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

STOP = False


def _on_signal(signum: int, _frame: Any) -> None:
    global STOP
    STOP = True
    print(f"[frame_replay] signal {signum} → stop", flush=True)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Replay tip frame volume → live tip path")
    p.add_argument("--frames-dir", required=True, type=Path)
    p.add_argument(
        "--frame-path",
        type=Path,
        default=Path(os.environ.get("GF_CARLA_FRAME_PATH") or "/tmp/gf_front.yuv"),
    )
    p.add_argument("--loop", action="store_true", default=os.environ.get("GF_INJECT_LOOP") == "1")
    p.add_argument("--period-s", type=float, default=float(os.environ.get("GF_FRAME_REPLAY_PERIOD_S") or "0.05"))
    args = p.parse_args(argv)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    frames_dir: Path = args.frames_dir
    stream_p = frames_dir / "stream.json"
    index_p = frames_dir / "frames.jsonl"
    if not stream_p.is_file() or not index_p.is_file():
        print(f"[frame_replay] missing stream/frames under {frames_dir}", file=sys.stderr)
        return 2

    stream = json.loads(stream_p.read_text(encoding="utf-8"))
    out = args.frame_path
    stream_out = out.with_name(out.stem + ".stream.json")
    meta_out = out.with_name(out.stem + ".meta.json")
    atomic_write_text(stream_out, json.dumps(stream, separators=(",", ":")))

    rows: list[dict[str, Any]] = []
    for line in index_p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        print("[frame_replay] empty frames.jsonl", file=sys.stderr)
        return 2

    print(
        f"[frame_replay] {len(rows)} frames → {out} fmt={stream.get('format')} "
        f"loop={int(args.loop)}",
        flush=True,
    )

    while not STOP:
        for row in rows:
            if STOP:
                break
            fname = str(row.get("file") or "")
            bin_p = frames_dir / fname
            if not bin_p.is_file():
                continue
            plane = bin_p.read_bytes()
            seq = int(row.get("seq") or 0)
            ts = int(row.get("timestamp_ns") or time.time_ns())
            # Use wall clock for live consumers; keep seq from recording.
            live_ts = time.time_ns()
            atomic_write_bytes(out, plane)
            atomic_write_text(
                meta_out,
                json.dumps({"timestamp_ns": live_ts, "seq": seq}, separators=(",", ":")),
            )
            time.sleep(max(0.001, args.period_s))
        if not args.loop:
            break
        print("[frame_replay] loop", flush=True)

    print("[frame_replay] done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
