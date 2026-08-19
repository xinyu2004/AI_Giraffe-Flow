"""CARLA address + connect helpers (deployment env; never hard-fail to dry-run).

This process is a CARLA Python *client*; UE is the *server*.
SIL / frame_ingest uses ``projects/<sku>/carla.env`` (loaded by run_sil) — not this file.

Load order for CARLA_HOST / PORT / GF_CARLA_CONNECT_TIMEOUT_S:
  1) already-set process environment (highest)
  2) local file ``carla.env`` next to these scripts (auto-loaded once)
  3) built-in defaults (127.0.0.1:2000, timeout 10s)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional, Tuple

_LIB = Path(__file__).resolve().parent
# carla.env lives at carla_scenarios/ (parent of src/ when lib is under src/lib).
if _LIB.name == "lib" and _LIB.parent.name == "src":
    _AFC_ROOT = _LIB.parent.parent
elif _LIB.name == "lib":
    _AFC_ROOT = _LIB.parent
else:
    _AFC_ROOT = _LIB
_LOADED = False
_SOURCES: dict[str, str] = {}


def afc_root() -> Path:
    return _AFC_ROOT


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key:
            out[key] = val
    return out


def load_local_env(*, force: bool = False) -> Path | None:
    """Load ``carla_scenarios/carla.env`` into os.environ for keys not already set."""
    global _LOADED
    carla_env = _AFC_ROOT / "carla.env"
    if _LOADED and not force:
        return carla_env if carla_env.is_file() else None

    loaded: Path | None = None

    if carla_env.is_file():
        for key, val in _parse_env_file(carla_env).items():
            if key in os.environ and os.environ[key] != "":
                _SOURCES.setdefault(key, "process-env")
                continue
            os.environ[key] = val
            _SOURCES[key] = f"carla.env:{carla_env}"
        loaded = carla_env

    for key in ("CARLA_HOST", "CARLA_PORT", "GF_CARLA_CONNECT_TIMEOUT_S", "ChaseCam"):
        if key in os.environ and key not in _SOURCES:
            _SOURCES[key] = "process-env"

    _LOADED = True
    return loaded


def env_source(key: str) -> str:
    load_local_env()
    if key in _SOURCES:
        return _SOURCES[key]
    return "default"


def carla_host() -> str:
    load_local_env()
    return (os.environ.get("CARLA_HOST") or "127.0.0.1").strip()


def carla_port() -> int:
    load_local_env()
    return int(os.environ.get("CARLA_PORT") or "2000")


def connect_timeout_s() -> float:
    """Single RPC timeout knob (seconds). Default 10."""
    load_local_env()
    return float(os.environ.get("GF_CARLA_CONNECT_TIMEOUT_S") or "10")


def wait_budget_s(cli_wait: Optional[float] = None) -> float:
    """Optional retry window from CLI ``--wait-s`` only (not a second env timeout)."""
    if cli_wait is not None:
        return max(0.0, float(cli_wait))
    return 0.0


def describe_endpoint() -> str:
    load_local_env()
    return (
        f"CARLA_HOST={carla_host()} (from {env_source('CARLA_HOST')}) "
        f"CARLA_PORT={carla_port()} (from {env_source('CARLA_PORT')}) "
        f"GF_CARLA_CONNECT_TIMEOUT_S={connect_timeout_s()} "
        f"(from {env_source('GF_CARLA_CONNECT_TIMEOUT_S')})"
    )


def print_carla_api_versions(client: Any) -> tuple[str, str]:
    """Print conspicuous client/server API versions (same format as carla_bridge)."""
    cv = str(client.get_client_version())
    sv = str(client.get_server_version())
    print("===", flush=True)
    print(f"carla API  client={cv}  server={sv}", flush=True)
    print("===", flush=True)
    return cv, sv


def _stage_error(stage: str, exc: BaseException, *, timeout_s: float) -> RuntimeError:
    """Tag which CARLA RPC stage failed (esp. timeouts)."""
    msg = str(exc)
    kind = "timeout" if "time-out" in msg.lower() or "timeout" in msg.lower() else "error"
    return RuntimeError(
        f"CARLA {kind} during {stage} "
        f"(GF_CARLA_CONNECT_TIMEOUT_S={timeout_s:g}s): {exc}"
    )


def ensure_town(
    client: Any,
    world: Any,
    *,
    log_prefix: str = "[carla]",
    timeout_s: Optional[float] = None,
) -> Any:
    """Optionally load GF_CARLA_TOWN (e.g. Town04). Empty = keep current map.

    Uses the same GF_CARLA_CONNECT_TIMEOUT_S as other RPCs; failures are tagged
    as load_world / wait_for_tick so they are not confused with connect.
    """
    load_local_env()
    want = (os.environ.get("GF_CARLA_TOWN") or "").strip()
    if not want:
        return world
    cur = ""
    try:
        cur = str(world.get_map().name)
    except Exception:  # noqa: BLE001
        pass
    if want.lower() in cur.lower():
        print(f"{log_prefix} map ok ({cur})", flush=True)
        return world
    to = float(timeout_s if timeout_s is not None else connect_timeout_s())
    print(f"{log_prefix} load_world {want!r} (was {cur!r})", flush=True)
    try:
        world = client.load_world(want)
    except Exception as exc:  # noqa: BLE001
        raise _stage_error(f"load_world({want})", exc, timeout_s=to) from exc
    try:
        world.wait_for_tick(to)
    except Exception as exc:  # noqa: BLE001
        raise _stage_error(f"wait_for_tick after load_world({want})", exc, timeout_s=to) from exc
    print(f"{log_prefix} map now {world.get_map().name}", flush=True)
    return world


def duration_s_for_case(case_id: str, *, fallback: float = 8.0) -> float:
    """Per-case duration: ISP/tunnel uses GF_SCENARIO_DURATION_ISP_S (default 25)."""
    load_local_env()
    cid = (case_id or "").strip().lower()
    isp = cid.startswith("env_tunnel") or "isp" in cid
    if isp:
        return max(
            1.0,
            float(os.environ.get("GF_SCENARIO_DURATION_ISP_S") or "25"),
        )
    return max(
        1.0,
        float(os.environ.get("GF_SCENARIO_DURATION_S") or str(fallback)),
    )


def connect_world(
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    timeout_s: Optional[float] = None,
    wait_s: float = 0.0,
    log_prefix: str = "[carla]",
) -> Tuple[Any, Any, Any]:
    """Connect to CARLA UE. Raises on failure (never falls back to dry-run).

    One timeout knob: ``GF_CARLA_CONNECT_TIMEOUT_S`` (per RPC). Optional
    ``wait_s`` / ``--wait-s`` only retries within that window — not a second
    env timeout. Errors name the failing stage (get_server_version, get_world,
    load_world, …).

    Returns (carla_module, client, world).
    """
    load_local_env()
    try:
        import carla  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "carla Python module not installed. "
            "Use the UE-matching egg/wheel, or pass --dry-run explicitly for camera-less dry-run."
        ) from exc

    h = host if host is not None else carla_host()
    p = port if port is not None else carla_port()
    to = timeout_s if timeout_s is not None else connect_timeout_s()
    deadline = time.time() + max(0.0, wait_s)
    attempt = 0
    last_err: Optional[BaseException] = None
    last_stage = "connect"

    print(f"{log_prefix} {describe_endpoint()}", flush=True)

    while True:
        attempt += 1
        client = carla.Client(h, p)
        client.set_timeout(to)
        stage = "connect"
        try:
            stage = "get_client_version"
            try:
                cv = str(client.get_client_version())
            except Exception as exc:  # noqa: BLE001
                raise _stage_error(stage, exc, timeout_s=to) from exc
            stage = "get_server_version"
            try:
                sv = str(client.get_server_version())
            except Exception as exc:  # noqa: BLE001
                raise _stage_error(stage, exc, timeout_s=to) from exc
            print("===", flush=True)
            print(f"carla API  client={cv}  server={sv}", flush=True)
            print("===", flush=True)
            if cv.strip() != sv.strip():
                raise RuntimeError(
                    f"CARLA API mismatch client={cv} server={sv} ({h}:{p})"
                )
            stage = "get_world"
            try:
                world = client.get_world()
            except Exception as exc:  # noqa: BLE001
                raise _stage_error(stage, exc, timeout_s=to) from exc
            stage = "ensure_town/load_world"
            world = ensure_town(
                client, world, log_prefix=log_prefix, timeout_s=to
            )
            print(
                f"{log_prefix} connected {h}:{p} map={world.get_map().name} "
                f"(attempt={attempt})",
                flush=True,
            )
            return carla, client, world
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            last_stage = stage
            if "API mismatch" in str(exc):
                break
            remain = deadline - time.time()
            if remain <= 0:
                break
            print(
                f"{log_prefix} retry after {stage} failure {h}:{p} "
                f"({remain:.0f}s left): {exc}",
                flush=True,
            )
            time.sleep(min(2.0, max(0.5, remain)))

    raise RuntimeError(
        f"CARLA connect failed at stage={last_stage} {h}:{p} "
        f"after {attempt} attempt(s): {last_err}. "
        f"Edit {_AFC_ROOT}/carla.env (CARLA_HOST/PORT, "
        f"GF_CARLA_CONNECT_TIMEOUT_S) or set process env. "
        f"Optional retry window: --wait-s. "
        f"Camera-less dry-run without UE: pass --dry-run explicitly."
    )


def probe(
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    timeout_s: Optional[float] = None,
    wait_s: float = 0.0,
) -> dict[str, Any]:
    """Return connectivity dict for CI preflight."""
    load_local_env()
    h = host if host is not None else carla_host()
    p = port if port is not None else carla_port()
    try:
        _carla, client, world = connect_world(
            host=h, port=p, timeout_s=timeout_s, wait_s=wait_s, log_prefix="[preflight]"
        )
        return {
            "ok": True,
            "host": h,
            "port": p,
            "host_source": env_source("CARLA_HOST"),
            "map": world.get_map().name,
            "client_version": str(client.get_client_version()),
            "server_version": str(client.get_server_version()),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "host": h,
            "port": p,
            "host_source": env_source("CARLA_HOST"),
            "error": str(exc),
        }
