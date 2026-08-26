"""Cross-platform process helpers for host tools (Windows CARLA + Linux)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Iterable, Optional


def kill_proc_tree(proc: Optional[subprocess.Popen], *, name: str = "proc") -> None:
    """Terminate a Popen and its children (needed after start_new_session=True)."""
    if proc is None:
        return
    if proc.poll() is not None:
        return
    pid = proc.pid
    print(f"[proc] stopping {name} pid={pid}", flush=True)
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            pass
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(signal.SIGTERM)
        except Exception:  # noqa: BLE001
            pass
    try:
        proc.wait(timeout=5)
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
    try:
        proc.wait(timeout=2)
    except Exception:  # noqa: BLE001
        pass


def _win_pids_matching(substr: str) -> list[int]:
    # WMIC is widely available on Win10; ignore failures.
    try:
        r = subprocess.run(
            [
                "wmic",
                "process",
                "where",
                f"CommandLine like '%{substr}%'",
                "get",
                "ProcessId",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        return []
    pids: list[int] = []
    for line in (r.stdout or "").splitlines():
        s = line.strip()
        if not s or s.lower() == "processid":
            continue
        try:
            pids.append(int(s))
        except ValueError:
            continue
    return pids


def _unix_pids_matching(pattern: str) -> list[int]:
    try:
        r = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:  # noqa: BLE001
        return []
    pids: list[int] = []
    for line in (r.stdout or "").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            pids.append(int(s))
        except ValueError:
            continue
    return pids


def kill_matching(substr: str, *, exclude_pid: Optional[int] = None) -> int:
    """Best-effort kill processes whose cmdline contains substr. Returns count."""
    me = os.getpid()
    if sys.platform == "win32":
        pids = _win_pids_matching(substr)
    else:
        pids = _unix_pids_matching(substr)
    n = 0
    for pid in pids:
        if pid in (me, exclude_pid):
            continue
        if sys.platform == "win32":
            r = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0:
                n += 1
                print(f"[proc] killed stale pid={pid} ({substr})", flush=True)
        else:
            try:
                os.kill(pid, signal.SIGTERM)
                n += 1
                print(f"[proc] SIGTERM stale pid={pid} ({substr})", flush=True)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    return n


def kill_stale_host_planners(*, also_octave: bool = True) -> None:
    """Clear leftover giraffe_client / octave_bridge / octave-cli from prior runs."""
    kill_matching("giraffe_client")
    kill_matching("octave_bridge")
    if also_octave:
        # oct2py children often survive Ctrl+C of the bridge parent
        kill_matching("octave-cli")
        if sys.platform == "win32":
            kill_matching("octave.exe")
