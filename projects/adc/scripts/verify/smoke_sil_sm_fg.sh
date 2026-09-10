#!/usr/bin/env bash
# SIL-SM-01: PHM miss → sm health_fault (notify_sm) + Updating/pause + Collector.
# AFC has no USS — use perception.fcm (phm.yaml on_failure: notify_sm).
#
# Note: sticky Updating pauses FCM Alive; do not combine with main-chain Trajectory wait.
# Trajectory isolation remains smoke_sil_phm_fault / smoke_sil (planning path).
#
# Usage (after compile_sil + compose artifacts):
#   bash projects/adc/scripts/verify/smoke_sil_sm_fg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
LOG_DIR="${BUILD}/runtime/logs"
STORE="${BUILD}/runtime/collector/events.ndjson"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
ROUDI="${BUILD}/iox-roudi"
IOX_TOML="${PROJECT_DIR}/generated/iox_roudi.toml"
PART_LOG="${LOG_DIR}/fcm_sm_fg.log"

export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export GF_ARA_CFG_DIR="${GF_ARA_CFG_DIR:-${PROJECT_DIR}/cfg/gf_ara_cfg}"
export GF_COLLECTOR_STORE="${GF_COLLECTOR_STORE:-${STORE}}"
export GF_PER_DIR="${GF_PER_DIR:-${BUILD}/runtime/per}"

mkdir -p "${LOG_DIR}" "$(dirname "${GF_COLLECTOR_STORE}")" "${GF_PER_DIR}"
: >"${GF_COLLECTOR_STORE}"

assert_log() {
  local file="$1" pat="$2" label="$3"
  if ! grep -qE "${pat}" "${file}"; then
    echo "${TAG} FAIL ${label}: /${pat}/ in ${file}" >&2
    cat "${file}" >&2 || true
    exit 1
  fi
}

for bin in "${ROUDI}" "${FCM}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "${TAG} missing: ${bin} (compile_sil first)" >&2
    exit 1
  fi
done
if [[ ! -f "${IOX_TOML}" ]]; then
  echo "${TAG} missing ${IOX_TOML}" >&2
  exit 1
fi

# Do not inherit GF_PHM_FAULT_MS=0 from a prior mainchain smoke in the same shell.
FAULT_MS="${GF_SIL_SM_FAULT_MS:-400}"
if [[ "${FAULT_MS}" == "0" ]]; then
  FAULT_MS=400
fi

echo "${TAG} SIL-SM-01 fcm notify_sm + Updating + collector store (fault_ms=${FAULT_MS})"
cleanup() {
  set +e
  [[ -n "${FCM_PID:-}" ]] && kill "${FCM_PID}" 2>/dev/null
  [[ -n "${ROUDI_PID:-}" ]] && kill "${ROUDI_PID}" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT

"${ROUDI}" -c "${IOX_TOML}" >"${LOG_DIR}/roudi_sm_fg.log" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "${TAG} RouDi failed" >&2
  cat "${LOG_DIR}/roudi_sm_fg.log" >&2 || true
  exit 1
fi

GF_PHM_FAULT_MS="${FAULT_MS}" \
GF_SM_ENTER_UPDATING_ON_FAULT=1 \
  "${FCM}" >"${PART_LOG}" 2>&1 &
FCM_PID=$!

SECONDS=0
while (( SECONDS < 20 )); do
  if grep -qE "sm: health_fault" "${PART_LOG}" 2>/dev/null &&
     grep -qE "paused \\(sm Updating\\)|Running→Updating" "${PART_LOG}" 2>/dev/null; then
    break
  fi
  if ! kill -0 "${FCM_PID}" 2>/dev/null; then
    echo "${TAG} fcm exited early" >&2
    cat "${PART_LOG}" >&2 || true
    exit 1
  fi
  sleep 0.2
done

assert_log "${PART_LOG}" "FAULT inject|AliveMissed|DeadlineMissed" "phm fault"
assert_log "${PART_LOG}" "sm: health_fault" "sm health_fault"
assert_log "${PART_LOG}" "collector: event" "collector log line"
assert_log "${PART_LOG}" "paused \\(sm Updating\\)|Running→Updating" "sm Updating / pause"

if [[ ! -s "${GF_COLLECTOR_STORE}" ]]; then
  echo "${TAG} FAIL empty collector store ${GF_COLLECTOR_STORE}" >&2
  exit 1
fi
if ! grep -qE "AliveMissed|DeadlineMissed|phm" "${GF_COLLECTOR_STORE}"; then
  echo "${TAG} FAIL store missing phm miss event" >&2
  cat "${GF_COLLECTOR_STORE}" >&2 || true
  exit 1
fi

echo "${TAG} smoke_sil_sm_fg OK (notify_sm → health_fault → Updating/pause + collector)"
