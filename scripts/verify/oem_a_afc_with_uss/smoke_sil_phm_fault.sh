#!/usr/bin/env bash
# X-3 verify: PHM fault injection — miss then recover, e2e still OK.
#
# Usage (after compile_sil):
#   bash scripts/verify/oem_a_afc_with_uss/smoke_sil_phm_fault.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-500}"
export GF_MP_TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-8}"
export GF_MP_TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-60}"

echo "${TAG} PHM fault inject GF_PHM_FAULT_MS=${GF_PHM_FAULT_MS} (planning)"
bash "${SCRIPT_DIR}/run_sil_multiproc.sh"

# Fault is injected on planning (gateway keeps GF_PHM_FAULT_MS=0 for e2e).
LOG="${GF_BUILD_DIR:-${BUILD_SIL}}/iox_multiproc_logs/planning.log"
GW_LOG="${GF_BUILD_DIR:-${BUILD_SIL}}/iox_multiproc_logs/gateway.log"
if [[ ! -f "${LOG}" ]]; then
  echo "${TAG} missing planning log: ${LOG}" >&2
  exit 1
fi

if ! grep -qE 'FAULT inject|AliveMissed|DeadlineMissed' "${LOG}"; then
  echo "${TAG} FAIL: expected fault/AliveMissed/DeadlineMissed in ${LOG}" >&2
  cat "${LOG}" >&2 || true
  exit 1
fi
if ! grep -qE 'recovered|fault window ended|phm recovered' "${LOG}"; then
  echo "${TAG} FAIL: expected recover in ${LOG}" >&2
  cat "${LOG}" >&2 || true
  exit 1
fi
if [[ ! -f "${GW_LOG}" ]] || ! grep -qE 'Trajectory#[0-9]+' "${GW_LOG}"; then
  echo "${TAG} FAIL: expected Trajectory e2e in ${GW_LOG}" >&2
  cat "${GW_LOG}" >&2 || true
  exit 1
fi

echo "${TAG} smoke_sil_phm_fault OK (planning miss → recover → Trajectory e2e)"
