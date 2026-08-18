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

def _ipc_default(name: str) -> str:
    """SIL file-IPC under project/runtime_ipc (not /tmp)."""
    import os
    from pathlib import Path
    proj = (os.environ.get("GF_PROJECT_DIR") or "").strip()
    if proj:
        return str(Path(proj) / "runtime_ipc" / name)
    rt = (os.environ.get("GF_RUNTIME_DIR") or "").strip()
    if rt:
        return str(Path(rt) / "var" / name)
    return str(Path("runtime_ipc") / name)


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
        default=Path(os.environ.get("GF_CARLA_FRAME_PATH") or _ipc_default("front.yuv")),
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

    tip_pub = None
    tip_slot = (os.environ.get("GF_CHANNEL_SLOT") or "").strip()
    transport = (os.environ.get("GF_CHANNEL_TRANSPORT") or "shm").strip().lower()
    if tip_slot and transport == "shm":
        try:
            fi = Path(__file__).resolve().parents[2] / "apps" / "frame_ingest"
            if str(fi) not in sys.path:
                sys.path.insert(0, str(fi))
            from gf_channel_py import GfChannel as TipChannel  # noqa: WPS433

            tip_ch = TipChannel.open(tip_slot)
            tip_pub = tip_ch.publish
            print(f"[frame_replay] tip slot {tip_slot}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[frame_replay] tip open failed: {exc}", flush=True)

    # Timebase: prefer recorded deltas; fallback --period-s / GF_CHANNEL_RECORD_FPS.
    record_fps = float(os.environ.get("GF_CHANNEL_RECORD_FPS") or "0")
    use_record_dt = len(rows) >= 2 and all(
        isinstance(r.get("timestamp_ns"), (int, float)) for r in rows[: min(8, len(rows))]
    )

    while not STOP:
        t_wall0 = time.monotonic()
        t_rec0 = int(rows[0].get("timestamp_ns") or 0) if use_record_dt else 0
        for i, row in enumerate(rows):
            if STOP:
                break
            fname = str(row.get("file") or "")
            bin_p = frames_dir / fname
            if not bin_p.is_file():
                continue
            plane = bin_p.read_bytes()
            seq = int(row.get("seq") or 0)
            ts = int(row.get("timestamp_ns") or time.time_ns())
            live_ts = time.time_ns()
            if callable(tip_pub):
                tip_pub(plane, live_ts, seq)
            if transport == "file" or not tip_slot or os.environ.get("GF_TIP_FILE_TEE", "0") == "1":
                atomic_write_bytes(out, plane)
                atomic_write_text(
                    meta_out,
                    json.dumps({"timestamp_ns": live_ts, "seq": seq}, separators=(",", ":")),
                )
            if use_record_dt and i + 1 < len(rows):
                t_next = int(rows[i + 1].get("timestamp_ns") or ts)
                target = t_wall0 + (t_next - t_rec0) / 1e9
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            elif record_fps > 0:
                time.sleep(max(0.001, 1.0 / record_fps))
            else:
                time.sleep(max(0.001, args.period_s))
        if not args.loop:
            break
        print("[frame_replay] loop", flush=True)

    print("[frame_replay] done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
