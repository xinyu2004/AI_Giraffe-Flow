#!/usr/bin/env bash
# P2.5 live: multiproc SIL + gf_iox_obs_tap | GMT bridge foxglove --ws --stdin
#
# Usage (repo root or any cwd):
#   bash projects/oem_a/afc_with_uss/scripts/run_sil_live_foxglove.sh
#
# Then Foxglove Studio → Open connection → Foxglove WebSocket → ws://127.0.0.1:8765
# Topics: /gf/EgoMotion , /gf/Trajectory
#
# Env:
#   GF_BUILD_DIR   default <repo>/build
#   GF_WS_HOST     default 0.0.0.0  (use 127.0.0.1 for local-only)
#   GF_WS_PORT     default 8765
#   GF_SKIP_COMPILE=1  skip compile_sil
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

ROUDI="${BUILD}/iox-roudi"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
USS="${BUILD}/apps/sensing/uss/gf_sensing_uss"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"
TAP="${BUILD}/apps/tools/iox_obs_tap/gf_iox_obs_tap"

for bin in "${ROUDI}" "${GW}" "${FCM}" "${USS}" "${PLAN}" "${TAP}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "Missing executable: ${bin}" >&2
    echo "Build first: bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh" >&2
    exit 1
  fi
done

LOG_DIR="${BUILD}/iox_live_logs"
mkdir -p "${LOG_DIR}"

cleanup() {
  set +e
  for pid in "${TAP_PID:-}" "${GW_PID:-}" "${PLAN_PID:-}" "${FCM_PID:-}" "${USS_PID:-}" "${ROUDI_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null
  done
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "${TAG} live Foxglove: platform=${GF_PLATFORM_DIR} bind=${HOST}:${PORT}"
echo "${TAG} RouDi ..."
"${ROUDI}" >"${LOG_DIR}/roudi.log" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "${TAG} RouDi failed; see ${LOG_DIR}/roudi.log" >&2
  cat "${LOG_DIR}/roudi.log" >&2 || true
  exit 1
fi

echo "${TAG} fcm / uss / planning / gateway (run until Ctrl+C) ..."
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

# Hint a reachable URL for remote Studio (LAN IP if bound to all interfaces)
HINT_IP="127.0.0.1"
if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
  HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  HINT_IP="${HINT_IP:-<this-host-LAN-IP>}"
fi
echo "${TAG} Studio → Foxglove WebSocket → ws://${HINT_IP}:${PORT}"
echo "${TAG} (bind ${HOST}:${PORT}; GMT bridge is NOT ROS foxglove_bridge; main chain stays iceoryx)"

# live allowlist from compose output
OBS_JSON="${PROJECT_DIR}/generated/observability.json"
if [[ -f "${OBS_JSON}" ]]; then
  export GF_OBS_LIVE_SERVICES
  GF_OBS_LIVE_SERVICES="$(python - <<PY
import json
from pathlib import Path
d=json.loads(Path("${OBS_JSON}").read_text())
live=d.get("live_tap") or {}
svcs=live.get("services") or []
print(",".join(svcs))
PY
)"
  echo "${TAG} GF_OBS_LIVE_SERVICES=${GF_OBS_LIVE_SERVICES}"
else
  export GF_OBS_LIVE_SERVICES="${GF_OBS_LIVE_SERVICES:-EgoMotion,Trajectory}"
  echo "${TAG} WARN: no observability.json; using ${GF_OBS_LIVE_SERVICES}" >&2
fi

# stderr from tap stays visible; NDJSON on stdout → bridge
"${TAP}" 2>"${LOG_DIR}/tap.log" | GMT bridge foxglove --ws --stdin --host "${HOST}" --port "${PORT}"
