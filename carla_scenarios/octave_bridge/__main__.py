"""octave_bridge entry: cosim twin + plan_tick → vehicle_cmd + optional Foxglove BEV WS."""

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
from octave_bridge.foxglove_ws import FoxgloveBevHub  # noqa: E402
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
        "--foxglove-port",
        type=int,
        default=int(os.environ.get("GF_OCTAVE_BRIDGE_FOXGLOVE_PORT") or "8765"),
        help="Foxglove Studio WebSocket port (BEV). 0 = disable",
    )
    ap.add_argument(
        "--no-foxglove",
        action="store_true",
        help="Disable BEV WebSocket (plan/cmd only)",
    )
    args = ap.parse_args(argv)

    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)

    want_fg = (not args.no_foxglove) and args.foxglove_port > 0
    bev: BevFeed | None = None
    hub: FoxgloveBevHub | None = None
    if want_fg:
        try:
            bev = BevFeed()
            hub = FoxgloveBevHub(host=args.host, port=args.foxglove_port)
            hub.start()
            print(f"[octave_bridge] bev_compose from {bev.gmt_src}", flush=True)
        except (ModuleNotFoundError, OSError) as exc:
            print(f"[octave_bridge] WARN Foxglove/BEV disabled: {exc}", flush=True)
            bev = None
            if hub is not None:
                hub.stop()
            hub = None

    plan_seq = 0
    engine = resolve_engine()
    print(
        f"[octave_bridge] engine={engine} foxglove="
        f"{'ws://127.0.0.1:' + str(args.foxglove_port) if hub else 'off'}",
        flush=True,
    )

    def on_tick(st: BridgeState) -> bytes | None:
        nonlocal plan_seq
        view = build_view(state=st.state, fake_perc=st.fake_perc)
        if st.state is None and st.fake_perc is None:
            return None
        plan_seq += 1
        result = plan_tick(view, seq=plan_seq)
        if bev is not None and hub is not None:
            cam = bev.update(view, result)
            if cam is not None:
                hub.publish_row(cam)
        return result_to_cmd_blob(result, speed_mps=view.ego.speed_mps, seq=plan_seq)

    srv = CosimIoServer(host=args.host, port=args.port, on_tick=on_tick)

    def _watch_stop() -> None:
        while not STOP:
            time.sleep(0.2)
        srv.stop()
        if hub is not None:
            hub.stop()

    import threading

    threading.Thread(target=_watch_stop, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        if hub is not None:
            hub.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
