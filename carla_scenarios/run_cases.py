#!/usr/bin/env python3
"""AFC batch runner — long-lived Client A (NOT systemd).

One CARLA connection + one pygame window across cases (scheme-1: place/IC;
Giraffe owns continuous ego control). Same UE RPC port as carla_bridge.

Writes results only for batch runs (this script), under::

  results/runs/<YYYYMMDD_HHMMSS>/{summary.json,cases/<id>.json}

Single-case scripts (e.g. cases/longitudinal/acc.py) do **not** write results.

Usage::

  cd carla_scenarios
  python3 run_cases.py cases/longitudinal
  python3 run_cases.py   # root suite
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, List

_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "src"
_LIB = _SRC / "lib"
for _p in (_HERE, _SRC, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _proc_util import kill_matching, kill_proc_tree  # noqa: E402

from _carla_env import (  # noqa: E402
    carla_host,
    carla_port,
    connect_world,
    duration_s_for_case,
    load_local_env,
    wait_budget_s,
)
from _manifest import resolve_targets  # noqa: E402
from _camera_mount import load_camera_mount  # noqa: E402
from _view import ScenarioView  # noqa: E402
from spawn.ic import set_natural_continue  # noqa: E402
from spawn.boundary import reset_wrecked_ego  # noqa: E402
from spawn.roles import ROLE_EGO, find_by_role  # noqa: E402

STOP = False
_GIRAFFE_CLIENT_PROC: Optional[subprocess.Popen[Any]] = None


def _on_sig(signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    print(f"[run_cases] signal {signum} → stop", flush=True)


def _start_giraffe_client() -> None:
    """scenario_client 一键拉起 giraffe_client（用户无感两个 Client）。"""
    global _GIRAFFE_CLIENT_PROC
    flag = (os.environ.get("GF_START_GIRAFFE_CLIENT") or "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        print("[run_cases] GF_START_GIRAFFE_CLIENT=0 → skip giraffe_client", flush=True)
        return
    if _GIRAFFE_CLIENT_PROC is not None and _GIRAFFE_CLIENT_PROC.poll() is None:
        return
    # Prior Ctrl+C often left an orphaned giraffe_client (own session).
    n = kill_matching("giraffe_client")
    if n:
        print(f"[run_cases] cleared {n} stale giraffe_client before start", flush=True)
        time.sleep(0.4)
    cmd = [sys.executable, "-m", "giraffe_client"]
    log_path = _HERE / "results" / "giraffe_client.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    log_f.write(f"\n--- run_cases spawn {datetime.now().isoformat()} ---\n")
    log_f.flush()
    _GIRAFFE_CLIENT_PROC = subprocess.Popen(
        cmd,
        cwd=str(_HERE),
        env=os.environ.copy(),
        stdout=log_f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(
        f"[run_cases] started giraffe_client pid={_GIRAFFE_CLIENT_PROC.pid} "
        f"log={log_path}",
        flush=True,
    )


def _stop_giraffe_client() -> None:
    global _GIRAFFE_CLIENT_PROC
    proc = _GIRAFFE_CLIENT_PROC
    _GIRAFFE_CLIENT_PROC = None
    kill_proc_tree(proc, name="giraffe_client")
    # Belt-and-suspenders: orphans from older sessions.
    kill_matching("giraffe_client")


def _load_py(path: Path) -> Any:
    name = f"afc_case_{path.stem}_{abs(hash(str(path))) % 10**8}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_view(
    world: Any,
    ego: Any,
    view: Optional[ScenarioView],
    *,
    no_window: bool,
    title: str,
) -> Optional[ScenarioView]:
    if no_window:
        return None
    mount = load_camera_mount()
    if view is not None:
        try:
            if int(getattr(view._vehicle, "id", -1)) == int(getattr(ego, "id", -2)):
                return view
        except Exception:  # noqa: BLE001
            pass
        # Same window: only remount chase sensors onto the new hero.
        try:
            view.retarget_vehicle(ego)
            return view
        except Exception as exc:  # noqa: BLE001
            print(f"[run_cases] view retarget failed: {exc}; recreating", flush=True)
            try:
                view.destroy()
            except Exception:  # noqa: BLE001
                pass
    try:
        v = ScenarioView(
            world,
            ego,
            width=int(os.environ.get("GF_SCENARIO_VIEW_W") or "960"),
            height=int(os.environ.get("GF_SCENARIO_VIEW_H") or "540"),
            title=title,
            camera_mount=mount,
        )
        print("[run_cases] pygame window open (reused across cases)", flush=True)
        return v
    except Exception as exc:  # noqa: BLE001
        print(f"[run_cases] pygame unavailable: {exc}", flush=True)
        return None


def _write_results(
    *,
    run_dir: Path,
    case_rows: list[dict[str, Any]],
    passed_ids: list[str],
    failed_ids: list[str],
    skipped_rest: list[str],
    planned_skip: int,
    runnable_n: int,
    stop_on_fail: bool,
    duration_s: float,
    host: str,
    port: int,
) -> None:
    cases_dir = run_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    for row in case_rows:
        cid = str(row["id"])
        (cases_dir / f"{cid}.json").write_text(
            json.dumps(row, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    summary = {
        "timestamp": run_dir.name,
        "host": host,
        "port": port,
        "duration_s": duration_s,
        "stop_on_fail": stop_on_fail,
        "runnable": runnable_n,
        "planned_skipped": planned_skip,
        "passed": passed_ids,
        "failed": failed_ids,
        "skipped_remaining": skipped_rest,
        "passed_n": len(passed_ids),
        "failed_n": len(failed_ids),
        "cases": case_rows,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    latest = _HERE / "results" / "latest.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        json.dumps(
            {"run_dir": str(run_dir.relative_to(_HERE)), **summary},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[run_cases] results → {run_dir}", flush=True)


def main(argv: list[str] | None = None) -> int:
    load_local_env()
    p = argparse.ArgumentParser(
        description="AFC run_cases — long-lived Client A (not systemd)"
    )
    p.add_argument(
        "targets",
        nargs="*",
        help="Directory with manifest.yaml (default: cwd / carla_scenarios)",
    )
    p.add_argument(
        "--duration-s",
        type=float,
        default=float(os.environ.get("GF_SCENARIO_DURATION_S") or "8"),
        help="Per-case duration (default GF_SCENARIO_DURATION_S in carla.env)",
    )
    p.add_argument("--period-s", type=float, default=0.05)
    p.add_argument("--no-window", action="store_true")
    p.add_argument("--wait-s", type=float, default=None)
    p.add_argument("--include-planned", action="store_true")
    p.add_argument(
        "--stop-on-fail",
        action="store_true",
        help="Stop after first failing case (same as GF_SCENARIO_STOP_ON_FAIL=1)",
    )
    p.add_argument(
        "--no-results",
        action="store_true",
        help="Do not write results/ report (same as GF_SCENARIO_WRITE_RESULTS=0)",
    )
    args = p.parse_args(argv)
    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)

    env_stop = (os.environ.get("GF_SCENARIO_STOP_ON_FAIL") or "0").strip()
    stop_on_fail = bool(args.stop_on_fail) or env_stop in ("1", "true", "yes", "on")
    env_results = (os.environ.get("GF_SCENARIO_WRITE_RESULTS") or "1").strip().lower()
    write_results = (not args.no_results) and env_results not in (
        "0",
        "false",
        "no",
        "off",
    )

    try:
        cases = resolve_targets(list(args.targets or []))
    except (FileNotFoundError, ValueError) as exc:
        print(f"[run_cases] ERROR: {exc}", flush=True)
        return 2

    runnable: list[tuple[str, Path, str]] = []
    planned_skip = 0
    for c in cases:
        status = str(c.get("status") or "active")
        if status == "planned" and not args.include_planned:
            planned_skip += 1
            continue
        script = c.get("_script_path") or (Path(c["_dir"]) / str(c.get("script") or ""))
        script = Path(script)
        if not script.is_file():
            print(f"[run_cases] skip {c.get('id')}: missing {script}", flush=True)
            continue
        runnable.append((str(c.get("id")), script, str(c.get("keyword") or "")))

    if not runnable:
        print("[run_cases] no runnable cases", flush=True)
        return 2

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = _HERE / "results" / "runs" / run_id
    if write_results:
        run_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[run_cases] Client A long-lived host={carla_host()}:{carla_port()} "
        f"cases={len(runnable)} planned_skipped={planned_skip} "
        f"stop_on_fail={int(stop_on_fail)} write_results={int(write_results)} "
        f"(scheme-1: natural continue; Giraffe drives; one window)",
        flush=True,
    )
    carla, client, world = connect_world(
        wait_s=wait_budget_s(args.wait_s), log_prefix="[run_cases]"
    )
    _start_giraffe_client()
    # Always wipe leftover hero/lead from a prior crash/session — otherwise the
    # first case "continues" from the guardrail instead of a real cold start.
    reset_wrecked_ego(world, reason="suite_start")

    view: Optional[ScenarioView] = None
    passed_ids: list[str] = []
    failed_ids: list[str] = []
    skipped_rest: list[str] = []
    case_rows: list[dict[str, Any]] = []
    try:
        for idx, (cid, script, keyword) in enumerate(runnable):
            if STOP:
                skipped_rest.extend(c for c, _, _ in runnable[idx:])
                break
            # Only suite_start is a cold wipe. Mid-suite: keep the same hero (and
            # pygame window) even if yaw is ugly — wrong heading is a verdict
            # issue, not a reason to respawn / reopen the window.
            hero = find_by_role(world, ROLE_EGO)
            if idx == 0:
                keep_ego = False
            elif hero is not None:
                alive = True
                try:
                    if hasattr(hero, "is_alive"):
                        alive = bool(hero.is_alive)
                except Exception:  # noqa: BLE001
                    alive = False
                if alive:
                    keep_ego = True
                else:
                    keep_ego = False
                    reset_wrecked_ego(world, reason="dead")
            else:
                keep_ego = False
                print(
                    f"[run_cases] WARN {cid}: ego missing mid-batch → cold spawn "
                    f"(window may remount)",
                    flush=True,
                )
            print(
                f"[run_cases] ▶ {cid} ({script.name}) keep_ego={int(keep_ego)} "
                f"preserve_ego=1 [{idx + 1}/{len(runnable)}]",
                flush=True,
            )
            os.environ["GF_SCENARIO_CASE_ID"] = cid
            os.environ["GF_SCENARIO_CASE_INDEX"] = str(idx + 1)
            os.environ["GF_SCENARIO_CASE_TOTAL"] = str(len(runnable))
            os.environ["GF_SCENARIO_CASE_KEYWORD"] = keyword
            sp = str(script.parent)
            if sp not in sys.path:
                sys.path.insert(0, sp)
            t0 = time.time()
            mod = _load_py(script)
            runner: Optional[Callable[..., Any]] = getattr(mod, "run_session", None)
            if runner is None:
                print(
                    f"[run_cases] ERROR: {script} has no run_session(); "
                    "run the script directly instead",
                    flush=True,
                )
                failed_ids.append(cid)
                case_rows.append(
                    {
                        "id": cid,
                        "keyword": keyword,
                        "script": str(script.relative_to(_HERE)),
                        "exit": 2,
                        "passed": False,
                        "elapsed_s": 0.0,
                        "error": "no_run_session",
                    }
                )
                if stop_on_fail:
                    skipped_rest.extend(c for c, _, _ in runnable[idx + 1 :])
                    break
                continue
            # Tunnel/ISP need longer windows; other cases follow suite --duration-s.
            cid_l = cid.lower()
            if cid_l.startswith("env_tunnel") or "isp" in cid_l:
                case_dur = duration_s_for_case(cid, fallback=float(args.duration_s))
            else:
                case_dur = max(1.0, float(args.duration_s))
            set_natural_continue(keep_ego)
            try:
                code, view = runner(
                    carla,
                    client,
                    world,
                    period_s=args.period_s,
                    no_window=args.no_window,
                    duration_s=max(1.0, case_dur),
                    view=view,
                    keep_ego=keep_ego,
                    preserve_ego=True,
                    stop_flag=lambda: STOP,
                    ensure_view=_ensure_view,
                )
            except Exception as exc:  # noqa: BLE001
                elapsed = time.time() - t0
                print(
                    f"[run_cases] ■ {cid} layout/run error: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                failed_ids.append(cid)
                case_rows.append(
                    {
                        "id": cid,
                        "keyword": keyword,
                        "script": str(script.relative_to(_HERE)),
                        "exit": 1,
                        "passed": False,
                        "elapsed_s": round(elapsed, 3),
                        "index": idx + 1,
                        "total": len(runnable),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                if stop_on_fail:
                    skipped_rest.extend(c for c, _, _ in runnable[idx + 1 :])
                    break
                continue
            finally:
                set_natural_continue(False)
            elapsed = time.time() - t0
            ok = int(code) == 0
            row = {
                "id": cid,
                "keyword": keyword,
                "script": str(script.relative_to(_HERE)),
                "exit": int(code),
                "passed": ok,
                "elapsed_s": round(elapsed, 3),
                "index": idx + 1,
                "total": len(runnable),
            }
            case_rows.append(row)
            if ok:
                passed_ids.append(cid)
                print(f"[run_cases] ■ {cid} exit=0 PASS", flush=True)
            else:
                failed_ids.append(cid)
                print(
                    f"[run_cases] ■ {cid} exit={code} FAIL "
                    f"(continue={int(not stop_on_fail)})",
                    flush=True,
                )
                if stop_on_fail:
                    skipped_rest.extend(c for c, _, _ in runnable[idx + 1 :])
                    print(
                        "[run_cases] stop_on_fail=1 → not running remaining cases",
                        flush=True,
                    )
                    break
            time.sleep(0.3)
    finally:
        _stop_giraffe_client()
        if view is not None:
            try:
                view.destroy()
            except Exception:  # noqa: BLE001
                pass
        if write_results:
            try:
                _write_results(
                    run_dir=run_dir,
                    case_rows=case_rows,
                    passed_ids=passed_ids,
                    failed_ids=failed_ids,
                    skipped_rest=skipped_rest,
                    planned_skip=planned_skip,
                    runnable_n=len(runnable),
                    stop_on_fail=stop_on_fail,
                    duration_s=float(args.duration_s),
                    host=carla_host(),
                    port=int(carla_port()),
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[run_cases] WARN: results write failed: {exc}", flush=True)
        else:
            print("[run_cases] results skipped (GF_SCENARIO_WRITE_RESULTS=0)", flush=True)
        print("===", flush=True)
        print(
            f"[run_cases] SUMMARY passed={len(passed_ids)} "
            f"failed={len(failed_ids)} skipped_remaining={len(skipped_rest)} "
            f"planned_skipped={planned_skip} runnable={len(runnable)} "
            f"stop_on_fail={int(stop_on_fail)}",
            flush=True,
        )
        if passed_ids:
            print(f"[run_cases]   passed: {', '.join(passed_ids)}", flush=True)
        if failed_ids:
            print(f"[run_cases]   failed: {', '.join(failed_ids)}", flush=True)
        if skipped_rest:
            print(
                f"[run_cases]   skipped_remaining: {', '.join(skipped_rest)}",
                flush=True,
            )
        print(
            "[run_cases] hint: GF_SCENARIO_STOP_ON_FAIL=0 continue (default), "
            "=1 or --stop-on-fail abort after first fail",
            flush=True,
        )
        print("===", flush=True)
    return 1 if failed_ids else 0


if __name__ == "__main__":
    sys.exit(main())
