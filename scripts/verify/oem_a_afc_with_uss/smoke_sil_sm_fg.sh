#!/usr/bin/env bash
# SG-03 SIL: PHM miss on uss (on_failure: notify_sm) → SM health_fault + shared collector store.
# Gateway keeps fault_ms=0 so Trajectory e2e still holds.
#
# Usage (after compile_sil):
#   bash scripts/verify/oem_a_afc_with_uss/smoke_sil_sm_fg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
LOG_DIR="${BUILD}/iox_multiproc_logs"
STORE="${BUILD}/iox_multiproc_logs/collector_shared.ndjson"
mkdir -p "${LOG_DIR}"
rm -f "${STORE}"

export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-500}"
export GF_PHM_FAULT_TARGET=uss
export GF_MP_TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-8}"
export GF_MP_TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-60}"
export GF_SM_ENTER_UPDATING_ON_FAULT="${GF_SM_ENTER_UPDATING_ON_FAULT:-1}"
export GF_COLLECTOR_STORE="${STORE}"

echo "${TAG} SM FG + PHM notify_sm target=uss fault_ms=${GF_PHM_FAULT_MS} store=${STORE}"
bash "${SCRIPT_DIR}/run_sil_multiproc.sh"

USS_LOG="${LOG_DIR}/uss.log"
GW_LOG="${LOG_DIR}/gateway.log"

if [[ ! -f "${USS_LOG}" ]]; then
  echo "${TAG} missing uss log: ${USS_LOG}" >&2
  exit 1
fi
if ! grep -qE 'FAULT inject|AliveMissed|DeadlineMissed' "${USS_LOG}"; then
  echo "${TAG} FAIL: expected PHM miss in ${USS_LOG}" >&2
  cat "${USS_LOG}" >&2 || true
  exit 1
fi
if ! grep -qE 'sm: health_fault' "${USS_LOG}"; then
  echo "${TAG} FAIL: expected sm: health_fault in ${USS_LOG}" >&2
  cat "${USS_LOG}" >&2 || true
  exit 1
fi
if ! grep -qE 'collector: event source=phm' "${USS_LOG}"; then
  echo "${TAG} FAIL: expected collector phm event in ${USS_LOG}" >&2
  cat "${USS_LOG}" >&2 || true
  exit 1
fi
if [[ "${GF_SM_ENTER_UPDATING_ON_FAULT}" == "1" ]]; then
  if ! grep -qE 'sm: transition .*→Updating|phm paused' "${USS_LOG}"; then
    echo "${TAG} FAIL: expected SM Updating / phm paused in ${USS_LOG}" >&2
    cat "${USS_LOG}" >&2 || true
    exit 1
  fi
fi
if [[ ! -f "${GW_LOG}" ]] || ! grep -qE 'Trajectory#[0-9]+' "${GW_LOG}"; then
  echo "${TAG} FAIL: expected Trajectory e2e in ${GW_LOG}" >&2
  cat "${GW_LOG}" >&2 || true
  exit 1
fi
if [[ ! -s "${STORE}" ]] || ! grep -qE 'AliveMissed|DeadlineMissed' "${STORE}"; then
  echo "${TAG} FAIL: expected shared collector store event in ${STORE}" >&2
  cat "${STORE}" >&2 || true
  exit 1
fi

echo "${TAG} smoke_sil_sm_fg OK (uss miss → SM health_fault → collector store → Trajectory e2e)"
