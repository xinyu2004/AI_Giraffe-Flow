#!/usr/bin/env bash
# SIL run (product path): RouDi + wiring main chain; optional Foxglove from observability.json.
# Optional G3 inject mode: replace gateway EgoMotion with session replay (no dual publish).
#
# Config truth = gf-config → compose → generated/observability.json + build binaries.
#   live_tap effective → gf_iox_obs_tap | GMT bridge foxglove --ws
#   else → main chain only until Ctrl+C
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#   # B1 boundary inject (no gateway; full consumer chain):
#   GF_INJECT_SESSION=build/observability/session.jsonl \
#     bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#   # B2 single-module (DUT only + inject):
#   GF_INJECT_SESSION=… GF_INJECT_DUT=sensing.uss \
#     bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#
# Env:
#   GF_BUILD_DIR     default <repo>/build
#   GF_WS_HOST       default 0.0.0.0
#   GF_WS_PORT       default 8765
#   GF_LIVE_PORT     default 8766 (GMT GUI live bridge)
#   GF_LIVE_SESSION  optional tee path (default build/observability/session_live.jsonl)
#   GF_LIVE_TEE      default 1 — tee tap NDJSON to GF_LIVE_SESSION
#   GF_SKIP_COMPILE=1  skip compile_sil (assume already built)
#   GF_INJECT_SESSION  if set → inject mode (no gateway; run gf_iox_obs_inject)
#   GF_INJECT_MODE     continuous (default) | playhead — playhead waits for GMT on GF_INJECT_PORT
#   GF_INJECT_PORT     default 8767 (playhead control TCP)
#   GF_INJECT_HOST     default 0.0.0.0 (playhead bind)
#   GF_INJECT_LIVE     default 1 — keep live_tap during inject but only downstream topics
#   GF_INJECT_SERVICES default EgoMotion (or auto from DUT requires ∩ injectable)
#   GF_INJECT_DUT      B2: SOR process id (e.g. sensing.uss) → only that app + inject
#   GF_INJECT_APPS     B2 override: comma list uss,fcm,planning (skip SOR lookup)
#   GF_SIL_KILL_STALE  default 1 — 启动前释放被旧 SIL/GMT 占用的 8765/8766/8767
#                      设 0 则端口忙时直接失败并提示如何手动停
#   # playhead example:
#   GF_INJECT_SESSION=… GF_INJECT_MODE=playhead \
#     bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#   # then GMT gui → 回灌 tab → connect 127.0.0.1:8767
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

ROOT="${ROOT}"
BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
HOST="${GF_WS_HOST:-0.0.0.0}"
PORT="${GF_WS_PORT:-8765}"
export GF_PLATFORM_DIR="${GF_PLATFORM_DIR:-${PROJECT_DIR}/platform}"
export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-0}"
export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

INJECT_SESSION="${GF_INJECT_SESSION:-}"
INJECT_ON=0
INJECT_MODE="off" # off | b1 | b2
if [[ -n "${INJECT_SESSION}" ]]; then
  INJECT_ON=1
  if [[ -n "${GF_INJECT_DUT:-}" || -n "${GF_INJECT_APPS:-}" ]]; then
    INJECT_MODE="b2"
  else
    INJECT_MODE="b1"
  fi
fi

# Which consumer apps to start (keys: uss fcm planning). Empty until resolved.
RUN_APPS=""

if [[ "${GF_SKIP_COMPILE:-0}" != "1" ]]; then
  bash "${SCRIPT_DIR}/compile_sil.sh"
fi

OBS_JSON="${PROJECT_DIR}/generated/observability.json"
SOR_JSON="${PROJECT_DIR}/gf.sor.json"
LIVE_ON=0
LIVE_SVCS=""
if [[ -f "${OBS_JSON}" ]]; then
  export GF_OBS_JSON="${OBS_JSON}"
  eval "$(python - <<'PY'
import json
from pathlib import Path
import os
obs = Path(os.environ["GF_OBS_JSON"])
d = json.loads(obs.read_text(encoding="utf-8"))
live = d.get("live_tap") or {}
en = bool(live.get("enabled"))
svcs = [str(x).strip() for x in (live.get("services") or []) if str(x).strip()]
print("LIVE_ON=%s" % ("1" if en and svcs else "0"))
print("LIVE_SVCS=%s" % ",".join(svcs))
PY
)"
else
  echo "${TAG} WARN: missing ${OBS_JSON} — run compile_sil first; live Foxglove off" >&2
fi

# Inject replaces gateway. Live tap may stay on for downstream观察 (not injectable topics).
if [[ "${INJECT_ON}" == "1" ]]; then
  echo "${TAG} inject mode=${INJECT_MODE}: gateway OFF (session=${INJECT_SESSION})"
  if [[ "${GF_INJECT_LIVE:-1}" == "0" ]]; then
    LIVE_ON=0
    echo "${TAG} GF_INJECT_LIVE=0 → live_tap forced OFF"
  elif [[ "${LIVE_ON}" == "1" ]]; then
    # 默认只订下游：从 live 白名单去掉正在灌的服务（MVP：EgoMotion）
    export GF_LIVE_SVCS_RAW="${LIVE_SVCS}"
    export GF_INJECT_SERVICES_FOR_FILTER="${GF_INJECT_SERVICES:-EgoMotion}"
    eval "$(python - <<'PY'
import os
raw = os.environ.get("GF_LIVE_SVCS_RAW") or ""
inj = os.environ.get("GF_INJECT_SERVICES_FOR_FILTER") or "EgoMotion"
def short(s: str) -> str:
    s = s.strip()
    pref = "services.semantic."
    if s.startswith(pref):
        s = s[len(pref):]
    if "/" in s:
        s = s.rsplit("/", 1)[-1]
    return s
block = {short(x) for x in inj.replace(";", ",").split(",") if x.strip()}
keep = []
for part in raw.replace(";", ",").split(","):
    p = part.strip()
    if not p:
        continue
    if short(p) in block:
        continue
    keep.append(short(p) or p)
print("LIVE_SVCS=%s" % ",".join(keep))
print("LIVE_ON=%s" % ("1" if keep else "0"))
PY
)"
    if [[ "${LIVE_ON}" == "1" ]]; then
      echo "${TAG} inject+live: downstream tap only → ${LIVE_SVCS} (excluded injectable)"
    else
      echo "${TAG} inject+live: no downstream services left after filter — live_tap OFF"
    fi
  fi
fi

# Resolve B1/B2 app subset + optional auto services from SOR
if [[ "${INJECT_ON}" == "1" ]]; then
  export GF_SOR_JSON="${SOR_JSON}"
  export GF_INJECT_DUT="${GF_INJECT_DUT:-}"
  export GF_INJECT_APPS="${GF_INJECT_APPS:-}"
  export GF_INJECT_SERVICES_ENV="${GF_INJECT_SERVICES:-}"
  eval "$(python - <<'PY'
import json, os, sys
from pathlib import Path

# process id / aliases → app key used by run_sil
PROC_TO_APP = {
    "sensing.uss": "uss",
    "uss": "uss",
    "gf_sensing_uss": "uss",
    "perception.fcm": "fcm",
    "fcm": "fcm",
    "gf_perception_fcm": "fcm",
    "planning.driving": "planning",
    "planning": "planning",
    "gf_planning_driving": "planning",
}
# inject MVP can publish these short names
INJECTABLE = {"EgoMotion"}

dut = (os.environ.get("GF_INJECT_DUT") or "").strip()
apps_env = (os.environ.get("GF_INJECT_APPS") or "").strip()
svcs_env = (os.environ.get("GF_INJECT_SERVICES_ENV") or "").strip()
sor_path = Path(os.environ.get("GF_SOR_JSON") or "")

def short(svc: str) -> str:
    s = svc.strip()
    pref = "services.semantic."
    if s.startswith(pref):
        return s[len(pref):]
    return s.rsplit(".", 1)[-1] if s else ""

apps: list[str] = []
requires: list[str] = []

if apps_env:
    for part in apps_env.replace(";", ",").split(","):
        k = part.strip().lower()
        if not k:
            continue
        mapped = PROC_TO_APP.get(k) or PROC_TO_APP.get(part.strip())
        if mapped is None:
            print(f"echo \"${{TAG}} ERROR: unknown GF_INJECT_APPS entry: {part}\" >&2")
            print("exit 1")
            sys.exit(0)
        if mapped not in apps:
            apps.append(mapped)
elif dut:
    if not sor_path.is_file():
        print(f"echo \"${{TAG}} ERROR: GF_INJECT_DUT needs {sor_path}\" >&2")
        print("exit 1")
        sys.exit(0)
    sor = json.loads(sor_path.read_text(encoding="utf-8"))
    want = dut
    hit = None
    for dep in sor.get("deployments") or []:
        if not isinstance(dep, dict):
            continue
        proc = str(dep.get("process") or "")
        if proc == want or proc.endswith("." + want) or PROC_TO_APP.get(proc) == PROC_TO_APP.get(want):
            hit = dep
            break
        # alias match
        if PROC_TO_APP.get(want) and PROC_TO_APP.get(proc) == PROC_TO_APP.get(want):
            hit = dep
            break
    if hit is None:
        print(f"echo \"${{TAG}} ERROR: DUT process not in SOR: {want}\" >&2")
        print("exit 1")
        sys.exit(0)
    proc = str(hit.get("process") or "")
    app = PROC_TO_APP.get(proc)
    if app is None:
        print(f"echo \"${{TAG}} ERROR: no binary mapping for DUT {proc}\" >&2")
        print("exit 1")
        sys.exit(0)
    apps = [app]
    requires = [short(str(x)) for x in (hit.get("requires") or []) if str(x).strip()]
else:
    # B1: full consumer chain
    apps = ["fcm", "uss", "planning"]

# services: explicit env wins; else DUT requires ∩ injectable; else EgoMotion
if svcs_env:
    services = [short(x) for x in svcs_env.replace(";", ",").split(",") if x.strip()]
elif requires:
    services = [s for s in requires if s in INJECTABLE]
    missing = [s for s in requires if s not in INJECTABLE]
    if missing:
        print(
            "echo \"%s WARN: DUT requires not injectable (MVP): %s\" >&2"
            % ("${TAG}", ",".join(missing))
        )
    if not services:
        print(
            "echo \"%s ERROR: no injectable services for DUT (need EgoMotion in requires or set GF_INJECT_SERVICES)\" >&2"
            % ("${TAG}",)
        )
        print("exit 1")
        sys.exit(0)
else:
    services = ["EgoMotion"]

print("RUN_APPS=%s" % ",".join(apps))
print("GF_INJECT_SERVICES=%s" % ",".join(services))
PY
)"
  export GF_INJECT_SERVICES
fi

ROUDI="${BUILD}/iox-roudi"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
USS="${BUILD}/apps/sensing/uss/gf_sensing_uss"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"
TAP="${BUILD}/apps/tools/iox_obs_tap/gf_iox_obs_tap"
INJ="${BUILD}/apps/tools/iox_obs_inject/gf_iox_obs_inject"

NEED_BINS=("${ROUDI}")
if [[ "${INJECT_ON}" == "1" ]]; then
  NEED_BINS+=("${INJ}")
  if [[ ! -f "${INJECT_SESSION}" ]]; then
    echo "${TAG} ERROR: GF_INJECT_SESSION not a file: ${INJECT_SESSION}" >&2
    exit 1
  fi
  IFS=',' read -r -a _apps_arr <<< "${RUN_APPS}"
  for a in "${_apps_arr[@]}"; do
    case "${a}" in
      uss) NEED_BINS+=("${USS}") ;;
      fcm) NEED_BINS+=("${FCM}") ;;
      planning) NEED_BINS+=("${PLAN}") ;;
      *) echo "${TAG} ERROR: bad RUN_APPS entry: ${a}" >&2; exit 1 ;;
    esac
  done
else
  NEED_BINS+=("${GW}" "${FCM}" "${USS}" "${PLAN}")
fi
if [[ "${LIVE_ON}" == "1" ]]; then
  NEED_BINS+=("${TAP}")
fi
for bin in "${NEED_BINS[@]}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "Missing executable: ${bin}" >&2
    echo "Build first: bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh" >&2
    if [[ "${bin}" == "${TAP}" ]]; then
      echo "live_tap is on but tap binary missing — check profile=vehicle-debug + live in gf-config." >&2
    fi
    if [[ "${bin}" == "${INJ}" ]]; then
      echo "inject binary missing — vehicle-debug compose should add tools/iox_obs_inject; re-run compile_sil." >&2
    fi
    exit 1
  fi
done

if [[ ! -f "${GF_PLATFORM_DIR}/exec.yaml" && ! -f "${GF_PLATFORM_DIR}/platform/exec.yaml" ]]; then
  echo "Missing exec.yaml under ${GF_PLATFORM_DIR} (or …/platform/)" >&2
  exit 1
fi

LOG_DIR="${BUILD}/iox_sil_logs"
mkdir -p "${LOG_DIR}"

LIVE_PORT="${GF_LIVE_PORT:-8766}"
INJ_PORT="${GF_INJECT_PORT:-8767}"

# 释放上次 Ctrl+C 未清干净 / 重复开跑 留下的 bridge / inject（EADDRINUSE / iceoryx same-name）
gf_sil_preflight_ports() {
  export GF_SIL_PORT_WS="${PORT}"
  export GF_SIL_PORT_LIVE="${LIVE_PORT}"
  export GF_SIL_PORT_INJ="${INJ_PORT}"
  export GF_SIL_KILL_STALE="${GF_SIL_KILL_STALE:-1}"
  export GF_SIL_INJECT_ON="${INJECT_ON}"
  export GF_SIL_LIVE_ON="${LIVE_ON}"
  python - <<'PY'
import os, re, signal, subprocess, time

tag = "[afc_with_uss]"

def cmdline(pid: int) -> str:
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(
            "utf-8", "replace"
        )
    except OSError:
        return ""

def ss_listeners():
    try:
        out = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    rows = []
    for line in out.splitlines():
        mport = re.search(r":(\d+)\s", line)
        if not mport:
            continue
        port = int(mport.group(1))
        for name, pid in re.findall(r'\("([^"]+)",pid=(\d+)', line):
            rows.append((port, name, int(pid)))
    return rows

def pids_matching(pattern: str) -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    me = {os.getpid(), os.getppid()}
    return [int(x) for x in out.split() if int(x) not in me]

wanted = set()
if os.environ.get("GF_SIL_LIVE_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_WS"]))
    wanted.add(int(os.environ["GF_SIL_PORT_LIVE"]))
if os.environ.get("GF_SIL_INJECT_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_INJ"]))

kill_stale = os.environ.get("GF_SIL_KILL_STALE", "1") == "1"
listeners = [(p, n, pid) for p, n, pid in ss_listeners() if p in wanted]
other_run_sil = pids_matching("afc_with_uss/scripts/run_sil.sh")

if not listeners and not other_run_sil:
    if os.environ.get("GF_SIL_INJECT_ON") == "1" and kill_stale:
        subprocess.run(
            ["pkill", "-f", "gf_iox_obs_inject"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    raise SystemExit(0)

if listeners:
    print(f"{tag} port busy (leftover SIL/GMT?):", flush=True)
    for p, n, pid in listeners:
        print(f"{tag}   :{p}  {n} pid={pid}", flush=True)
if other_run_sil:
    print(f"{tag} other run_sil still running: pids={other_run_sil}", flush=True)

ours, others = [], []
for p, n, pid in listeners:
    cmd = cmdline(pid)
    if (
        "GMT" in cmd
        or "gf_gmt" in cmd
        or "bridge" in cmd
        or "gf_iox_obs_inject" in cmd
        or "iox_obs_inject" in cmd
        or n.startswith("gf_iox_obs")
    ):
        ours.append((p, n, pid, cmd))
    else:
        others.append((p, n, pid, cmd))

if not kill_stale:
    print(f"{tag} ERROR: Address already in use / previous SIL still up.", flush=True)
    print(f"{tag}   → Ctrl+C the other terminal's run_sil, or re-run with:", flush=True)
    print(f"{tag}   GF_SIL_KILL_STALE=1 bash projects/oem_a/afc_with_uss/scripts/run_sil.sh …", flush=True)
    raise SystemExit(1)

targets = {pid for _, _, pid, _ in ours} | {pid for _, _, pid, _ in others}
targets.update(other_run_sil)
print(f"{tag} GF_SIL_KILL_STALE=1 → stopping stale pids {sorted(targets)}", flush=True)
for pid in sorted(targets):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
subprocess.run(
    ["pkill", "-f", "gf_iox_obs_inject"],
    check=False,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
subprocess.run(
    ["pkill", "-f", "GMT bridge"],
    check=False,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(0.6)
for pid in sorted(targets):
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
time.sleep(0.3)
left = [(p, n, pid) for p, n, pid in ss_listeners() if p in wanted]
if left:
    print(f"{tag} ERROR: still busy after kill:", flush=True)
    for p, n, pid in left:
        print(f"{tag}   :{p} {n} pid={pid} — {cmdline(pid)[:100]}", flush=True)
    raise SystemExit(1)
print(f"{tag} stale listeners cleared", flush=True)
PY
}

gf_sil_preflight_ports

cleanup() {
  set +e
  for pid in "${LIVE_FAN_PID:-}" "${TAP_PID:-}" "${INJ_PID:-}" "${GW_PID:-}" "${PLAN_PID:-}" "${FCM_PID:-}" "${USS_PID:-}" "${ROUDI_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null
  done
  # process-substitution GMT bridges may outlive the fan pipeline
  if [[ "${LIVE_ON}" == "1" ]]; then
    fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
    fuser -k "${LIVE_PORT}/tcp" >/dev/null 2>&1 || true
  fi
  if [[ "${INJECT_ON}" == "1" ]]; then
    fuser -k "${INJ_PORT}/tcp" >/dev/null 2>&1 || true
    pkill -f gf_iox_obs_inject >/dev/null 2>&1 || true
  fi
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "${TAG} run_sil: platform=${GF_PLATFORM_DIR} live=${LIVE_ON} inject=${INJECT_MODE} apps=${RUN_APPS:-full}"
echo "${TAG} RouDi ..."
"${ROUDI}" >"${LOG_DIR}/roudi.log" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "${TAG} RouDi failed; see ${LOG_DIR}/roudi.log" >&2
  cat "${LOG_DIR}/roudi.log" >&2 || true
  exit 1
fi

start_consumers() {
  local apps="${1:-fcm,uss,planning}"
  local a
  IFS=',' read -r -a _arr <<< "${apps}"
  for a in "${_arr[@]}"; do
    case "${a}" in
      fcm)
        echo "${TAG} start fcm"
        "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
        FCM_PID=$!
        ;;
      uss)
        echo "${TAG} start uss"
        "${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
        USS_PID=$!
        ;;
      planning)
        echo "${TAG} start planning"
        GF_PHM_FAULT_MS=0 "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
        PLAN_PID=$!
        ;;
    esac
  done
  sleep 0.5
}

if [[ "${INJECT_ON}" == "1" ]]; then
  start_consumers "${RUN_APPS}"
  DRIVE_MODE="${GF_INJECT_MODE:-continuous}"
  INJ_PORT="${GF_INJECT_PORT:-8767}"
  INJ_HOST="${GF_INJECT_HOST:-0.0.0.0}"
  echo "${TAG} inject from ${INJECT_SESSION} (services=${GF_INJECT_SERVICES} topology=${INJECT_MODE} drive=${DRIVE_MODE})"
  export GF_INJECT_SESSION="${INJECT_SESSION}"
  export GF_INJECT_MODE="${DRIVE_MODE}"
  export GF_INJECT_PORT="${INJ_PORT}"
  export GF_INJECT_HOST="${INJ_HOST}"
  GF_INJECT_SESSION="${INJECT_SESSION}" \
    GF_INJECT_MODE="${DRIVE_MODE}" \
    GF_INJECT_PORT="${INJ_PORT}" \
    GF_INJECT_HOST="${INJ_HOST}" \
    "${INJ}" "${INJECT_SESSION}" >"${LOG_DIR}/inject.log" 2>&1 &
  INJ_PID=$!

  LIVE_FAN_PID=""
  if [[ "${LIVE_ON}" == "1" ]]; then
    export GF_OBS_LIVE_SERVICES="${LIVE_SVCS}"
    LIVE_PORT="${GF_LIVE_PORT:-8766}"
    LIVE_SESSION="${GF_LIVE_SESSION:-${ROOT}/build/observability/session_live.jsonl}"
    LIVE_TEE="${GF_LIVE_TEE:-1}"
    HINT_IP="127.0.0.1"
    if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
      HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
      HINT_IP="${HINT_IP:-127.0.0.1}"
    fi
    echo "${TAG} GF_OBS_LIVE_SERVICES=${GF_OBS_LIVE_SERVICES} (downstream while inject)"
    echo "${TAG} Foxglove → ws://${HINT_IP}:${PORT}  GMT Live → ws://${HINT_IP}:${LIVE_PORT}"
    if [[ "${LIVE_TEE}" == "1" ]]; then
      mkdir -p "$(dirname "${LIVE_SESSION}")"
      : > "${LIVE_SESSION}"
    fi
    (
      if [[ "${LIVE_TEE}" == "1" ]]; then
        "${TAP}" 2>"${LOG_DIR}/tap.log" \
          | tee "${LIVE_SESSION}" \
          | tee >(GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}") \
          | GMT bridge foxglove --ws --stdin --host "${HOST}" --port "${PORT}"
      else
        "${TAP}" 2>"${LOG_DIR}/tap.log" \
          | tee >(GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}") \
          | GMT bridge foxglove --ws --stdin --host "${HOST}" --port "${PORT}"
      fi
    ) &
    LIVE_FAN_PID=$!
  fi

  if [[ "${DRIVE_MODE}" == "playhead" || "${DRIVE_MODE}" == "controlled" || "${DRIVE_MODE}" == "wait" ]]; then
    LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "${TAG} playhead: inject listening 0.0.0.0:${INJ_PORT} (TCP)"
    echo "${TAG} 本机 GMT → Host=127.0.0.1 → 回灌 tcp:${INJ_PORT}；可同时连 Live ws:${GF_LIVE_PORT:-8766}"
    if [[ -n "${LAN_IP}" && "${LAN_IP}" != "127.0.0.1" ]]; then
      echo "${TAG} 远端 GMT → Host=${LAN_IP} → 回灌+Live 均可连"
    fi
    echo "${TAG} Ctrl+C 结束"
    wait "${INJ_PID}" || true
    if [[ -n "${LIVE_FAN_PID}" ]]; then
      kill "${LIVE_FAN_PID}" 2>/dev/null || true
    fi
    echo "${TAG} inject stopped; logs: ${LOG_DIR}/ (apps=${RUN_APPS})"
    exit 0
  fi
  # continuous: wait for inject to finish
  wait "${INJ_PID}" || true
  if [[ -n "${LIVE_FAN_PID}" ]]; then
    kill "${LIVE_FAN_PID}" 2>/dev/null || true
  fi
  echo "${TAG} inject finished; logs: ${LOG_DIR}/ (apps=${RUN_APPS})"
  exit 0
fi

echo "${TAG} fcm / uss / planning ..."
start_consumers "fcm,uss,planning"

# max_traj=0 → run forever
GF_PHM_FAULT_MS=0 "${GW}" 0 >"${LOG_DIR}/gateway.log" 2>&1 &
GW_PID=$!
sleep 0.5

if [[ "${LIVE_ON}" != "1" ]]; then
  echo "${TAG} live_tap off — main chain only. logs: ${LOG_DIR}/"
  echo "${TAG} (enable live_tap in gf-config A → Verify/compile → re-run for Foxglove)"
  wait "${GW_PID}" || true
  exit 0
fi

export GF_OBS_LIVE_SERVICES="${LIVE_SVCS}"
LIVE_PORT="${GF_LIVE_PORT:-8766}"
HINT_IP="127.0.0.1"
if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
  HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  HINT_IP="${HINT_IP:-<this-host-LAN-IP>}"
fi
echo "${TAG} GF_OBS_LIVE_SERVICES=${GF_OBS_LIVE_SERVICES}"
echo "${TAG} Foxglove Studio → ws://${HINT_IP}:${PORT}"
echo "${TAG} GMT GUI live → ws://${HINT_IP}:${LIVE_PORT}（窗内 host:port 连接）"
echo "${TAG} (GMT bridge is NOT ROS foxglove_bridge; main chain stays iceoryx)"

LIVE_SESSION="${GF_LIVE_SESSION:-${ROOT}/build/observability/session_live.jsonl}"
LIVE_TEE="${GF_LIVE_TEE:-1}"
if [[ "${LIVE_TEE}" == "1" ]]; then
  mkdir -p "$(dirname "${LIVE_SESSION}")"
  : > "${LIVE_SESSION}"
  echo "${TAG} live tee → ${LIVE_SESSION}"
fi
echo "${TAG} Ctrl+C 结束"

_live_fan() {
  if [[ "${LIVE_TEE}" == "1" ]]; then
    "${TAP}" 2>"${LOG_DIR}/tap.log" \
      | tee "${LIVE_SESSION}" \
      | tee >(GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}") \
      | GMT bridge foxglove --ws --stdin --host "${HOST}" --port "${PORT}"
  else
    "${TAP}" 2>"${LOG_DIR}/tap.log" \
      | tee >(GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}") \
      | GMT bridge foxglove --ws --stdin --host "${HOST}" --port "${PORT}"
  fi
}

_live_fan
