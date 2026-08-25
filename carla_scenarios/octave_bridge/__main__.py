"""octave_bridge entry: cosim twin + semantic_map + plan_tick + shared BEV feed."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

# Allow `python -m octave_bridge` from carla_scenarios/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from octave_bridge.bev_feed import BevFeed  # noqa: E402
from octave_bridge.io_server import BridgeState, CosimIoServer  # noqa: E402
from octave_bridge.runtime import plan_tick, resolve_engine  # noqa: E402
from octave_bridge.semantic_map import build_view, result_to_cmd_blob  # noqa: E402

STOP = False


def _on_sig(signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    print(f"[octave_bridge] signal {signum}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Host Octave planning bridge (gf_carla_io twin)")
    ap.add_argument("--host", default=os.environ.get("GF_OCTAVE_BRIDGE_HOST", "0.0.0.0"))
    ap.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GF_COSIM_PORT") or os.environ.get("GF_OCTAVE_BRIDGE_PORT") or "7600"),
    )
    ap.add_argument(
        "--bev-out",
        default=os.environ.get("GF_OCTAVE_BRIDGE_BEV", ""),
        help="Optional path to write latest BEV PNG each tick",
    )
    ap.add_argument("--no-bev", action="store_true", help="Skip LiveBevComposer feed")
    args = ap.parse_args(argv)

    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)

    bev: BevFeed | None = None
    if not args.no_bev:
        try:
            bev = BevFeed()
            print(f"[octave_bridge] bev_compose from {bev.gmt_src}", flush=True)
        except ModuleNotFoundError as exc:
            print(f"[octave_bridge] WARN BEV disabled: {exc}", flush=True)
            bev = None
    plan_seq = 0
    engine = resolve_engine()
    print(
        f"[octave_bridge] engine={engine} bev="
        f"{'off' if bev is None else 'shared bev_compose'}",
        flush=True,
    )

    def on_tick(st: BridgeState) -> bytes | None:
        nonlocal plan_seq
        view = build_view(state=st.state, fake_perc=st.fake_perc)
        if st.state is None and st.fake_perc is None:
            return None
        plan_seq += 1
        result = plan_tick(view, seq=plan_seq)
        if bev is not None:
            cam = bev.update(view, result)
            if args.bev_out and cam is not None:
                raw = bev.png_bytes()
                if raw:
                    Path(args.bev_out).write_bytes(raw)
        spd = view.ego.speed_mps
        return result_to_cmd_blob(result, speed_mps=spd, seq=plan_seq)

    srv = CosimIoServer(host=args.host, port=args.port, on_tick=on_tick)

    def _watch_stop() -> None:
        while not STOP:
            time.sleep(0.2)
        srv.stop()

    import threading

    threading.Thread(target=_watch_stop, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
