#!/usr/bin/env bash
# SIL run (product path): RouDi + wiring main chain; optional Foxglove from observability.json.
#
# Config truth = gf-config → compose → generated/observability.json + build binaries.
#   live_tap effective → gf_iox_obs_tap | GMT bridge foxglove --ws
#   else → main chain only until Ctrl+C
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#
# Env:
#   GF_BUILD_DIR     default <repo>/build
#   GF_WS_HOST       default 0.0.0.0
#   GF_WS_PORT       default 8765
#   GF_SKIP_COMPILE=1  skip compile_sil (assume already built)
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

if [[ "${GF_SKIP_COMPILE:-0}" != "1" ]]; then
  bash "${SCRIPT_DIR}/compile_sil.sh"
fi

OBS_JSON="${PROJECT_DIR}/generated/observability.json"
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

ROUDI="${BUILD}/iox-roudi"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
USS="${BUILD}/apps/sensing/uss/gf_sensing_uss"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"
TAP="${BUILD}/apps/tools/iox_obs_tap/gf_iox_obs_tap"

NEED_BINS=("${ROUDI}" "${GW}" "${FCM}" "${USS}" "${PLAN}")
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
    exit 1
  fi
done

if [[ ! -f "${GF_PLATFORM_DIR}/exec.yaml" && ! -f "${GF_PLATFORM_DIR}/platform/exec.yaml" ]]; then
  echo "Missing exec.yaml under ${GF_PLATFORM_DIR} (or …/platform/)" >&2
  exit 1
fi

LOG_DIR="${BUILD}/iox_sil_logs"
mkdir -p "${LOG_DIR}"

cleanup() {
  set +e
  for pid in "${TAP_PID:-}" "${GW_PID:-}" "${PLAN_PID:-}" "${FCM_PID:-}" "${USS_PID:-}" "${ROUDI_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null
  done
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "${TAG} run_sil: platform=${GF_PLATFORM_DIR} live=${LIVE_ON}"
echo "${TAG} RouDi ..."
"${ROUDI}" >"${LOG_DIR}/roudi.log" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "${TAG} RouDi failed; see ${LOG_DIR}/roudi.log" >&2
  cat "${LOG_DIR}/roudi.log" >&2 || true
  exit 1
fi

echo "${TAG} fcm / uss / planning / gateway (Ctrl+C to stop) ..."
"${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
FCM_PID=$!
"${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
USS_PID=$!
GF_PHM_FAULT_MS=0 "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
PLAN_PID=$!
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
HINT_IP="127.0.0.1"
if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
  HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  HINT_IP="${HINT_IP:-<this-host-LAN-IP>}"
fi
echo "${TAG} GF_OBS_LIVE_SERVICES=${GF_OBS_LIVE_SERVICES}"
echo "${TAG} Studio → Foxglove WebSocket → ws://${HINT_IP}:${PORT}  (随时可连，不必先开 Studio)"
echo "${TAG} (GMT bridge is NOT ROS foxglove_bridge; main chain stays iceoryx)"
echo "${TAG} Ctrl+C 结束"

"${TAP}" 2>"${LOG_DIR}/tap.log" | GMT bridge foxglove --ws --stdin --host "${HOST}" --port "${PORT}"
