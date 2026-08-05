#!/usr/bin/env bash
# Verify: finite multiproc trajectory + exec/phm assertions (not product path).
# Product run: projects/oem_a/afc_with_uss/scripts/run_sil.sh
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/run_sil_multiproc.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

ROOT="${ROOT}"
BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-15}"
TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-60}"
export GF_PLATFORM_DIR="${GF_PLATFORM_DIR:-${PROJECT_DIR}/platform}"
export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-400}"

export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
_COLLECTOR_DEFAULT="${BUILD}/runtime/collector/events.ndjson"
mkdir -p "${BUILD}/runtime/logs" "${BUILD}/runtime/collector" "${BUILD}/runtime/per"
export GF_COLLECTOR_STORE="${GF_COLLECTOR_STORE:-${_COLLECTOR_DEFAULT}}"
export GF_PER_DIR="${GF_PER_DIR:-${BUILD}/runtime/per}"

ROUDI="${BUILD}/iox-roudi"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
USS="${BUILD}/apps/sensing/uss/gf_sensing_uss"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"

for bin in "${ROUDI}" "${GW}" "${FCM}" "${USS}" "${PLAN}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "Missing executable: ${bin}" >&2
    echo "Build first: bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh" >&2
    exit 1
  fi
done

if [[ ! -f "${GF_PLATFORM_DIR}/exec.yaml" && ! -f "${GF_PLATFORM_DIR}/platform/exec.yaml" ]]; then
  echo "Missing exec.yaml under ${GF_PLATFORM_DIR} (or …/platform/)" >&2
  exit 1
fi

LOG_DIR="${BUILD}/runtime/logs"
mkdir -p "${LOG_DIR}"

cleanup() {
  local code=$?
  set +e
  for pid in "${GW_PID:-}" "${PLAN_PID:-}" "${FCM_PID:-}" "${USS_PID:-}" "${ROUDI_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null
  done
  wait 2>/dev/null
  exit "${code}"
}
trap cleanup EXIT INT TERM

echo "[run_sil_multiproc] platform=${GF_PLATFORM_DIR} fault_ms=${GF_PHM_FAULT_MS} target=${GF_PHM_FAULT_TARGET:-planning}"
echo "[run_sil_multiproc] RouDi ..."
"${ROUDI}" >"${LOG_DIR}/roudi.log" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "[run_sil_multiproc] RouDi failed; see ${LOG_DIR}/roudi.log" >&2
  cat "${LOG_DIR}/roudi.log" >&2 || true
  exit 1
fi

# Which process gets GF_PHM_FAULT_MS (others get 0). Default: planning (SG-02).
# uss/fcm/gateway use on_failure: notify_sm (SG-03).
FAULT_TARGET="${GF_PHM_FAULT_TARGET:-planning}"
fault_env() {
  local proc="$1"
  if [[ "${FAULT_TARGET}" == "${proc}" ]]; then
    echo "${GF_PHM_FAULT_MS}"
  else
    echo "0"
  fi
}

echo "[run_sil_multiproc] fcm / uss / planning ..."
GF_PHM_FAULT_MS="$(fault_env fcm)" "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
FCM_PID=$!
GF_PHM_FAULT_MS="$(fault_env uss)" "${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
USS_PID=$!
GF_PHM_FAULT_MS="$(fault_env planning)" "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
PLAN_PID=$!
sleep 0.5

echo "[run_sil_multiproc] gateway (expect ${TRAJ_COUNT} Trajectory) ..."
GF_PHM_FAULT_MS="$(fault_env gateway)" "${GW}" "${TRAJ_COUNT}" >"${LOG_DIR}/gateway.log" 2>&1 &
GW_PID=$!

echo "[run_sil_multiproc] waiting (timeout ${TIMEOUT_SEC}s) ..."
SECONDS=0
while kill -0 "${GW_PID}" 2>/dev/null; do
  if (( SECONDS >= TIMEOUT_SEC )); then
    echo "[run_sil_multiproc] TIMEOUT" >&2
    for f in gateway planning fcm uss; do
      echo "--- ${f}.log ---" >&2
      cat "${LOG_DIR}/${f}.log" >&2 || true
    done
    tail -40 "${LOG_DIR}/roudi.log" >&2 || true
    exit 1
  fi
  sleep 0.2
done

wait "${GW_PID}"
GW_RC=$?
if [[ "${GW_RC}" -ne 0 ]]; then
  echo "[run_sil_multiproc] gateway exited ${GW_RC}" >&2
  cat "${LOG_DIR}/gateway.log" >&2 || true
  exit "${GW_RC}"
fi

assert_log() {
  local file="$1" pat="$2" label="$3"
  if ! grep -qE "${pat}" "${file}"; then
    echo "[run_sil_multiproc] FAIL ${label}: missing /${pat}/ in ${file}" >&2
    cat "${file}" >&2 || true
    exit 1
  fi
}

assert_log "${LOG_DIR}/gateway.log" "Offer→Running process=adapter.vehicle_can_gateway" "X-1 gateway"
assert_log "${LOG_DIR}/planning.log" "Offer→Running process=planning.driving" "X-1 planning"
assert_log "${LOG_DIR}/fcm.log" "Offer→Running process=perception.fcm" "X-1 fcm"
assert_log "${LOG_DIR}/uss.log" "Offer→Running process=sensing.uss" "X-1 uss"
assert_log "${LOG_DIR}/gateway.log" "phm entity=gateway_alive" "X-2 gateway phm"
assert_log "${LOG_DIR}/planning.log" "phm entity=planning_alive" "X-2 planning phm"

if [[ "${GF_PHM_FAULT_MS}" != "0" ]]; then
  case "${FAULT_TARGET}" in
    planning) FAULT_LOG="${LOG_DIR}/planning.log" ;;
    gateway) FAULT_LOG="${LOG_DIR}/gateway.log" ;;
    uss) FAULT_LOG="${LOG_DIR}/uss.log" ;;
    fcm) FAULT_LOG="${LOG_DIR}/fcm.log" ;;
    *)
      echo "[run_sil_multiproc] unknown GF_PHM_FAULT_TARGET=${FAULT_TARGET}" >&2
      exit 1
      ;;
  esac
  assert_log "${FAULT_LOG}" "FAULT inject|AliveMissed|DeadlineMissed" "X-3 fault (${FAULT_TARGET})"
  # planning uses restart/soft recover; notify_sm targets may pause without "recovered"
  if [[ "${FAULT_TARGET}" == "planning" ]]; then
    assert_log "${FAULT_LOG}" "recovered|fault window ended" "X-3 recover"
  fi
fi

echo "[run_sil_multiproc] OK — Trajectory×${TRAJ_COUNT} + exec/phm checks"
echo "logs: ${LOG_DIR}/"
tail -20 "${LOG_DIR}/gateway.log" || true
exit 0
