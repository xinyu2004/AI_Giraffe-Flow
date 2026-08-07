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
#   GF_INJECT_MODE=playhead bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#   # continuous (board-side file):
#   GF_INJECT_SESSION=projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl \
#     bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#   # B2 single-module (DUT only + inject):
#   GF_INJECT_MODE=playhead GF_INJECT_DUT=sensing.uss \
#     bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#
# Env:
#   GF_BUILD_DIR     default projects/.../build-sil
#   GF_WS_HOST       default 0.0.0.0
#   GF_WS_PORT       default 8765
#   GF_LIVE_PORT     default 8766 (GMT GUI live bridge)
#   GF_LIVE_SESSION  optional tee path (default ${BUILD}/observability/session_live.jsonl)
#   GF_OBS_OUT       observability root (default ${BUILD}/observability)
#   GF_SYNTH_BEV       default 1 — Foxglove live bridge composes BEV from EgoMotion/Trajectory
#   GF_SKIP_COMPILE=1  skip compile_sil (assume already built)
#   GF_INJECT_SESSION  continuous 必填；playhead 可选（GMT stream，可不设）
#   GF_INJECT_MODE     continuous (default) | playhead — playhead waits for GMT on GF_INJECT_PORT
#   GF_INJECT_PORT     default 8767 (playhead control TCP)
#   GF_INJECT_HOST     default 0.0.0.0 (playhead bind)
#   GF_INJECT_LIVE     default 1 — keep live_tap during inject
#                      1 = downstream only (exclude injectable EgoMotion)
#                      all|passthrough = keep full live whitelist (EgoMotion+…) for scenario demo
#                      0 = force live_tap OFF
#   GF_INJECT_SERVICES default EgoMotion (or auto from DUT requires ∩ injectable)
#   GF_INJECT_DUT      B2: SOR process id (e.g. sensing.uss) → only that app + inject
#   GF_INJECT_APPS     B2 override: comma list uss,fcm,planning (skip SOR lookup)
#   GF_INJECT_MAX_EVENTS  continuous: hard max events (default ~20000); ignore for playhead
#   GF_INJECT_WINDOW_MAX_EVENTS  playhead: events per A/B window (default 256, clamp 16–4096)
#   GF_INJECT_LOOP     continuous: 1 = replay from start until signal; playhead uses GMT UI loop
#   GF_SIL_KILL_STALE  default 1 — 启动前释放被旧 SIL/GMT 占用的 8765/8766/8767/13400
#                      设 0 则端口忙时直接失败并提示如何手动停
#   GF_DOIP            default auto — 1/0 强制开/关；auto = deploy_config kDoip
#   GF_DOIP_PORT       default from deploy_config kDoipTcpPort（通常 13400）
#   GF_PHM_FAULT_MS    DoIP 开且未显式设置时默认 500 — 真实 AliveMissed → GF_PER_DIR → DEM 0x19
#   GF_PHM_FAULT_TARGET  默认 uss（fcm|uss|planning|gateway）；其它进程 fault=0
#                      关闭 PHM 注入：GF_PHM_FAULT_MS=0
#   frame_ingest（行为）：compose→frame_ingest_config.hpp（勿手改 JSON）
#   调试覆盖仍可用 GF_FRAME_SOURCE / GF_START_CARLA_BRIDGE / GF_CARLA_*（见 SIM_SPIKE.md）
#   # playhead (GMT stream; session file optional):
#   GF_INJECT_MODE=playhead bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#   # then GMT gui → open session → 回灌 tab → connect 127.0.0.1:8767
#   # continuous still needs a file:
#   GF_INJECT_SESSION=… bash …/run_sil.sh
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
# Remember whether caller set PHM fault (empty = unset) before applying defaults.
_PHM_FAULT_USER="${GF_PHM_FAULT_MS-}"
export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-0}"
export GF_PHM_FAULT_TARGET="${GF_PHM_FAULT_TARGET:-uss}"
export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
# COVESA libdlt from in-tree build (not apt)
_DLT_LIBDIR="${BUILD}/_dep-manifest/dlt-daemon/src/lib"
if [[ -d "${_DLT_LIBDIR}" ]]; then
  export LD_LIBRARY_PATH="${_DLT_LIBDIR}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi
# Shared collector NDJSON + per (DEM DTC) for GMT OTA/UDS
_COLLECTOR_DEFAULT="${BUILD}/runtime/collector/events.ndjson"
mkdir -p "$(dirname "${_COLLECTOR_DEFAULT}")"
export GF_COLLECTOR_STORE="${GF_COLLECTOR_STORE:-${_COLLECTOR_DEFAULT}}"
_PER_DEFAULT="${BUILD}/runtime/per"
mkdir -p "${_PER_DEFAULT}"
export GF_PER_DIR="${GF_PER_DIR:-${_PER_DEFAULT}}"

INJECT_SESSION="${GF_INJECT_SESSION:-}"
INJECT_ON=0
INJECT_MODE="off" # off | b1 | b2
DRIVE_HINT="${GF_INJECT_MODE:-continuous}"
if [[ -n "${INJECT_SESSION}" ]]; then
  INJECT_ON=1
  if [[ -n "${GF_INJECT_DUT:-}" || -n "${GF_INJECT_APPS:-}" ]]; then
    INJECT_MODE="b2"
  else
    INJECT_MODE="b1"
  fi
elif [[ "${DRIVE_HINT}" == "playhead" || "${DRIVE_HINT}" == "controlled" || "${DRIVE_HINT}" == "wait" ]]; then
  # playhead stream: session file optional — GMT owns full JSONL
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

# Behavior freeze from compose hpp (not tip JSON / .env).
DEPLOY_HPP="${PROJECT_DIR}/generated/include/gf_gen/deploy_config.hpp"
FRAME_HPP="${PROJECT_DIR}/generated/include/gf_gen/frame_ingest_config.hpp"
_gf_hpp_bool() {
  local hpp="$1" key="$2" default="$3"
  if [[ -f "${hpp}" ]] && grep -qE "inline constexpr bool ${key} = true" "${hpp}"; then
    echo 1
  elif [[ -f "${hpp}" ]] && grep -qE "inline constexpr bool ${key} = false" "${hpp}"; then
    echo 0
  else
    echo "${default}"
  fi
}
_gf_hpp_cstr() {
  local hpp="$1" key="$2" default="$3"
  if [[ -f "${hpp}" ]]; then
    local v
    v="$(sed -nE "s/.*inline constexpr const char\* ${key} = \"([^\"]*)\".*/\1/p" "${hpp}" | head -1)"
    if [[ -n "${v}" ]]; then
      echo "${v}"
      return
    fi
  fi
  echo "${default}"
}
_gf_hpp_u32() {
  local hpp="$1" key="$2" default="$3"
  if [[ -f "${hpp}" ]]; then
    local v
    v="$(sed -nE "s/.*inline constexpr std::uint32_t ${key} = ([0-9]+)u?.*/\1/p" "${hpp}" | head -1)"
    if [[ -n "${v}" ]]; then
      echo "${v}"
      return
    fi
  fi
  echo "${default}"
}
# frame_ingest → export GF_* for carla_bridge child; user-set GF_* wins (debug).
if [[ ! -f "${FRAME_HPP}" ]]; then
  echo "${TAG} WARN: missing ${FRAME_HPP} — run compose so frame_ingest is frozen" >&2
fi
if [[ -z "${GF_START_CARLA_BRIDGE+x}" ]]; then
  export GF_START_CARLA_BRIDGE="$(_gf_hpp_bool "${FRAME_HPP}" kBridgeEnabled 0)"
fi
if [[ -z "${GF_CARLA_BRIDGE_DRY_RUN+x}" ]]; then
  export GF_CARLA_BRIDGE_DRY_RUN="$(_gf_hpp_bool "${FRAME_HPP}" kBridgeDryRun 1)"
fi
if [[ -z "${GF_CARLA_DEMO_LC+x}" ]]; then
  export GF_CARLA_DEMO_LC="$(_gf_hpp_bool "${FRAME_HPP}" kDemoLaneChange 0)"
fi
if [[ -z "${GF_FRAME_SOURCE+x}" ]]; then
  export GF_FRAME_SOURCE="$(_gf_hpp_cstr "${FRAME_HPP}" kFrameSource none)"
fi
if [[ -z "${GF_PERCEPTION_BACKEND+x}" ]]; then
  export GF_PERCEPTION_BACKEND="$(_gf_hpp_cstr "${FRAME_HPP}" kPerceptionBackend stub)"
fi
if [[ -z "${GF_CARLA_FRAME_PATH+x}" ]]; then
  export GF_CARLA_FRAME_PATH="$(_gf_hpp_cstr "${FRAME_HPP}" kFramePath /tmp/gf_front.rgb)"
fi
if [[ -z "${GF_CARLA_CMD_PATH+x}" ]]; then
  export GF_CARLA_CMD_PATH="$(_gf_hpp_cstr "${FRAME_HPP}" kCmdPath /tmp/gf_carla_cmd.json)"
fi
if [[ -z "${GF_CARLA_DEMO_LC_SEC+x}" ]]; then
  export GF_CARLA_DEMO_LC_SEC="$(_gf_hpp_u32 "${FRAME_HPP}" kDemoLaneChangeSec 8)"
fi
echo "${TAG} frame_ingest: hpp source=${GF_FRAME_SOURCE} bridge=${GF_START_CARLA_BRIDGE} dry=${GF_CARLA_BRIDGE_DRY_RUN}"

# Flow/EM hints from deploy_config.hpp (soft for Flow; EM uses compiled table).
_gf_deploy_bool() {
  _gf_hpp_bool "${DEPLOY_HPP}" "$1" "$2"
}
if [[ ! -f "${DEPLOY_HPP}" ]]; then
  echo "${TAG} WARN: missing ${DEPLOY_HPP} — run compose + compile_sil (EM needs GF_HAS_DEPLOY_CONFIG)" >&2
fi
EM_ON="$(_gf_deploy_bool kEm 1)"
DLT_ON="$(_gf_deploy_bool kDlt 0)"
IOX_ON="$(_gf_deploy_bool kRouDi 0)"
LIVE_ON="$(_gf_deploy_bool kLiveTap 0)"
DOIP_ON="$(_gf_deploy_bool kDoip 0)"
# Soft Flow overrides (debug only; not product acceptance).
if [[ "${GF_LIVE_TAP:-}" == "0" || "${GF_LIVE_TAP:-}" == "off" ]]; then LIVE_ON=0; fi
if [[ "${GF_LIVE_TAP:-}" == "1" || "${GF_LIVE_TAP:-}" == "on" ]]; then LIVE_ON=1; fi
echo "${TAG} deploy_config: em=${EM_ON} dlt=${DLT_ON} roudi=${IOX_ON} live=${LIVE_ON} doip=${DOIP_ON}"

OBS_JSON="${PROJECT_DIR}/generated/observability.json"
SOR_JSON="${PROJECT_DIR}/gf.sor.json"
# Whitelist services from observability.json (OK — not behavior enablement).
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
svcs = [str(x).strip() for x in (live.get("services") or []) if str(x).strip()]
print("LIVE_SVCS=%s" % ",".join(svcs))
PY
)"
else
  echo "${TAG} WARN: missing ${OBS_JSON} — live service whitelist empty" >&2
fi
if [[ "${LIVE_ON}" == "1" && -z "${LIVE_SVCS}" ]]; then
  echo "${TAG} WARN: live_tap frozen ON but services list empty — Foxglove may be idle" >&2
fi

# DoIP: enable + params from deploy_config.hpp (debug GF_DOIP / GF_DOIP_* still allowed).
if [[ "${GF_DOIP:-}" == "0" || "${GF_DOIP:-}" == "off" ]]; then
  DOIP_ON=0
elif [[ "${GF_DOIP:-}" == "1" || "${GF_DOIP:-}" == "on" ]]; then
  DOIP_ON=1
fi
_gf_hpp_int() {
  local hpp="$1" key="$2" default="$3"
  if [[ -f "${hpp}" ]]; then
    local v
    v="$(sed -nE "s/.*inline constexpr std::uint(16|32)_t ${key} = (0[xX][0-9A-Fa-f]+|[0-9]+)u?.*/\2/p" "${hpp}" | head -1)"
    if [[ -n "${v}" ]]; then
      printf '%d\n' "${v}"
      return
    fi
  fi
  echo "${default}"
}
if [[ -z "${GF_DOIP_PORT+x}" ]]; then
  export GF_DOIP_PORT="$(_gf_hpp_int "${DEPLOY_HPP}" kDoipTcpPort 13400)"
fi
DOIP_PORT="${GF_DOIP_PORT}"
export GF_DOIP_PORT

# Inject replaces gateway. Live tap may stay on.
if [[ "${INJECT_ON}" == "1" ]]; then
  echo "${TAG} inject mode=${INJECT_MODE}: gateway OFF (session=${INJECT_SESSION:-GMT-stream})"
  _INJ_LIVE="${GF_INJECT_LIVE:-1}"
  if [[ "${_INJ_LIVE}" == "0" ]]; then
    LIVE_ON=0
    echo "${TAG} GF_INJECT_LIVE=0 → live_tap forced OFF"
  elif [[ "${LIVE_ON}" == "1" ]]; then
    if [[ "${_INJ_LIVE}" == "all" || "${_INJ_LIVE}" == "passthrough" || "${_INJ_LIVE}" == "full" ]]; then
      # Scenario / ADAS demo: keep EgoMotion on Foxglove/GMT Live (same as whitelist)
      echo "${TAG} inject+live: GF_INJECT_LIVE=${_INJ_LIVE} → full tap → ${LIVE_SVCS}"
    else
      # Default G3: only订下游 — 从 live 白名单去掉正在灌的服务（MVP：EgoMotion）
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
        echo "${TAG} inject+live: downstream tap only → ${LIVE_SVCS} (excluded injectable; GF_INJECT_LIVE=all to keep EgoMotion)"
      else
        echo "${TAG} inject+live: no downstream services left after filter — live_tap OFF"
        echo "${TAG} tip: for scenario demo use GF_INJECT_LIVE=all bash …/run_sil.sh"
      fi
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
    apps = ["fcm", "planning"]

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
TAP="${BUILD}/apps/debug_bridge/iox_obs_tap/gf_iox_obs_tap"
INJ="${BUILD}/apps/debug_bridge/iox_obs_inject/gf_iox_obs_inject"
DOIP="${BUILD}/gf_doip_ota_server"
DLT_DAEMON="${BUILD}/_dep-manifest/dlt-daemon/src/daemon/dlt-daemon"
DLT_RECEIVE="${BUILD}/_dep-manifest/dlt-daemon/src/console/dlt-receive"
EM_BIN="${BUILD}/middleware/exec/gf_em_daemon"
# EM/Flow flags already from deploy_config.hpp. Script starts EM only.
IOX_TOML="${PROJECT_DIR}/generated/iox_roudi.toml"

NEED_BINS=()
if [[ "${EM_ON}" == "1" ]]; then
  NEED_BINS+=("${EM_BIN}")
  [[ "${IOX_ON}" == "1" ]] && NEED_BINS+=("${ROUDI}")
  [[ "${DLT_ON}" == "1" ]] && NEED_BINS+=("${DLT_DAEMON}")
  NEED_BINS+=("${GW}" "${FCM}" "${USS}" "${PLAN}")
else
  echo "${TAG} ERROR: kEm=false — product SIL requires exec/EM (gf-config runtime_modules)" >&2
  exit 1
fi
if [[ "${INJECT_ON}" == "1" ]]; then
  NEED_BINS+=("${INJ}")
  DRIVE_CHECK="${GF_INJECT_MODE:-continuous}"
  if [[ -z "${INJECT_SESSION}" ]]; then
    if [[ "${DRIVE_CHECK}" != "playhead" && "${DRIVE_CHECK}" != "controlled" && "${DRIVE_CHECK}" != "wait" ]]; then
      echo "${TAG} ERROR: continuous inject requires GF_INJECT_SESSION" >&2
      exit 1
    fi
    echo "${TAG} playhead stream: no GF_INJECT_SESSION (GMT owns session)"
  elif [[ ! -f "${INJECT_SESSION}" ]]; then
    echo "${TAG} ERROR: GF_INJECT_SESSION not a file: ${INJECT_SESSION}" >&2
    exit 1
  fi
fi
if [[ "${LIVE_ON}" == "1" ]]; then
  NEED_BINS+=("${TAP}")
fi
if [[ "${DOIP_ON}" == "1" ]]; then
  NEED_BINS+=("${DOIP}")
fi
for bin in "${NEED_BINS[@]}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "Missing executable: ${bin}" >&2
    echo "Build first: bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh" >&2
    if [[ "${bin}" == "${TAP}" ]]; then
      echo "live_tap is on but tap binary missing — check profile=vehicle-debug + live in gf-config." >&2
    fi
    if [[ "${bin}" == "${INJ}" ]]; then
      echo "inject binary missing — vehicle-debug compose should add debug_bridge/iox_obs_inject; re-run compile_sil." >&2
    fi
    if [[ "${bin}" == "${DOIP}" ]]; then
      echo "DoIP OTA server missing — rebuild (target gf_doip_ota_server) or set GF_DOIP=0." >&2
    fi
    if [[ "${bin}" == "${ROUDI}" ]]; then
      echo "iox-roudi missing — req.bindings has iceoryx; rebuild iceoryx." >&2
    fi
    if [[ "${bin}" == "${EM_BIN}" ]]; then
      echo "gf_em_daemon missing — rebuild middleware/exec." >&2
    fi
    exit 1
  fi
done
if [[ "${IOX_ON}" == "1" && ! -f "${IOX_TOML}" ]]; then
  echo "${TAG} ERROR: missing ${IOX_TOML} (compose with req.bindings iceoryx)" >&2
  exit 1
fi
if [[ ! -f "${DEPLOY_HPP}" ]]; then
  echo "${TAG} ERROR: missing ${DEPLOY_HPP} (compose) — EM needs compile-time deploy_config" >&2
  exit 1
fi

LOG_DIR="${BUILD}/runtime/logs"
mkdir -p "${LOG_DIR}"
# SIL local file sink (optional); upstream path for Host Info is DLT via gf_dlt_log.
export GF_LOG_DIR="${GF_LOG_DIR:-${LOG_DIR}}"
export GF_LOG_FILE="${GF_LOG_FILE:-${LOG_DIR}/giraffe_modules.log}"
: >"${LOG_DIR}/host.log"
: >"${GF_LOG_FILE}"
GF_DLT_LOG="${BUILD}/middleware/log/gf_dlt_log"

# Host-phase Info → stdout + host.log + file；若 dlt-daemon 已起则再经 gf_dlt_log → DLT
# Never block SIL boot on DLT: gf_dlt_log can futex-hang on /tmp/dlt after apps attach.
host_info() {
  local msg="$*"
  local line="log: [INFO] host ${msg}"
  echo "${line}"
  echo "${line}" >>"${LOG_DIR}/host.log"
  echo "${line}" >>"${GF_LOG_FILE}"
  if [[ "${DLT_ON}" == "1" && -x "${GF_DLT_LOG}" && -n "${DLT_PID:-}" ]] && kill -0 "${DLT_PID}" 2>/dev/null; then
    if command -v timeout >/dev/null 2>&1; then
      timeout 0.8 env GF_DLT_APP_ID=HOST GF_PLATFORM_DIR="${GF_PLATFORM_DIR}" \
        GF_LOG_DIR="${GF_LOG_DIR}" GF_LOG_FILE="${GF_LOG_FILE}" \
        "${GF_DLT_LOG}" -a HOST -c host "${msg}" >/dev/null 2>&1 || true
    else
      GF_DLT_APP_ID=HOST GF_PLATFORM_DIR="${GF_PLATFORM_DIR}" \
        GF_LOG_DIR="${GF_LOG_DIR}" GF_LOG_FILE="${GF_LOG_FILE}" \
        "${GF_DLT_LOG}" -a HOST -c host "${msg}" >/dev/null 2>&1 &
    fi
  fi
}

LIVE_PORT="${GF_LIVE_PORT:-8766}"
INJ_PORT="${GF_INJECT_PORT:-8767}"

# 释放上次 Ctrl+C 未清干净 / 重复开跑 留下的 bridge / inject / DoIP（EADDRINUSE / iceoryx same-name）
gf_sil_preflight_ports() {
  export GF_SIL_PORT_WS="${PORT}"
  export GF_SIL_PORT_LIVE="${LIVE_PORT}"
  export GF_SIL_PORT_INJ="${INJ_PORT}"
  export GF_SIL_PORT_DOIP="${DOIP_PORT}"
  export GF_SIL_KILL_STALE="${GF_SIL_KILL_STALE:-1}"
  export GF_SIL_INJECT_ON="${INJECT_ON}"
  export GF_SIL_LIVE_ON="${LIVE_ON}"
  export GF_SIL_DOIP_ON="${DOIP_ON}"
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

def ancestor_pids(start: int) -> set[int]:
    """Exclude self + parents (e.g. bash run_sil / timeout wrapping this python)."""
    seen: set[int] = set()
    pid = start
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
                # pid (comm) state ppid ... — comm may contain spaces/parens
                body = f.read()
            rparen = body.rfind(")")
            if rparen < 0:
                break
            parts = body[rparen + 2 :].split()
            pid = int(parts[1])  # ppid
        except (OSError, ValueError, IndexError):
            break
    return seen

def pids_matching(pattern: str) -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    me = ancestor_pids(os.getpid())
    return [int(x) for x in out.split() if int(x) not in me]

wanted = set()
if os.environ.get("GF_SIL_LIVE_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_WS"]))
    wanted.add(int(os.environ["GF_SIL_PORT_LIVE"]))
if os.environ.get("GF_SIL_INJECT_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_INJ"]))
if os.environ.get("GF_SIL_DOIP_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_DOIP"]))

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
    if os.environ.get("GF_SIL_DOIP_ON") == "1" and kill_stale:
        subprocess.run(
            ["pkill", "-f", "gf_doip_ota_server"],
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
        or "gf_doip_ota_server" in cmd
        or n.startswith("gf_iox_obs")
        or n.startswith("gf_doip")
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
    ["pkill", "-f", "gf_doip_ota_server"],
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
  for pid in "${LIVE_FAN_PID:-}" "${TAP_PID:-}" "${INJ_PID:-}" "${DOIP_PID:-}" "${CARLA_BRIDGE_PID:-}" "${EM_PID:-}" "${GW_PID:-}" "${PLAN_PID:-}" "${FCM_PID:-}" "${USS_PID:-}" "${ROUDI_PID:-}" "${DLT_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null
  done
  # EM children (dlt/RouDi/apps) may outlive the daemon briefly
  if [[ -n "${EM_PID:-}" ]]; then
    pkill -P "${EM_PID}" >/dev/null 2>&1 || true
  fi
  # process-substitution GMT bridges may outlive the fan pipeline
  if [[ "${LIVE_ON}" == "1" ]]; then
    fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
    fuser -k "${LIVE_PORT}/tcp" >/dev/null 2>&1 || true
  fi
  if [[ "${INJECT_ON}" == "1" ]]; then
    fuser -k "${INJ_PORT}/tcp" >/dev/null 2>&1 || true
    pkill -f gf_iox_obs_inject >/dev/null 2>&1 || true
  fi
  if [[ "${DOIP_ON}" == "1" ]]; then
    fuser -k "${DOIP_PORT}/tcp" >/dev/null 2>&1 || true
    pkill -f gf_doip_ota_server >/dev/null 2>&1 || true
  fi
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "${TAG} run_sil: platform=${GF_PLATFORM_DIR} live=${LIVE_ON} inject=${INJECT_MODE} doip=${DOIP_ON}:${DOIP_PORT} em=${EM_ON}"

# =============================================================================
# --- EM (entry) -----------------------------------------------------------------
# EM scope: Giraffe platform daemons (dlt?/RouDi?/…) + SOA apps (deploy_config.hpp).
# NOT EM: tap / Foxglove / GMT inject / frame_ingest / carla_bridge / DoIP — those
# are run_sil Flow/GMT segments (or app compile-time freeze), not em_launch rows.
# systemd (board) is only a protection layer around the same EM entry.
# =============================================================================
DLT_PID=""
ROUDI_PID=""
EM_PID=""
host_info "run_sil begin platform=${GF_PLATFORM_DIR} live=${LIVE_ON} inject=${INJECT_MODE} doip=${DOIP_ON}:${DOIP_PORT} em=${EM_ON}"

# Stale dlt/RouDi + IPC reclaim is inside EM StartAll (before Spawn host.*).

export GF_IOX_TOML="${IOX_TOML}"
export GF_EM_LOG_DIR="${LOG_DIR}/em"
mkdir -p "${GF_EM_LOG_DIR}"
# PHM fault defaults must be in env *before* EM spawns apps (children inherit).
if [[ "${DOIP_ON}" == "1" && -z "${_PHM_FAULT_USER}" ]]; then
  export GF_PHM_FAULT_MS=500
  export GF_PHM_FAULT_TARGET="${GF_PHM_FAULT_TARGET:-uss}"
fi
host_info "start EM mode=deploy_config dlt=${DLT_ON} roudi=${IOX_ON}"
echo "${TAG} [EM] gf_em_daemon (deploy_config.hpp) → dlt?=${DLT_ON} RouDi?=${IOX_ON} → apps"
: >"${LOG_DIR}/em_daemon.stdout"
"${EM_BIN}" \
  --platform "${GF_PLATFORM_DIR}" \
  --build-dir "${BUILD}" \
  --log-dir "${GF_EM_LOG_DIR}" \
  --deadline-ms 0 \
  >"${LOG_DIR}/em_daemon.stdout" 2>&1 &
EM_PID=$!
# Wait until EM has spawned planning (or timeout)
_em_ready=0
for _i in $(seq 1 50); do
  if ! kill -0 "${EM_PID}" 2>/dev/null; then
    host_info "EM exited early; see ${LOG_DIR}/em_daemon.stdout"
    echo "${TAG} EM failed; see ${LOG_DIR}/em_daemon.stdout" >&2
    cat "${LOG_DIR}/em_daemon.stdout" >&2 || true
    exit 1
  fi
  if grep -q 'em_daemon: spawned name=planning.driving' "${LOG_DIR}/em_daemon.stdout" 2>/dev/null \
    || grep -q 'em_daemon: spawned name=planning.driving' "${GF_EM_LOG_DIR}/giraffe_modules.log" 2>/dev/null; then
    _em_ready=1
    break
  fi
  sleep 0.2
done
if [[ "${_em_ready}" != "1" ]]; then
  # Accept StartAll done as weaker ready signal
  if grep -q 'StartAll done' "${LOG_DIR}/em_daemon.stdout" 2>/dev/null \
    || grep -q 'StartAll done' "${GF_EM_LOG_DIR}/giraffe_modules.log" 2>/dev/null; then
    _em_ready=1
  fi
fi
if [[ "${_em_ready}" != "1" ]]; then
  host_info "EM spawn timeout; see ${LOG_DIR}/em_daemon.stdout"
  echo "${TAG} EM spawn timeout; see ${LOG_DIR}/em_daemon.stdout / ${GF_EM_LOG_DIR}" >&2
  tail -n 80 "${LOG_DIR}/em_daemon.stdout" >&2 || true
  exit 1
fi
host_info "EM ok pid=${EM_PID} (dlt/RouDi/apps via deploy_config)"
# =============================================================================
# --- Flow / GMT (not EM) — DoIP / carla_bridge / live Foxglove -----------------
# =============================================================================

if [[ "${DOIP_ON}" == "1" ]]; then
  # GMT DEM: real PHM AliveMissed in apps → PersistDtc → shared GF_PER_DIR;
  # DoIP 0x19 uses ReloadDtcsFromPer (no fake seed).
  # Opt-out: GF_PHM_FAULT_MS=0 before run_sil.
  if [[ -z "${_PHM_FAULT_USER}" ]]; then
    export GF_PHM_FAULT_MS=500
    export GF_PHM_FAULT_TARGET="${GF_PHM_FAULT_TARGET:-uss}"
  fi
  echo "${TAG} DoIP OTA server → TCP ${DOIP_PORT} (GMT OTA: 127.0.0.1:${DOIP_PORT})"
  echo "${TAG} DEM: PHM fault_ms=${GF_PHM_FAULT_MS} target=${GF_PHM_FAULT_TARGET} per=${GF_PER_DIR}"
  host_info "start DoIP OTA server port=${DOIP_PORT} per=${GF_PER_DIR} phm_fault_ms=${GF_PHM_FAULT_MS} target=${GF_PHM_FAULT_TARGET}"
  : >"${LOG_DIR}/doip_ota.log"
  # DoIP/UDS params from deploy_config.hpp (export for gf_doip_ota_server).
  if [[ -z "${GF_DIAG_S3_SERVER_MS+x}" ]]; then
    export GF_DIAG_S3_SERVER_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagS3ServerMs 5000)"
  fi
  if [[ -z "${GF_DIAG_TP_PERIOD_MS+x}" ]]; then
    export GF_DIAG_TP_PERIOD_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagTesterPresentPeriodMs 2000)"
  fi
  if [[ -z "${GF_DIAG_P2_SERVER_MS+x}" ]]; then
    export GF_DIAG_P2_SERVER_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagP2ServerMs 50)"
  fi
  if [[ -z "${GF_DIAG_P2STAR_SERVER_MS+x}" ]]; then
    export GF_DIAG_P2STAR_SERVER_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagP2StarServerMs 5000)"
  fi
  if [[ -z "${GF_DIAG_SECURITY_DELAY_MS+x}" ]]; then
    export GF_DIAG_SECURITY_DELAY_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagSecurityDelayMs 10000)"
  fi
  if [[ -z "${GF_OTA_TRANSFER_MODE+x}" ]]; then
    export GF_OTA_TRANSFER_MODE="$(_gf_hpp_cstr "${DEPLOY_HPP}" kOtaTransferMode request_file_transfer)"
  fi
  if [[ -z "${GF_OTA_REQUIRE_PROG_SESSION+x}" ]]; then
    export GF_OTA_REQUIRE_PROG_SESSION="$(_gf_hpp_bool "${DEPLOY_HPP}" kOtaRequireProgSession 1)"
  fi
  if [[ -z "${GF_OTA_REQUIRE_SECURITY+x}" ]]; then
    export GF_OTA_REQUIRE_SECURITY="$(_gf_hpp_bool "${DEPLOY_HPP}" kOtaRequireSecurity 1)"
  fi
  if [[ -z "${GF_OTA_MAX_BLOCK+x}" ]]; then
    export GF_OTA_MAX_BLOCK="$(_gf_hpp_int "${DEPLOY_HPP}" kOtaMaxBlockLength 1024)"
  fi
  if [[ -z "${GF_DOIP_LOGICAL_ADDR+x}" ]]; then
    export GF_DOIP_LOGICAL_ADDR="$(_gf_hpp_int "${DEPLOY_HPP}" kDoipLogicalAddr 3584)"
  fi
  if [[ -z "${GF_DOIP_TESTER_ADDR+x}" ]]; then
    export GF_DOIP_TESTER_ADDR="$(_gf_hpp_int "${DEPLOY_HPP}" kDoipTesterAddr 3712)"
  fi
  # Mirror UDS steps to terminal (same lines as GMT OTA log) + keep file
  (
    if command -v stdbuf >/dev/null 2>&1; then
      stdbuf -oL -eL env GF_DOIP_PORT="${DOIP_PORT}" "${DOIP}"
    else
      env GF_DOIP_PORT="${DOIP_PORT}" "${DOIP}"
    fi
  ) > >(tee -a "${LOG_DIR}/doip_ota.log" >&2) 2>&1 &
  DOIP_PID=$!
  sleep 0.3
  if ! kill -0 "${DOIP_PID}" 2>/dev/null; then
    host_info "DoIP server failed; see ${LOG_DIR}/doip_ota.log"
    echo "${TAG} DoIP server failed; see ${LOG_DIR}/doip_ota.log" >&2
    cat "${LOG_DIR}/doip_ota.log" >&2 || true
    exit 1
  fi
  host_info "DoIP ok pid=${DOIP_PID} port=${DOIP_PORT}"
fi

# Per-process PHM fault (others get 0). Target via GF_PHM_FAULT_TARGET.
_fault_ms_for() {
  local name="$1"
  if [[ "${GF_PHM_FAULT_MS}" == "0" ]]; then
    echo 0
  elif [[ "${name}" == "${GF_PHM_FAULT_TARGET}" ]]; then
    echo "${GF_PHM_FAULT_MS}"
  else
    echo 0
  fi
}

start_consumers() {
  local apps="${1:-fcm,planning}"
  local a
  host_info "spawn apps (direct, no EM) apps=${apps}"
  IFS=',' read -r -a _arr <<< "${apps}"
  for a in "${_arr[@]}"; do
    case "${a}" in
      fcm)
        echo "${TAG} start fcm (PHM fault_ms=$(_fault_ms_for fcm))"
        host_info "start app=fcm fault_ms=$(_fault_ms_for fcm)"
        # stdbuf: line-buffer stdout so smoke/timeout kill still leaves Trajectory lines on disk
        if command -v stdbuf >/dev/null 2>&1; then
          GF_DLT_APP_ID=FCM_ GF_PHM_FAULT_MS="$(_fault_ms_for fcm)" stdbuf -oL -eL "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
        else
          GF_DLT_APP_ID=FCM_ GF_PHM_FAULT_MS="$(_fault_ms_for fcm)" "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
        fi
        FCM_PID=$!
        ;;
      uss)
        echo "${TAG} start uss (PHM fault_ms=$(_fault_ms_for uss))"
        host_info "start app=uss fault_ms=$(_fault_ms_for uss)"
        if command -v stdbuf >/dev/null 2>&1; then
          GF_DLT_APP_ID=USS_ GF_PHM_FAULT_MS="$(_fault_ms_for uss)" stdbuf -oL -eL "${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
        else
          GF_DLT_APP_ID=USS_ GF_PHM_FAULT_MS="$(_fault_ms_for uss)" "${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
        fi
        USS_PID=$!
        ;;
      planning)
        echo "${TAG} start planning (PHM fault_ms=$(_fault_ms_for planning))"
        host_info "start app=planning fault_ms=$(_fault_ms_for planning)"
        if command -v stdbuf >/dev/null 2>&1; then
          GF_DLT_APP_ID=PLAN GF_PHM_FAULT_MS="$(_fault_ms_for planning)" stdbuf -oL -eL "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
        else
          GF_DLT_APP_ID=PLAN GF_PHM_FAULT_MS="$(_fault_ms_for planning)" "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
        fi
        PLAN_PID=$!
        ;;
    esac
  done
  sleep 0.5
}

if [[ "${INJECT_ON}" == "1" ]]; then
  # GMT inject is not EM scope (no inject/tap in em_launch). Stop EM so product
  # gateway does not dual-publish with inject; Flow starts RouDi+consumers+inject.
  echo "${TAG} GMT inject (Flow, not EM): stop EM; RouDi+consumers+inject"
  if [[ -n "${EM_PID:-}" ]]; then
    kill "${EM_PID}" 2>/dev/null || true
    pkill -P "${EM_PID}" >/dev/null 2>&1 || true
    wait "${EM_PID}" 2>/dev/null || true
    EM_PID=""
  fi
  if [[ "${IOX_ON}" == "1" ]]; then
    : >"${LOG_DIR}/roudi.log"
    "${ROUDI}" -c "${IOX_TOML}" >"${LOG_DIR}/roudi.log" 2>&1 &
    ROUDI_PID=$!
    sleep 0.8
  fi
  start_consumers "${RUN_APPS}"
  DRIVE_MODE="${GF_INJECT_MODE:-continuous}"
  INJ_PORT="${GF_INJECT_PORT:-8767}"
  INJ_HOST="${GF_INJECT_HOST:-0.0.0.0}"
  if [[ -n "${INJECT_SESSION}" ]]; then
    echo "${TAG} inject from ${INJECT_SESSION} (services=${GF_INJECT_SERVICES} topology=${INJECT_MODE} drive=${DRIVE_MODE})"
    export GF_INJECT_SESSION="${INJECT_SESSION}"
  else
    echo "${TAG} inject playhead stream (no session file; services=${GF_INJECT_SERVICES} topology=${INJECT_MODE})"
    unset GF_INJECT_SESSION || true
  fi
  export GF_INJECT_MODE="${DRIVE_MODE}"
  export GF_INJECT_PORT="${INJ_PORT}"
  export GF_INJECT_HOST="${INJ_HOST}"
  # Plain listen hint; colored LISTENING comes from inject (/dev/tty)
  if [[ -t 2 ]]; then
    export GF_STATUS_COLOR=1
  fi
  echo "${TAG} [GMT Inject] listen tcp://0.0.0.0:${INJ_PORT} (playhead)" >&2
  : >"${LOG_DIR}/inject.log"
  INJ_FIFO="${LOG_DIR}/inject.fifo"
  rm -f "${INJ_FIFO}"
  mkfifo "${INJ_FIFO}"
  # tee starts reading before inject writes → no lost LISTENING/CONNECTED lines
  tee -a "${LOG_DIR}/inject.log" <"${INJ_FIFO}" >&2 &
  INJ_TEE_PID=$!
  if command -v stdbuf >/dev/null 2>&1; then
    _INJ_RUN=(stdbuf -oL -eL "${INJ}")
  else
    _INJ_RUN=("${INJ}")
  fi
  if [[ -n "${INJECT_SESSION}" ]]; then
    GF_INJECT_SESSION="${INJECT_SESSION}" \
      GF_INJECT_MODE="${DRIVE_MODE}" \
      GF_INJECT_PORT="${INJ_PORT}" \
      GF_INJECT_HOST="${INJ_HOST}" \
      "${_INJ_RUN[@]}" "${INJECT_SESSION}" >"${INJ_FIFO}" 2>&1 &
  else
    # playhead stream-only: no argv path
    GF_INJECT_MODE="${DRIVE_MODE}" \
      GF_INJECT_PORT="${INJ_PORT}" \
      GF_INJECT_HOST="${INJ_HOST}" \
      "${_INJ_RUN[@]}" >"${INJ_FIFO}" 2>&1 &
  fi
  INJ_PID=$!

  LIVE_FAN_PID=""
  if [[ "${LIVE_ON}" == "1" ]]; then
    export GF_OBS_LIVE_SERVICES="${LIVE_SVCS}"
    LIVE_PORT="${GF_LIVE_PORT:-8766}"
    LIVE_SESSION="${GF_LIVE_SESSION:-$(gf_obs_dir)/session_live.jsonl}"
    LIVE_TEE="${GF_LIVE_TEE:-1}"
    HINT_IP="127.0.0.1"
    if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
      HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
      HINT_IP="${HINT_IP:-127.0.0.1}"
    fi
    echo "${TAG} live services=${GF_OBS_LIVE_SERVICES}"
    echo "${TAG} listen Foxglove ws://${HINT_IP}:${PORT}  GMT-Live ws://${HINT_IP}:${LIVE_PORT}"
    # BEV from EgoMotion/Trajectory only. Scenario JSONL → GMT Open session / Inject
    # (or GF_INJECT_SESSION for continuous); not attached here.
    _FOX_BEV=()
    if [[ "${GF_SYNTH_BEV:-1}" != "0" ]]; then
      _FOX_BEV=(--synth-bev)
      echo "${TAG} Foxglove --synth-bev (EgoMotion/Trajectory → /gf/camera/front/compressed; GF_SYNTH_BEV=0 to disable)"
    fi
    if [[ "${LIVE_TEE}" == "1" ]]; then
      mkdir -p "$(dirname "${LIVE_SESSION}")"
      : > "${LIVE_SESSION}"
    fi
    # Same fan isolation as non-inject path: GMT close must not kill Foxglove.
    _tee_fan() {
      if tee --help 2>&1 | grep -q -- '--output-error'; then
        tee --output-error=warn "$@"
      else
        tee "$@"
      fi
    }
    _gmt_live_bridge() {
      while true; do
        GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}"
        local ec=$?
        [[ "${ec}" -eq 0 ]] && break
        echo "${TAG} WARN: GMT live bridge exited ec=${ec}; restart in 0.3s" >&2
        sleep 0.3
      done
    }
    (
      if [[ "${LIVE_TEE}" == "1" ]]; then
        "${TAP}" 2>"${LOG_DIR}/tap.log" \
          | tee "${LIVE_SESSION}" \
          | _tee_fan >( _gmt_live_bridge ) \
          | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" --host "${HOST}" --port "${PORT}"
      else
        "${TAP}" 2>"${LOG_DIR}/tap.log" \
          | _tee_fan >( _gmt_live_bridge ) \
          | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" --host "${HOST}" --port "${PORT}"
      fi
    ) &
    LIVE_FAN_PID=$!
  fi

  if [[ "${DRIVE_MODE}" == "playhead" || "${DRIVE_MODE}" == "controlled" || "${DRIVE_MODE}" == "wait" ]]; then
    echo "${TAG} Ctrl+C to stop (yellow=listen green=CONNECTED cyan=DISCONNECTED red=err)"
    wait "${INJ_PID}" || true
    kill "${INJ_TEE_PID}" 2>/dev/null || true
    rm -f "${INJ_FIFO}"
    if [[ -n "${LIVE_FAN_PID}" ]]; then
      kill "${LIVE_FAN_PID}" 2>/dev/null || true
    fi
    echo "${TAG} inject stopped; logs: ${LOG_DIR}/ (apps=${RUN_APPS})"
    exit 0
  fi
  # continuous: wait for inject to finish
  wait "${INJ_PID}" || true
  kill "${INJ_TEE_PID}" 2>/dev/null || true
  rm -f "${INJ_FIFO}"
  if [[ -n "${LIVE_FAN_PID}" ]]; then
    kill "${LIVE_FAN_PID}" 2>/dev/null || true
  fi
  echo "${TAG} inject finished; logs: ${LOG_DIR}/ (apps=${RUN_APPS})"
  exit 0
fi

# Optional CARLA / dry-run bridge — enabled by frame_ingest_config.hpp (or debug GF_*).
CARLA_BRIDGE_PID=""
if [[ "${GF_START_CARLA_BRIDGE:-0}" == "1" ]]; then
  export GF_CARLA_FRAME_PATH="${GF_CARLA_FRAME_PATH:-/tmp/gf_front.rgb}"
  export GF_CARLA_CMD_PATH="${GF_CARLA_CMD_PATH:-/tmp/gf_carla_cmd.json}"
  export GF_FRAME_SOURCE="${GF_FRAME_SOURCE:-carla_file}"
  export CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
  export CARLA_PORT="${CARLA_PORT:-2000}"
  BRIDGE_PY="${PROJECT_DIR}/tools/carla_bridge/carla_bridge.py"
  PY="${GF_CARLA_PYTHON:-python3}"
  echo "${TAG} carla_bridge → frame=${GF_CARLA_FRAME_PATH} cmd=${GF_CARLA_CMD_PATH} source=${GF_FRAME_SOURCE} dry=${GF_CARLA_BRIDGE_DRY_RUN:-0}"
  : >"${LOG_DIR}/carla_bridge.log"
  if [[ -f "${BRIDGE_PY}" ]]; then
    "${PY}" "${BRIDGE_PY}" >"${LOG_DIR}/carla_bridge.log" 2>&1 &
    CARLA_BRIDGE_PID=$!
    sleep 0.4
    if ! kill -0 "${CARLA_BRIDGE_PID}" 2>/dev/null; then
      echo "${TAG} WARN: carla_bridge exited early; see ${LOG_DIR}/carla_bridge.log (SIL continues)" >&2
      CARLA_BRIDGE_PID=""
    else
      host_info "carla_bridge ok pid=${CARLA_BRIDGE_PID} dry=${GF_CARLA_BRIDGE_DRY_RUN:-0}"
    fi
  else
    echo "${TAG} WARN: missing ${BRIDGE_PY}" >&2
  fi
fi

# SOA apps already under EM. Do not direct-spawn gateway/fcm/planning.
host_info "apps under EM — logs: ${GF_EM_LOG_DIR}/ and ${LOG_DIR}/em_daemon.stdout"
echo "${TAG} [EM] apps managed by EM pid=${EM_PID} (no direct spawn)"

if [[ "${LIVE_ON}" != "1" ]]; then
  echo "${TAG} live_tap off — EM only. logs: ${LOG_DIR}/ ${GF_EM_LOG_DIR}/"
  echo "${TAG} (enable live_tap in gf-config → Verify/compile → re-run for Foxglove)"
  wait "${EM_PID}" || true
  exit 0
fi

export GF_OBS_LIVE_SERVICES="${LIVE_SVCS}"
LIVE_PORT="${GF_LIVE_PORT:-8766}"
HINT_IP="127.0.0.1"
if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
  HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  HINT_IP="${HINT_IP:-<this-host-LAN-IP>}"
fi
echo "${TAG} live services=${GF_OBS_LIVE_SERVICES}"
echo "${TAG} listen Foxglove ws://${HINT_IP}:${PORT}  GMT-Live ws://${HINT_IP}:${LIVE_PORT}"
echo "${TAG} Ctrl+C to stop (yellow=listen green=CONNECTED cyan=DISCONNECTED red=err)"
if [[ -t 2 ]]; then
  export GF_STATUS_COLOR=1
fi

LIVE_SESSION="${GF_LIVE_SESSION:-$(gf_obs_dir)/session_live.jsonl}"
LIVE_TEE="${GF_LIVE_TEE:-1}"
if [[ "${LIVE_TEE}" == "1" ]]; then
  mkdir -p "$(dirname "${LIVE_SESSION}")"
  : > "${LIVE_SESSION}"
fi

_FOX_BEV=()
if [[ "${GF_SYNTH_BEV:-1}" != "0" ]]; then
  _FOX_BEV=(--synth-bev)
  echo "${TAG} Foxglove --synth-bev (EgoMotion/Trajectory → BEV)"
fi

# GNU tee: if GMT Live process-sub dies, do NOT collapse the pipe to Foxglove.
_tee_fan() {
  if tee --help 2>&1 | grep -q -- '--output-error'; then
    tee --output-error=warn "$@"
  else
    tee "$@"
  fi
}

# GMT GUI open/close must not kill this side-channel. Restart live bridge on crash;
# exit 0 after clean stdin EOF (tap ended).
_gmt_live_bridge() {
  while true; do
    GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}"
    local ec=$?
    if [[ "${ec}" -eq 0 ]]; then
      break
    fi
    echo "${TAG} WARN: GMT live bridge exited ec=${ec}; restart in 0.3s (Foxglove kept)" >&2
    sleep 0.3
  done
}

_live_fan() {
  if [[ "${LIVE_TEE}" == "1" ]]; then
    "${TAP}" 2>"${LOG_DIR}/tap.log" \
      | tee "${LIVE_SESSION}" \
      | _tee_fan >( _gmt_live_bridge ) \
      | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" --host "${HOST}" --port "${PORT}"
  else
    "${TAP}" 2>"${LOG_DIR}/tap.log" \
      | _tee_fan >( _gmt_live_bridge ) \
      | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" --host "${HOST}" --port "${PORT}"
  fi
}

# Obs fan is side-channel: must NOT be the foreground waiter.
# Otherwise tap/bridge exit (or pipe break) would tear down the whole SIL via EXIT trap.
_live_fan &
LIVE_FAN_PID=$!
echo "${TAG} live fan pid=${LIVE_FAN_PID} (apps keep running if fan dies; Ctrl+C stops all)"
echo "${TAG} GMT GUI can open/close anytime; this SIL keeps running"
wait "${EM_PID}" || true
