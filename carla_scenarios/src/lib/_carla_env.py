"""CARLA address + connect helpers (deployment env; never hard-fail to dry-run).

This process is a CARLA Python *client*; UE is the *server*.
SIL / frame_ingest uses ``projects/<sku>/carla.env`` (loaded by run_sil) — not this file.

Load order for CARLA_HOST / PORT / GF_CARLA_CONNECT_TIMEOUT_S:
  1) already-set process environment (highest)
  2) local file ``carla.env`` next to these scripts (auto-loaded once)
  3) built-in defaults (127.0.0.1:2000, timeout 10s)

**Layering:** call ``load_snapshot()`` once at the process edge, then
``connect_session(snap)``. Deep code (layouts / spawn / traffic) must take a
``CarlaSession`` — do not re-read ``os.environ`` / ``carla.env`` there.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
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
    return load_snapshot().host


def carla_port() -> int:
    return load_snapshot().port


def traffic_manager_port() -> int:
    """Edge helper: prefer ``load_snapshot().tm_port`` and pass it down."""
    return load_snapshot().tm_port


_TM_BY_PORT: dict[int, Any] = {}
_TM_LOGGED: set[int] = set()


def _attach_tm(client: Any, port: int) -> Any:
    """Bind TM once per port (suite-long). Used only by Session / get_traffic_manager."""
    cached = _TM_BY_PORT.get(port)
    if cached is not None:
        return cached
    try:
        tm = client.get_trafficmanager(port)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Traffic Manager bind failed on port {port} "
            f"(GF_TM_PORT from {env_source('GF_TM_PORT')}). "
            "On Windows with empty netstat: check "
            "`netsh interface ipv4 show excludedportrange protocol=tcp` "
            "and set GF_TM_PORT to a free port outside those ranges."
        ) from exc
    _TM_BY_PORT[port] = tm
    if port not in _TM_LOGGED:
        _TM_LOGGED.add(port)
        print(
            f"[tm] attach port={port} (GF_TM_PORT from {env_source('GF_TM_PORT')})",
            flush=True,
        )
    return tm


def get_traffic_manager(client: Any, *, port: Optional[int] = None) -> Any:
    """Attach TM. Prefer ``session.tm``; pass ``port`` from Snapshot when used."""
    return _attach_tm(client, int(port) if port is not None else traffic_manager_port())


def _env_bool(key: str, default: bool = True) -> bool:
    raw = (os.environ.get(key) or ("1" if default else "0")).strip().lower()
    return raw not in ("0", "off", "false", "no")


def _env_int(key: str, default: int) -> int:
    raw = (os.environ.get(key) or str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return int(default)


def _env_float(key: str, default: float) -> float:
    raw = (os.environ.get(key) or str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return float(default)


@dataclass(frozen=True)
class CarlaSnapshot:
    """Immutable deployment config — built once after ``load_local_env()``."""

    host: str
    port: int
    connect_timeout_s: float
    tm_port: int
    town: str
    view: bool
    view_w: int
    view_h: int
    chase_cam: str
    traffic_number: int
    traffic_maintain_s: float
    duration_s: float
    duration_isp_s: float
    acc_th_lo: float
    acc_th_hi: float


_SNAPSHOT: Optional[CarlaSnapshot] = None


def load_snapshot(*, force: bool = False) -> CarlaSnapshot:
    """Read carla.env / process env once; return frozen Snapshot (cached)."""
    global _SNAPSHOT
    if _SNAPSHOT is not None and not force:
        return _SNAPSHOT
    load_local_env(force=force)
    raw_tm = (os.environ.get("GF_TM_PORT") or "8000").strip()
    try:
        tm_port = max(1, int(raw_tm))
    except ValueError:
        tm_port = 8000
    _SNAPSHOT = CarlaSnapshot(
        host=(os.environ.get("CARLA_HOST") or "127.0.0.1").strip(),
        port=int(os.environ.get("CARLA_PORT") or "2000"),
        connect_timeout_s=float(os.environ.get("GF_CARLA_CONNECT_TIMEOUT_S") or "10"),
        tm_port=tm_port,
        town=(os.environ.get("GF_CARLA_TOWN") or "").strip(),
        view=_env_bool("GF_SCENARIO_VIEW", True),
        view_w=max(160, _env_int("GF_SCENARIO_VIEW_W", 960)),
        view_h=max(120, _env_int("GF_SCENARIO_VIEW_H", 540)),
        chase_cam=(os.environ.get("ChaseCam") or "1").strip() or "1",
        traffic_number=max(0, _env_int("GF_TRAFFIC_NUMBER", 18)),
        traffic_maintain_s=max(0.5, _env_float("GF_TRAFFIC_MAINTAIN_S", 2.0)),
        duration_s=max(1.0, _env_float("GF_SCENARIO_DURATION_S", 8.0)),
        duration_isp_s=max(1.0, _env_float("GF_SCENARIO_DURATION_ISP_S", 25.0)),
        acc_th_lo=_env_float("GF_ACC_TH_LO", 1.0),
        acc_th_hi=_env_float("GF_ACC_TH_HI", 2.5),
    )
    return _SNAPSHOT


@dataclass
class CarlaSession:
    """One connected CARLA client + Snapshot. Sole owner of set_autopilot port."""

    snap: CarlaSnapshot
    carla: Any
    client: Any
    world: Any
    _tm: Any = None

    @property
    def tm_port(self) -> int:
        return int(self.snap.tm_port)

    @property
    def tm(self) -> Any:
        if self._tm is None:
            self._tm = _attach_tm(self.client, self.tm_port)
        return self._tm

    def ap_off(self, actor: Any) -> None:
        """Disable TM autopilot on *this* TM port (never default 8000)."""
        if actor is None:
            return
        try:
            actor.set_autopilot(False, self.tm_port)
        except Exception:  # noqa: BLE001
            try:
                actor.set_autopilot(False)
            except Exception:  # noqa: BLE001
                pass

    def ap_on(self, actor: Any) -> None:
        if actor is None:
            return
        try:
            actor.set_autopilot(True, self.tm_port)
        except Exception:  # noqa: BLE001
            pass

    @classmethod
    def bind(
        cls,
        carla_mod: Any,
        client: Any,
        world: Any,
        snap: Optional[CarlaSnapshot] = None,
    ) -> "CarlaSession":
        return cls(
            snap=snap if snap is not None else load_snapshot(),
            carla=carla_mod,
            client=client,
            world=world,
        )


def connect_timeout_s() -> float:
    """Single RPC timeout knob (seconds). Default 10."""
    return load_snapshot().connect_timeout_s


def wait_budget_s(cli_wait: Optional[float] = None) -> float:
    """Optional retry window from CLI ``--wait-s`` only (not a second env timeout)."""
    if cli_wait is not None:
        return max(0.0, float(cli_wait))
    return 0.0


def describe_endpoint() -> str:
    snap = load_snapshot()
    return (
        f"CARLA_HOST={snap.host} (from {env_source('CARLA_HOST')}) "
        f"CARLA_PORT={snap.port} (from {env_source('CARLA_PORT')}) "
        f"GF_CARLA_CONNECT_TIMEOUT_S={snap.connect_timeout_s} "
        f"(from {env_source('GF_CARLA_CONNECT_TIMEOUT_S')}) "
        f"GF_TM_PORT={snap.tm_port} (from {env_source('GF_TM_PORT')})"
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
    town: str = "",
    log_prefix: str = "[carla]",
    timeout_s: Optional[float] = None,
) -> Any:
    """Optionally load town (e.g. Town04). Empty = keep current map.

    Pass ``town`` from Snapshot; do not re-read env here.
    """
    want = (town or "").strip()
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


def duration_s_for_case(case_id: str, *, fallback: float = 8.0, snap: Optional[CarlaSnapshot] = None) -> float:
    """Per-case duration from Snapshot (ISP/tunnel uses duration_isp_s)."""
    s = snap if snap is not None else load_snapshot()
    cid = (case_id or "").strip().lower()
    isp = cid.startswith("env_tunnel") or "isp" in cid
    if isp:
        return max(1.0, float(s.duration_isp_s))
    return max(1.0, float(s.duration_s if s.duration_s else fallback))


def connect_world(
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    timeout_s: Optional[float] = None,
    wait_s: float = 0.0,
    log_prefix: str = "[carla]",
    snap: Optional[CarlaSnapshot] = None,
) -> Tuple[Any, Any, Any]:
    """Connect to CARLA UE. Raises on failure (never falls back to dry-run).

    Returns (carla_module, client, world). Prefer ``connect_session``.
    """
    s = snap if snap is not None else load_snapshot()
    try:
        import carla  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "carla Python module not installed. "
            "Use the UE-matching egg/wheel, or pass --dry-run explicitly for camera-less dry-run."
        ) from exc

    h = host if host is not None else s.host
    p = port if port is not None else s.port
    to = timeout_s if timeout_s is not None else s.connect_timeout_s
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
                client,
                world,
                town=s.town,
                log_prefix=log_prefix,
                timeout_s=to,
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


def connect_session(
    *,
    wait_s: float = 0.0,
    log_prefix: str = "[carla]",
    snap: Optional[CarlaSnapshot] = None,
) -> CarlaSession:
    """Connect + bind Snapshot + attach TM once. Edge entry for suite/case."""
    s = snap if snap is not None else load_snapshot()
    carla_mod, client, world = connect_world(
        wait_s=wait_s, log_prefix=log_prefix, snap=s
    )
    session = CarlaSession.bind(carla_mod, client, world, s)
    # Warm TM once so layout ap_off does not race first attach.
    _ = session.tm
    return session


def probe(
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    timeout_s: Optional[float] = None,
    wait_s: float = 0.0,
) -> dict[str, Any]:
    """Return connectivity dict for CI preflight."""
    s = load_snapshot()
    h = host if host is not None else s.host
    p = port if port is not None else s.port
    try:
        _carla, client, world = connect_world(
            host=h, port=p, timeout_s=timeout_s, wait_s=wait_s, log_prefix="[preflight]", snap=s
        )
        return {
            "ok": True,
            "host": h,
            "port": p,
            "host_source": env_source("CARLA_HOST"),
            "map": world.get_map().name,
            "client_version": str(client.get_client_version()),
            "server_version": str(client.get_server_version()),
            "tm_port": s.tm_port,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "host": h,
            "port": p,
            "host_source": env_source("CARLA_HOST"),
            "error": str(exc),
        }
