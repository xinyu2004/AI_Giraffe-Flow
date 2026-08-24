#!/usr/bin/env bash
# Verify-only: finite main-chain (RouDi + gateway/fcm/planning). Not product run_sil.
#
# Caller may export GF_PHM_FAULT_MS / GF_PHM_FAULT_TARGET before invoking (smoke only).
# Default: no fault inject.
#
# Usage:
#   bash projects/afc/scripts/verify/run_mainchain_verify.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-15}"
TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-60}"
export GF_PLATFORM_DIR="${GF_PLATFORM_DIR:-${PROJECT_DIR}/platform}"
# Smoke opt-in only; unset → 0 (no inject).
FAULT_MS="${GF_PHM_FAULT_MS:-0}"
FAULT_TARGET="${GF_PHM_FAULT_TARGET:-planning}"

export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
_COLLECTOR_DEFAULT="${BUILD}/runtime/collector/events.ndjson"
mkdir -p "${BUILD}/runtime/logs" "${BUILD}/runtime/collector" "${BUILD}/runtime/per"
export GF_COLLECTOR_STORE="${GF_COLLECTOR_STORE:-${_COLLECTOR_DEFAULT}}"
export GF_PER_DIR="${GF_PER_DIR:-${BUILD}/runtime/per}"

ROUDI="${BUILD}/iox-roudi"
IOX_TOML="${PROJECT_DIR}/generated/iox_roudi.toml"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"

IOX_ON=0
if [[ -f "${PROJECT_DIR}/req.yaml" ]] && grep -Eq '^[[:space:]]*-[[:space:]]*iceoryx[[:space:]]*$' "${PROJECT_DIR}/req.yaml"; then
  IOX_ON=1
fi

NEED_BINS=("${GW}" "${FCM}" "${PLAN}")
if [[ "${IOX_ON}" == "1" ]]; then
  NEED_BINS=("${ROUDI}" "${NEED_BINS[@]}")
fi
for bin in "${NEED_BINS[@]}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "${TAG} missing executable: ${bin}" >&2
    echo "${TAG} build: bash projects/afc/scripts/compile_sil.sh" >&2
    exit 1
  fi
done

if [[ "${IOX_ON}" != "1" ]]; then
  echo "${TAG} RouDi required (req.bindings has no iceoryx)" >&2
  exit 1
fi
if [[ ! -f "${IOX_TOML}" ]]; then
  echo "${TAG} missing ${IOX_TOML} — compose first" >&2
  exit 1
fi
if [[ ! -f "${GF_PLATFORM_DIR}/exec.yaml" && ! -f "${GF_PLATFORM_DIR}/platform/exec.yaml" ]]; then
  echo "${TAG} missing exec.yaml under ${GF_PLATFORM_DIR}" >&2
  exit 1
fi

LOG_DIR="${BUILD}/runtime/logs"
mkdir -p "${LOG_DIR}"

cleanup() {
  local code=$?
  set +e
  for pid in "${GW_PID:-}" "${PLAN_PID:-}" "${FCM_PID:-}" "${ROUDI_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null
  done
  wait 2>/dev/null
  exit "${code}"
}
trap cleanup EXIT INT TERM

fault_env() {
  local proc="$1"
  if [[ "${FAULT_MS}" == "0" ]]; then
    echo 0
  elif [[ "${FAULT_TARGET}" == "${proc}" ]]; then
    echo "${FAULT_MS}"
  else
    echo 0
  fi
}

echo "${TAG} run_mainchain_verify platform=${GF_PLATFORM_DIR} traj=${TRAJ_COUNT} fault_ms=${FAULT_MS} target=${FAULT_TARGET}"
echo "${TAG} RouDi → ${IOX_TOML}"
"${ROUDI}" -c "${IOX_TOML}" >"${LOG_DIR}/roudi.log" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "${TAG} RouDi failed; see ${LOG_DIR}/roudi.log" >&2
  cat "${LOG_DIR}/roudi.log" >&2 || true
  exit 1
fi

echo "${TAG} start fcm / planning / gateway"
GF_PHM_FAULT_MS="$(fault_env fcm)" "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
FCM_PID=$!
GF_PHM_FAULT_MS="$(fault_env planning)" "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
PLAN_PID=$!
sleep 0.5
GF_PHM_FAULT_MS="$(fault_env gateway)" "${GW}" "${TRAJ_COUNT}" >"${LOG_DIR}/gateway.log" 2>&1 &
GW_PID=$!

echo "${TAG} waiting for gateway (timeout ${TIMEOUT_SEC}s) ..."
SECONDS=0
while kill -0 "${GW_PID}" 2>/dev/null; do
  if (( SECONDS >= TIMEOUT_SEC )); then
    echo "${TAG} TIMEOUT" >&2
    for f in gateway planning fcm; do
      echo "--- ${f}.log ---" >&2
      cat "${LOG_DIR}/${f}.log" >&2 || true
    done
    exit 1
  fi
  sleep 0.2
done

wait "${GW_PID}"
GW_RC=$?
if [[ "${GW_RC}" -ne 0 ]]; then
  echo "${TAG} gateway exited ${GW_RC}" >&2
  cat "${LOG_DIR}/gateway.log" >&2 || true
  exit "${GW_RC}"
fi

assert_log() {
  local file="$1" pat="$2" label="$3"
  if ! grep -qE "${pat}" "${file}"; then
    echo "${TAG} FAIL ${label}: /${pat}/ in ${file}" >&2
    cat "${file}" >&2 || true
    exit 1
  fi
}

assert_log "${LOG_DIR}/gateway.log" "Offer→Running process=adapter.vehicle_can_gateway" "gateway offer"
assert_log "${LOG_DIR}/planning.log" "Offer→Running process=planning.driving" "planning offer"
assert_log "${LOG_DIR}/fcm.log" "Offer→Running process=perception.fcm" "fcm offer"
assert_log "${LOG_DIR}/gateway.log" "Trajectory#" "trajectory e2e"

if [[ "${FAULT_MS}" != "0" ]]; then
  case "${FAULT_TARGET}" in
    planning) FAULT_LOG="${LOG_DIR}/planning.log" ;;
    gateway) FAULT_LOG="${LOG_DIR}/gateway.log" ;;
    fcm) FAULT_LOG="${LOG_DIR}/fcm.log" ;;
    *)
      echo "${TAG} unknown GF_PHM_FAULT_TARGET=${FAULT_TARGET}" >&2
      exit 1
      ;;
  esac
  assert_log "${FAULT_LOG}" "FAULT inject|AliveMissed|DeadlineMissed" "fault (${FAULT_TARGET})"
  if [[ "${FAULT_TARGET}" == "planning" ]]; then
    assert_log "${FAULT_LOG}" "recovered|fault window ended|phm recovered" "recover"
  fi
fi

echo "${TAG} run_mainchain_verify OK — Trajectory×${TRAJ_COUNT}"
echo "${TAG} logs: ${LOG_DIR}/"
