#!/usr/bin/env python3
"""gf_frame_ingest Python module runner (carla / isp / replay / colorbar).

When spawned by C++ gf_frame_ingest: use --module-only (parent Created TipChannel).
Standalone: Create slots then run module (dev fallback).
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from gf_channel_py import GfChannel, TipChannel  # noqa: E402

STOP = False


def _on_sig(signum: int, _frame: Any) -> None:
    global STOP
    STOP = True
    print(f"[frame_ingest] signal {signum} → stop", flush=True)


def _env(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    return v if v else default


def _parse_slots() -> List[dict[str, Any]]:
    raw = _env("GF_TIP_SLOTS_JSON", "")
    if raw:
        import json

        try:
            data = json.loads(raw)
            if isinstance(data, list) and data:
                return data
        except json.JSONDecodeError:
            pass
    return [
        {
            "id": _env("GF_TIP_SLOT_ID", "front"),
            "slot_name": _env("GF_TIP_SLOT", "gf.tip.front"),
            "w": int(_env("GF_CARLA_CAM_W", _env("GF_FRAME_W", "640"))),
            "h": int(_env("GF_CARLA_CAM_H", _env("GF_FRAME_H", "480"))),
            "pixel_format": _env("GF_PIXEL_FORMAT", "nv12"),
            "buffers": int(_env("GF_TIP_BUFFERS", "2")),
        }
    ]


def create_slots(slots: List[dict[str, Any]]) -> List[GfChannel]:
    lib = GfChannel.load_lib()
    out: List[GfChannel] = []
    for s in slots:
        name = str(s.get("slot_name") or f"gf.tip.{s.get('id', 'front')}")
        ch = GfChannel.create(
            name,
            int(s["w"]),
            int(s["h"]),
            str(s.get("pixel_format") or "nv12"),
            int(s.get("buffers") or 2),
            lib=lib,
        )
        print(
            f"[frame_ingest] TipChannel created {name} "
            f"{s['w']}x{s['h']} {s.get('pixel_format')} buf={s.get('buffers', 2)}",
            flush=True,
        )
        out.append(ch)
        if name.endswith(".front") or s.get("id") == "front":
            os.environ["GF_TIP_SLOT"] = name
    if out and "GF_TIP_SLOT" not in os.environ:
        os.environ["GF_TIP_SLOT"] = str(
            slots[0].get("slot_name") or f"gf.tip.{slots[0].get('id', 'front')}"
        )
    os.environ["GF_TIP_TRANSPORT"] = _env("GF_TIP_TRANSPORT", "shm")
    return out


def open_front_slot() -> TipChannel:
    slot = _env("GF_TIP_SLOT", "gf.tip.front")
    ch = GfChannel.open(slot)
    print(f"[frame_ingest] TipChannel opened {slot} (module-only)", flush=True)
    return ch


def run_colorbar(channels: List[GfChannel], period_s: float) -> int:
    """Publish a moving color-bar / phase pattern (no camera / no CARLA)."""
    ch = channels[0]
    w = int(_env("GF_CARLA_CAM_W", "640"))
    h = int(_env("GF_CARLA_CAM_H", "480"))
    fmt = _env("GF_PIXEL_FORMAT", "nv12")
    need = w * h + (w * h) // 2 if fmt in ("nv12", "nv21") else w * h * 3
    seq = 0
    print(f"[frame_ingest] module=colorbar period={period_s}s", flush=True)
    while not STOP:
        seq += 1
        phase = seq & 0xFF
        plane = bytes([(phase + i) & 0xFF for i in range(need)])
        ch.publish(plane, time.time_ns(), seq)
        time.sleep(period_s)
    return 0


def run_isp_stub(_channels: List[GfChannel]) -> int:
    print(
        "[frame_ingest] module=isp (stub) — waiting; wire real ISP adapter later",
        flush=True,
    )
    while not STOP:
        time.sleep(1.0)
    return 0


def run_carla_module() -> int:
    bridge = _HERE.parent.parent / "tools" / "carla_bridge" / "carla_bridge.py"
    # Staged share/frame_ingest/modules/carla_bridge
    staged = _HERE / "modules" / "carla_bridge" / "carla_bridge.py"
    if staged.is_file():
        bridge = staged
    if not bridge.is_file():
        print(f"[ERROR] frame_ingest: missing {bridge}", file=sys.stderr, flush=True)
        return 2
    print(f"[frame_ingest] module=carla → {bridge}", flush=True)
    sys.path.insert(0, str(bridge.parent))
    # tip_channel_py for carla_bridge Open path
    sys.path.insert(0, str(_HERE))
    import carla_bridge as cb  # type: ignore  # noqa: E402

    return int(cb.main())


def run_replay_module() -> int:
    replay = _HERE.parent.parent / "tools" / "carla_bridge" / "frame_replay.py"
    staged = _HERE / "modules" / "carla_bridge" / "frame_replay.py"
    if staged.is_file():
        replay = staged
    if not replay.is_file():
        print(f"[ERROR] frame_ingest: missing {replay}", file=sys.stderr, flush=True)
        return 2
    print(f"[frame_ingest] module=replay → {replay}", flush=True)
    sys.path.insert(0, str(replay.parent))
    sys.path.insert(0, str(_HERE))
    import runpy

    sys.argv = [str(replay)] + sys.argv[1:]
    runpy.run_path(str(replay), run_name="__main__")
    return 0


def _normalize_source(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s == "synth":
        return "colorbar"
    if s in ("file",):
        return "replay"
    if s == "carla_file":
        return "carla"
    return s


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Giraffe frame_ingest (tip ingress)")
    p.add_argument(
        "--source",
        default=_env(
            "GF_FRAME_SOURCE",
            _env("GF_TIP_SOURCE", _env("GF_ACTIVE_SOURCE", _env("GF_FRAME_INGEST_SOURCE", "isp"))),
        ),
        choices=["none", "carla", "isp", "replay", "colorbar", "synth", "file", "carla_file"],
    )
    p.add_argument(
        "--module-only",
        action="store_true",
        help="TipChannel already Created by C++ parent; only run module",
    )
    p.add_argument("--dry-run", action="store_true", help="pass through to carla dry-run")
    args, rest = p.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + rest
    if args.dry_run:
        os.environ["GF_CARLA_BRIDGE_DRY_RUN"] = "1"

    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)

    source = _normalize_source(args.source)
    if source == "none":
        print("[frame_ingest] tip_source=none — idle", flush=True)
        while not STOP:
            time.sleep(1.0)
        return 0

    module_only = args.module_only or _env("GF_TIP_INGEST_OWNER") == "cpp"
    channels: List[GfChannel] = []
    try:
        if source in ("colorbar", "isp"):
            if module_only:
                channels = [open_front_slot()]
            else:
                channels = create_slots(_parse_slots())
        elif not module_only:
            # carla/replay Open tip; still Create here when standalone so shm exists
            channels = create_slots(_parse_slots())

        if source == "colorbar":
            return run_colorbar(channels, float(_env("GF_CARLA_DRY_PERIOD_S", "0.04")))
        if source == "carla":
            return run_carla_module()
        if source == "replay":
            return run_replay_module()
        if source == "isp":
            return run_isp_stub(channels)
        print(f"[ERROR] frame_ingest: unknown source={source}", file=sys.stderr)
        return 2
    finally:
        for ch in channels:
            try:
                ch.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
