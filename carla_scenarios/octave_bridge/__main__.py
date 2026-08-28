"""octave_bridge entry: cosim twin + plan_tick → vehicle_cmd + optional Foxglove BEV WS."""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import sys
import time
from pathlib import Path

# Allow `python -m octave_bridge` from carla_scenarios/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _proc_util import kill_matching  # noqa: E402
from octave_bridge.bev_feed import BevAsync, BevFeed  # noqa: E402
from octave_bridge.foxglove_ws import FoxgloveBevHub  # noqa: E402
from octave_bridge.io_server import BridgeState, CosimIoServer  # noqa: E402
from octave_bridge.runtime import (  # noqa: E402
    close_octave,
    last_ipc,
    last_plan_timing,
    plan_tick,
    warm_octave,
)
from octave_bridge.semantic_map import build_view, result_to_cmd_blob  # noqa: E402

_LIB = _ROOT / "src" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from _perf import PerfAgg  # noqa: E402

STOP = False
_CLEANED = False


def _on_sig(signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    print(f"[octave_bridge] signal {signum}", flush=True)


_BEV_ASYNC: BevAsync | None = None


def _cleanup(srv: CosimIoServer | None, hub: FoxgloveBevHub | None) -> None:
    global _CLEANED, _BEV_ASYNC
    if _CLEANED:
        return
    _CLEANED = True
    ba = _BEV_ASYNC
    _BEV_ASYNC = None
    if ba is not None:
        ba.stop()
    if srv is not None:
        srv.stop()
    if hub is not None:
        hub.stop()
    close_octave()


def main(argv: list[str] | None = None) -> int:
    global _BEV_ASYNC
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
    ap.add_argument(
        "--no-kill-stale",
        action="store_true",
        help="Do not kill leftover octave_bridge/octave processes before bind",
    )
    args = ap.parse_args(argv)

    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)

    kill_stale = (os.environ.get("GF_OCTAVE_KILL_STALE") or "1").strip().lower() not in (
        "0",
        "off",
        "false",
        "no",
    )
    if args.no_kill_stale:
        kill_stale = False
    if kill_stale:
        # Do not kill giraffe_client here — run_cases owns it; only bridge/octave orphans.
        n1 = kill_matching("octave_bridge", exclude_pid=os.getpid())
        n2 = kill_matching("octave-cli")
        if sys.platform == "win32":
            n2 += kill_matching("octave.exe")
        if n1 or n2:
            print(
                f"[octave_bridge] cleared stale bridge={n1} octave={n2}; wait port",
                flush=True,
            )
            time.sleep(0.5)

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
    perf = PerfAgg("octave")
    budget_s = 0.05
    try:
        budget_s = max(0.01, float(os.environ.get("GF_PLAN_BUDGET_S") or "0.05"))
    except ValueError:
        budget_s = 0.05
    bev_async: BevAsync | None = None
    if bev is not None and hub is not None:
        bev_async = BevAsync(bev, hub)
        _BEV_ASYNC = bev_async
    try:
        warm_octave()
    except Exception as exc:
        print(f"[octave_bridge] ERROR octave warm: {exc}", flush=True)
        _cleanup(None, hub)
        return 1
    print(
        "[octave_bridge] engine=octave (.m) trigger=FAKE_PERC window=1 pack=numeric "
        f"budget={1000.0 * budget_s:.0f}ms foxglove="
        f"{'ws://127.0.0.1:' + str(args.foxglove_port) + ' async' if hub else 'off'}",
        flush=True,
    )

    def on_tick(st: BridgeState) -> bytes | None:
        nonlocal plan_seq
        view = build_view(state=st.state, fake_perc=st.fake_perc)
        if st.state is None and st.fake_perc is None:
            return None
        plan_seq += 1
        result = plan_tick(view, seq=plan_seq)
        wall_s, m_s, ffi_s = last_plan_timing()
        cmd = result_to_cmd_blob(result, speed_mps=view.ego.speed_mps, seq=plan_seq)
        if bev_async is not None:
            bev_async.submit(view, result)
        perf.add("plan", wall_s)
        perf.add("m", m_s)
        perf.add("ffi", ffi_s)
        if wall_s > budget_s:
            perf.count("over_budget")
        extra = {
            "trig": "perc",
            "seq": plan_seq,
            "budget_ms": f"{1000.0 * budget_s:.0f}",
            "ipc": last_ipc(),
        }
        if bev_async is not None:
            extra["bev_drop"] = bev_async.dropped()
        perf.tick(extra=extra)
        return cmd

    srv = CosimIoServer(host=args.host, port=args.port, on_tick=on_tick)
    atexit.register(lambda: _cleanup(srv, hub))

    def _watch_stop() -> None:
        while not STOP:
            time.sleep(0.2)
        _cleanup(srv, hub)

    import threading

    threading.Thread(target=_watch_stop, daemon=True).start()
    try:
        srv.serve_forever()
    except OSError as exc:
        print(
            f"[octave_bridge] ERROR bind/listen {args.host}:{args.port}: {exc}\n"
            "  Port still held by a leftover octave_bridge (or other cosim peer).\n"
            "  Re-run with default --kill-stale, or manually end python/octave processes.",
            flush=True,
        )
        _cleanup(srv, hub)
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup(srv, hub)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
