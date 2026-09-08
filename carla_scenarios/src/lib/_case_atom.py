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
    CarlaSession,
    connect_session,
    duration_s_for_case,
    load_snapshot,
    wait_budget_s,
)
from _case_params import kwargs_for_case
from _instrument import (
    CtrlProbe,
    ego_yaw_rate_degps,
    make_cluster_state,
    mps_to_kph,
    prime_run_meta,
)
from _camera_mount import load_camera_mount
from _traffic import allow_ambient_peds, ensure_ambient_traffic, maintain_ambient_traffic
from _tsr_static_truth import collect_hud_signs
from _verdict import (
    CmdProbe,
    Sample,
    actors_colliding,
    freeze_actors,
    print_verdict,
    run_duration_loop,
    time_headway_s,
)
from _view import ScenarioView, gap_speed, run_loop
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
        session: Optional[CarlaSession] = None,
    ) -> Tuple[int, Optional[ScenarioView]]:
        stop = stop_flag or (lambda: STOP)
        if session is None:
            session = CarlaSession.bind(carla, client, world, load_snapshot())
        snap = session.snap
        meta: dict[str, Any] = {
            "keep_ego": keep_ego,
            "preserve_ego": preserve_ego,
        }
        weather_cfg = None
        if self.weather_preset is not None:
            weather_cfg = load_weather(self.weather_preset, snap=snap)
            apply_weather(world, carla, weather_cfg)
            meta["weather"] = weather_cfg.preset

        from spawn.ic import set_natural_continue

        set_natural_continue(keep_ego)
        t_layout = time.time()
        layout_kw = kwargs_for_case(self.tag)
        try:
            ego, target, layout_meta = self.layout(
                session, keep_ego=keep_ego, **layout_kw
            )
        finally:
            set_natural_continue(False)
        dt_layout = time.time() - t_layout
        meta.update(layout_meta or {})
        if keep_ego:
            meta["natural_continue"] = True
        if weather_cfg is not None:
            apply_wiper(ego, weather_cfg.wiper_speed)
        peds_ok = allow_ambient_peds(self.tag, meta, keep_ego=keep_ego)
        t_seed = time.time()
        ensure_ambient_traffic(
            carla,
            client,
            world,
            near=ego,
            rebuild=not keep_ego,
            log_prefix=f"[{self.tag}]",
            allow_peds=peds_ok,
            fixture=target,
            session=session,
        )
        dt_seed = time.time() - t_seed

        title = self.title or f"AFC {self.tag}"
        print(
            f"[{self.tag}] READY host={snap.host}:{snap.port} "
            f"ego={ego.id} target={getattr(target, 'id', None)} "
            f"duration_s={duration_s} "
            f"keep_ego={int(keep_ego)} preserve_ego={int(preserve_ego)} "
            f"layout_s={dt_layout:0.2f} seed_s={dt_seed:0.2f}",
            flush=True,
        )

        if ensure_view is not None:
            view = ensure_view(
                world,
                ego,
                view,
                no_window=no_window,
                title=title,
                session=session,
            )
        elif view is None and not no_window and snap.view:
            try:
                mount = load_camera_mount()
                view = ScenarioView(
                    world,
                    ego,
                    width=snap.view_w,
                    height=snap.view_h,
                    title=title,
                    camera_mount=mount,
                    chase_cam=snap.chase_cam,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[{self.tag}] pygame unavailable: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                view = None
        if view is not None and hasattr(view, "reset_perf"):
            view.reset_perf()

        samples: list[Sample] = []
        cmd = CmdProbe()
        ctrl = CtrlProbe()
        seq = {"n": 0}
        done = {"hit": False}
        th_lo = float(snap.acc_th_lo)
        th_hi = float(snap.acc_th_hi)

        def tick(elapsed: float) -> None:
            if done["hit"]:
                try:
                    freeze_actors(ego, target, carla_mod=carla, session=session)
                except Exception:  # noqa: BLE001
                    pass
                return
            seq["n"] += 1
            cmd.poll()
            ctrl.poll()
            if self.on_tick is not None:
                self.on_tick(elapsed, ego, target, meta, cmd)
            maintain_ambient_traffic(
                carla,
                client,
                world,
                near=ego,
                fixture=target,
                elapsed_s=elapsed,
                allow_peds=peds_ok,
                log_prefix=f"[{self.tag}]",
                session=session,
            )

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
                    mode = (ctrl.mode or "").upper()
                ttc = None
                if gap > 0.5 and target is not None:
                    closing = es - ls
                    if closing > 0.3:
                        ttc = gap / closing
                signs = collect_hud_signs(ego, world)
                view.set_cluster(
                    make_cluster_state(
                        tag=self.tag,
                        elapsed=elapsed,
                        duration_s=duration_s,
                        ego_mps=es,
                        gap_m=gap,
                        th_s=th,
                        th_lo=th_lo,
                        th_hi=th_hi,
                        ctrl_ok=cmd.seen_control,
                        tgt_kph=tgt,
                        mode=mode,
                        ttc_s=ttc,
                        yaw_rate_degps=ego_yaw_rate_degps(ego),
                        sig=signs.get("sig"),
                        sig_m=signs.get("sig_m"),
                        ped=signs.get("ped"),
                        ped_m=signs.get("ped_m"),
                        limit_kph=signs.get("limit_kph"),
                        meta=meta,
                        alert="HIT" if collided else "",
                    )
                )

            if self.early_exit_on_collision and collided:
                done["hit"] = True
                try:
                    freeze_actors(ego, target, carla_mod=carla, session=session)
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
                freeze_actors(ego, target, carla_mod=carla, session=session)
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
        session = connect_session(wait_s=wait_s, log_prefix=f"[{self.tag}]")
        print(
            f"[{self.tag}] host={session.snap.host}:{session.snap.port} "
            f"tm={session.tm_port}",
            flush=True,
        )
        code, view = self.run_session(
            session.carla,
            session.client,
            session.world,
            period_s=period_s,
            no_window=no_window,
            duration_s=duration_s,
            keep_ego=False,
            session=session,
        )
        if view is not None:
            view.destroy()
        return code

    def main(self, argv: list[str] | None = None) -> int:
        snap = load_snapshot()
        p = argparse.ArgumentParser(description=f"AFC case {self.tag}")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--no-window", action="store_true")
        p.add_argument("--wait-s", type=float, default=None)
        p.add_argument("--period-s", type=float, default=0.05)
        p.add_argument(
            "--duration-s",
            type=float,
            default=duration_s_for_case(
                self.tag, fallback=float(self.default_duration_s), snap=snap
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
        session: Optional[CarlaSession] = None,
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
            session=session,
        )

    return run_session
