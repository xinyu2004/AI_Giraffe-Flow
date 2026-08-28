"""Shared scheme-1 atom runner for AFC cases (place/IC; Giraffe owns ego)."""

from __future__ import annotations

import argparse
import math
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple

from _carla_env import (
    carla_host,
    carla_port,
    connect_world,
    duration_s_for_case,
    load_local_env,
    wait_budget_s,
)
from _instrument import (
    CtrlProbe,
    ego_yaw_rate_degps,
    infer_cluster_template,
    make_cluster_state,
    mps_to_kph,
    prime_run_meta,
)
from _camera_mount import load_camera_mount
from _traffic import ensure_ambient_traffic
from _verdict import (
    CmdProbe,
    Sample,
    actors_colliding,
    freeze_actors,
    print_verdict,
    run_duration_loop,
    time_headway_s,
)
from _view import ScenarioView, gap_speed, run_loop, scenario_view_wanted
from _weather import apply_weather, apply_wiper, load_weather

STOP = False

LayoutFn = Callable[..., Tuple[Any, Optional[Any], dict[str, Any]]]
JudgeFn = Callable[
    [list[Sample], bool, dict[str, Any]], Tuple[bool, str, dict[str, Any]]
]
TickHook = Callable[[float, Any, Optional[Any], dict[str, Any], CmdProbe], None]


def _on_sig(signum: int, _frame: object) -> None:
    global STOP
    STOP = True


@dataclass
class AtomCase:
    """Declarative atom: layout + optional weather + judge."""

    tag: str
    layout: LayoutFn
    judge: JudgeFn
    weather_preset: Optional[str] = None
    early_exit_on_collision: bool = False
    title: str = ""
    hud_lines: list[str] = field(default_factory=list)  # unused; cluster replaces HUD
    on_tick: Optional[TickHook] = None
    default_duration_s: float = 10.0
    cluster_template: Optional[str] = None  # None → infer from tag

    def run_dry(self, duration_s: float, period_s: float) -> int:
        print(
            f"[{self.tag}] explicit --dry-run: no CARLA / no file IPC",
            flush=True,
        )
        print(f"[{self.tag}] READY dry-run", flush=True)
        t0 = time.time()
        while not STOP and (time.time() - t0) < duration_s:
            time.sleep(period_s)
        print_verdict(self.tag, False, "no_giraffe_control", mode="dry-run")
        return 1

    def run_session(
        self,
        carla: Any,
        client: Any,
        world: Any,
        *,
        period_s: float,
        no_window: bool,
        duration_s: float,
        view: Optional[ScenarioView] = None,
        keep_ego: bool = False,
        preserve_ego: bool = False,
        stop_flag: Optional[Callable[[], bool]] = None,
        ensure_view: Optional[Callable[..., Optional[ScenarioView]]] = None,
    ) -> Tuple[int, Optional[ScenarioView]]:
        stop = stop_flag or (lambda: STOP)
        load_local_env()
        mount = load_camera_mount()
        meta: dict[str, Any] = {
            "keep_ego": keep_ego,
            "preserve_ego": preserve_ego,
        }
        weather_cfg = None
        if self.weather_preset is not None:
            weather_cfg = load_weather(self.weather_preset)
            apply_weather(world, carla, weather_cfg)
            meta["weather"] = weather_cfg.preset

        # keep_ego = continue pose (skip hero IC). preserve_ego = don't destroy at end.
        from spawn.ic import set_natural_continue

        set_natural_continue(keep_ego)
        try:
            ego, target, layout_meta = self.layout(
                carla, client, world, keep_ego=keep_ego
            )
        finally:
            set_natural_continue(False)
        meta.update(layout_meta or {})
        if keep_ego:
            meta["natural_continue"] = True
        if weather_cfg is not None:
            apply_wiper(ego, weather_cfg.wiper_speed)
        ensure_ambient_traffic(
            carla, client, world, near=ego, log_prefix=f"[{self.tag}]"
        )

        title = self.title or f"AFC {self.tag}"
        print(
            f"[{self.tag}] READY host={carla_host()}:{carla_port()} "
            f"ego={ego.id} target={getattr(target, 'id', None)} "
            f"duration_s={duration_s} mount_ref={mount.describe()} "
            f"keep_ego={int(keep_ego)} preserve_ego={int(preserve_ego)}",
            flush=True,
        )

        if ensure_view is not None:
            view = ensure_view(
                world, ego, view, no_window=no_window, title=title
            )
        elif view is None and not no_window and scenario_view_wanted():
            try:
                view = ScenarioView(
                    world,
                    ego,
                    width=int(os.environ.get("GF_SCENARIO_VIEW_W") or "960"),
                    height=int(os.environ.get("GF_SCENARIO_VIEW_H") or "540"),
                    title=title,
                    camera_mount=mount,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[{self.tag}] pygame unavailable: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                view = None

        samples: list[Sample] = []
        cmd = CmdProbe()
        ctrl = CtrlProbe()
        seq = {"n": 0}
        done = {"hit": False}
        tmpl = self.cluster_template or infer_cluster_template(self.tag)
        th_lo = float(os.environ.get("GF_ACC_TH_LO") or "1.0")
        th_hi = float(os.environ.get("GF_ACC_TH_HI") or "2.5")

        def tick(elapsed: float) -> None:
            # Giraffe may keep sending throttle after a hit — re-assert freeze every frame.
            if done["hit"]:
                try:
                    freeze_actors(ego, target, carla_mod=carla)
                except Exception:  # noqa: BLE001
                    pass
                return
            seq["n"] += 1
            cmd.poll()
            ctrl.poll()
            if self.on_tick is not None:
                self.on_tick(elapsed, ego, target, meta, cmd)

            if target is not None:
                gap, es, ls, rel = gap_speed(ego, target)
                collided = actors_colliding(ego, target)
            else:
                ev = ego.get_velocity()
                es = math.sqrt(ev.x**2 + ev.y**2 + ev.z**2)
                gap, ls, rel, collided = 0.0, 0.0, 0.0, False
            th = time_headway_s(gap, es) if gap > 0 else None
            samples.append(
                Sample(
                    t=elapsed,
                    gap_m=gap,
                    ego_mps=es,
                    lead_mps=ls,
                    rel_mps=rel,
                    th_s=th or 0.0,
                    collided=collided,
                )
            )
            if view is not None:
                tgt = None
                mode = ""
                if ctrl.seen and ctrl.target_speed_mps is not None:
                    tgt = mps_to_kph(ctrl.target_speed_mps)
                    mode = (ctrl.mode or tmpl).upper()
                elif cmd.seen_control:
                    mode = tmpl.upper()
                ttc = None
                if tmpl == "aeb" and gap > 0:
                    closing = max(0.1, es - ls) if target is not None else max(0.1, es)
                    ttc = gap / closing
                yaw = ego_yaw_rate_degps(ego) if tmpl == "lateral" else None
                view.set_cluster(
                    make_cluster_state(
                        tag=self.tag,
                        template=tmpl,
                        elapsed=elapsed,
                        duration_s=duration_s,
                        ego_mps=es,
                        gap_m=gap,
                        th_s=th if tmpl in ("acc", "follow") else None,
                        th_lo=th_lo,
                        th_hi=th_hi,
                        ctrl_ok=cmd.seen_control,
                        tgt_kph=tgt,
                        mode=mode,
                        ttc_s=ttc,
                        yaw_rate_degps=yaw,
                        meta=meta,
                        alert="AEB" if (tmpl == "aeb" and collided) else "",
                    )
                )

            if self.early_exit_on_collision and collided:
                done["hit"] = True
                try:
                    freeze_actors(ego, target, carla_mod=carla)
                except Exception:  # noqa: BLE001
                    pass
                print(
                    f"[{self.tag}] collision at t={elapsed:.2f}s gap={gap:.2f}m "
                    f"→ freeze + early-exit (hold brake vs Giraffe)",
                    flush=True,
                )

        try:
            if view is not None:
                t0 = time.time()

                def _tick() -> None:
                    tick(time.time() - t0)

                run_loop(
                    stop_flag=lambda: stop()
                    or done["hit"]
                    or (time.time() - t0) >= duration_s,
                    tick=_tick,
                    view=view,
                    period_s=period_s,
                )
            else:
                run_duration_loop(
                    duration_s=duration_s,
                    period_s=period_s,
                    stop_flag=lambda: stop() or done["hit"],
                    on_tick=tick,
                )
        except Exception:
            raise

        if done["hit"]:
            try:
                freeze_actors(ego, target, carla_mod=carla)
            except Exception:  # noqa: BLE001
                pass

        ok, reason, extra = self.judge(samples, cmd.seen_control, meta)
        extra = {
            **extra,
            "cmd_fresh": cmd.fresh_count,
            "n": len(samples),
            **{k: v for k, v in meta.items() if isinstance(v, (int, float, str, bool))},
        }
        print_verdict(self.tag, ok, reason, **extra)
        # Batch passes preserve_ego=True so the next case can continue the same hero.
        # Single-run leaves UE clean for the next standalone script / bridge remount.
        if not preserve_ego:
            try:
                from spawn.roles import ROLE_EGO, ROLE_LEAD, destroy_role

                destroy_role(world, ROLE_LEAD)
                destroy_role(world, ROLE_EGO)
                print(
                    f"[{self.tag}] cleanup: destroyed leftover hero/lead "
                    f"(preserve_ego=0)",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[{self.tag}] cleanup warn: {type(exc).__name__}: {exc}",
                    flush=True,
                )
        return (0 if ok else 1), view

    def run_carla(
        self,
        period_s: float,
        *,
        no_window: bool,
        wait_s: float,
        duration_s: float,
    ) -> int:
        carla, client, world = connect_world(
            wait_s=wait_s, log_prefix=f"[{self.tag}]"
        )
        print(f"[{self.tag}] host={carla_host()}:{carla_port()}", flush=True)
        code, view = self.run_session(
            carla,
            client,
            world,
            period_s=period_s,
            no_window=no_window,
            duration_s=duration_s,
            keep_ego=False,
        )
        if view is not None:
            view.destroy()
        return code

    def main(self, argv: list[str] | None = None) -> int:
        p = argparse.ArgumentParser(description=f"AFC case {self.tag}")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--no-window", action="store_true")
        p.add_argument("--wait-s", type=float, default=None)
        p.add_argument("--period-s", type=float, default=0.05)
        p.add_argument(
            "--duration-s",
            type=float,
            default=duration_s_for_case(
                self.tag, fallback=float(self.default_duration_s)
            ),
        )
        args = p.parse_args(argv)
        signal.signal(signal.SIGINT, _on_sig)
        signal.signal(signal.SIGTERM, _on_sig)
        prime_run_meta(self.tag)

        if args.dry_run or os.environ.get("GF_SCENARIO_DRY_RUN") == "1":
            return self.run_dry(args.duration_s, args.period_s)
        try:
            return self.run_carla(
                args.period_s,
                no_window=args.no_window,
                wait_s=wait_budget_s(args.wait_s),
                duration_s=max(1.0, args.duration_s),
            )
        except RuntimeError as exc:
            print(f"[{self.tag}] FATAL: {exc}", file=sys.stderr, flush=True)
            print_verdict(self.tag, False, "infra_error")
            return 2


def bind_run_session(case: AtomCase) -> Callable[..., Tuple[int, Optional[ScenarioView]]]:
    """Expose run_session(*args) matching run_cases.py contract."""

    def run_session(
        carla: Any,
        client: Any,
        world: Any,
        *,
        period_s: float,
        no_window: bool,
        duration_s: float,
        view: Optional[ScenarioView] = None,
        keep_ego: bool = False,
        preserve_ego: bool = False,
        stop_flag: Optional[Callable[[], bool]] = None,
        ensure_view: Optional[Callable[..., Optional[ScenarioView]]] = None,
    ) -> Tuple[int, Optional[ScenarioView]]:
        return case.run_session(
            carla,
            client,
            world,
            period_s=period_s,
            no_window=no_window,
            duration_s=duration_s,
            view=view,
            keep_ego=keep_ego,
            preserve_ego=preserve_ego,
            stop_flag=stop_flag,
            ensure_view=ensure_view,
        )

    return run_session
