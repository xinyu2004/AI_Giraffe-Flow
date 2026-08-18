"""Shared weather + straight-follow case (ACC headway verdict; ego by Giraffe)."""

from __future__ import annotations

import argparse
import math
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

_AFC = Path(__file__).resolve().parents[2]
_SRC = _AFC / "src"
_LIB = _SRC / "lib"
for _p in (_AFC, _SRC, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _carla_env import (  # noqa: E402
    carla_host,
    carla_port,
    connect_world,
    load_local_env,
    wait_budget_s,
)
from _instrument import (  # noqa: E402
    CtrlProbe,
    make_cluster_state,
    mps_to_kph,
    prime_run_meta,
)
from _camera_mount import load_camera_mount  # noqa: E402
from _traffic import ensure_ambient_traffic  # noqa: E402
from _truth import write_truth  # noqa: E402
from _verdict import (  # noqa: E402
    CmdProbe,
    Sample,
    actors_colliding,
    print_verdict,
    time_headway_s,
)
from _view import ScenarioView, gap_speed, run_loop  # noqa: E402
from _weather import apply_weather, apply_wiper, load_weather  # noqa: E402
from layouts.follow_straight import layout_acc_follow  # noqa: E402
from judges.acc_headway import judge_acc  # noqa: E402

STOP = False


def _on_sig(signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def run_dry(tag: str, duration_s: float, period_s: float) -> int:
    print(f"[{tag}] explicit --dry-run: truth tip only (no closed loop)", flush=True)
    print(f"[{tag}] READY dry-run", flush=True)
    t0 = time.time()
    seq = 0
    while not STOP and (time.time() - t0) < duration_s:
        seq += 1
        elapsed = time.time() - t0
        write_truth(
            scenario=tag,
            lead_distance_m=28.0 + 6.0 * math.sin(elapsed * 0.35),
            lead_rel_speed_mps=-0.5,
            seq=seq,
        )
        time.sleep(period_s)
    print_verdict(tag, False, "no_giraffe_control", mode="dry-run")
    return 1


def run_session(
    tag: str,
    period_s: float,
    *,
    carla: Any,
    client: Any,
    world: Any,
    view: Optional[ScenarioView],
    no_window: bool,
    duration_s: float,
    preset: str,
    keep_ego: bool = False,
    stop_flag: Optional[Callable[[], bool]] = None,
    ensure_view: Optional[Callable[..., Optional[ScenarioView]]] = None,
) -> Tuple[int, Optional[ScenarioView]]:
    """Scheme-1 session on an existing world (daemon or CLI)."""
    stop = stop_flag or (lambda: STOP)
    load_local_env()
    cfg = load_weather(preset)
    apply_weather(world, carla, cfg)
    mount = load_camera_mount()
    ego, lead, _meta = layout_acc_follow(
        carla, client, world, lead_gap_m=32.0, keep_ego=keep_ego
    )
    apply_wiper(ego, cfg.wiper_speed)
    ensure_ambient_traffic(carla, client, world, near=ego, log_prefix=f"[{tag}]")

    print(
        f"[{tag}] READY host={carla_host()}:{carla_port()} "
        f"ego={ego.id} lead={lead.id} duration_s={duration_s} "
        f"weather={cfg.describe()} tip_ref={mount.describe()}",
        flush=True,
    )

    if ensure_view is not None:
        view = ensure_view(
            world, ego, view, no_window=no_window, title=f"AFC {tag} — weather"
        )
    elif view is None and not no_window:
        try:
            view = ScenarioView(
                world,
                ego,
                width=int(os.environ.get("GF_SCENARIO_VIEW_W") or "960"),
                height=int(os.environ.get("GF_SCENARIO_VIEW_H") or "540"),
                title=f"AFC {tag} — weather follow",
                camera_mount=mount,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[{tag}] pygame unavailable: {type(exc).__name__}: {exc}", flush=True)
            view = None

    samples: list[Sample] = []
    cmd = CmdProbe()
    ctrl = CtrlProbe()
    seq = {"n": 0}
    th_lo = float(os.environ.get("GF_ACC_TH_LO") or "1.0")
    th_hi = float(os.environ.get("GF_ACC_TH_HI") or "2.5")

    def tick(elapsed: float) -> None:
        seq["n"] += 1
        cmd.poll()
        ctrl.poll()
        gap, es, ls, rel = gap_speed(ego, lead)
        th = time_headway_s(gap, es)
        collided = actors_colliding(ego, lead)
        samples.append(
            Sample(
                t=elapsed,
                gap_m=gap,
                ego_mps=es,
                lead_mps=ls,
                rel_mps=rel,
                th_s=th,
                collided=collided,
            )
        )
        write_truth(
            scenario=tag,
            lead_distance_m=gap,
            lead_rel_speed_mps=rel,
            seq=seq["n"],
            ego_mps=es,
            th_s=th,
            t_s=elapsed,
            duration_s=duration_s,
        )
        if view is not None:
            tgt = None
            mode = "ACC"
            if ctrl.seen and ctrl.target_speed_mps is not None:
                tgt = mps_to_kph(ctrl.target_speed_mps)
                if ctrl.mode:
                    mode = ctrl.mode.upper()
            view.set_cluster(
                make_cluster_state(
                    tag=tag,
                    template="acc",
                    elapsed=elapsed,
                    duration_s=duration_s,
                    ego_mps=es,
                    gap_m=gap,
                    th_s=th,
                    th_lo=th_lo,
                    th_hi=th_hi,
                    ctrl_ok=cmd.seen_control,
                    tgt_kph=tgt,
                    mode=mode if cmd.seen_control else "",
                    meta={"weather": cfg.preset},
                )
            )

    try:
        if view is not None:
            t0 = time.time()

            def _tick() -> None:
                tick(time.time() - t0)

            run_loop(
                stop_flag=lambda: stop() or (time.time() - t0) >= duration_s,
                tick=_tick,
                view=view,
                period_s=period_s,
            )
        else:
            from _verdict import run_duration_loop

            run_duration_loop(
                duration_s=duration_s,
                period_s=period_s,
                stop_flag=stop,
                on_tick=tick,
            )
    except Exception:
        raise

    ok, reason, extra = judge_acc(
        samples, seen_control=cmd.seen_control, th_lo=th_lo, th_hi=th_hi
    )
    extra = {
        **extra,
        "cmd_fresh": cmd.fresh_count,
        "n": len(samples),
        "weather": cfg.preset,
        "wiper": cfg.wiper_speed,
    }
    print_verdict(tag, ok, reason, **extra)
    return (0 if ok else 1), view


def run_carla(
    tag: str,
    period_s: float,
    *,
    no_window: bool,
    wait_s: float,
    duration_s: float,
    preset: str,
) -> int:
    carla, client, world = connect_world(wait_s=wait_s, log_prefix=f"[{tag}]")
    print(f"[{tag}] host={carla_host()}:{carla_port()}", flush=True)
    code, view = run_session(
        tag,
        period_s,
        carla=carla,
        client=client,
        world=world,
        view=None,
        no_window=no_window,
        duration_s=duration_s,
        preset=preset,
        keep_ego=False,
    )
    if view is not None:
        view.destroy()
    return code


def main(tag: str, preset: str, argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=f"AFC weather case {tag}")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-window", action="store_true")
    p.add_argument("--wait-s", type=float, default=None)
    p.add_argument("--period-s", type=float, default=0.05)
    p.add_argument(
        "--duration-s",
        type=float,
        default=float(os.environ.get("GF_SCENARIO_DURATION_S") or "10"),
    )
    args = p.parse_args(argv)
    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)
    prime_run_meta(tag, keyword="ENV")

    if args.dry_run or os.environ.get("GF_SCENARIO_DRY_RUN") == "1":
        return run_dry(tag, args.duration_s, args.period_s)
    try:
        return run_carla(
            tag,
            args.period_s,
            no_window=args.no_window,
            wait_s=wait_budget_s(args.wait_s),
            duration_s=max(1.0, args.duration_s),
            preset=preset,
        )
    except RuntimeError as exc:
        print(f"[{tag}] FATAL: {exc}", file=sys.stderr, flush=True)
        print_verdict(tag, False, "infra_error")
        return 2
