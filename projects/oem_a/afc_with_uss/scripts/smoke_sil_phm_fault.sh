#!/usr/bin/env bash
# X-3: PHM fault injection on gateway — miss then recover, then e2e still OK.
#
# Usage (after compile_sil):
#   bash projects/oem_a/afc_with_uss/scripts/smoke_sil_phm_fault.sh
#
# Env:
#   GF_PHM_FAULT_MS   default 500 (skip Alive)
#   GF_MP_TRAJ_COUNT  default 8 (enough time to miss+recover+close loop)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-500}"
export GF_MP_TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-8}"
export GF_MP_TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-60}"

echo "${TAG} PHM fault inject GF_PHM_FAULT_MS=${GF_PHM_FAULT_MS}"
bash "${SCRIPT_DIR}/run_sil_multiproc.sh"

LOG="${GF_BUILD_DIR:-${BUILD_SIL}}/iox_multiproc_logs/gateway.log"
if [[ ! -f "${LOG}" ]]; then
  echo "${TAG} missing gateway log: ${LOG}" >&2
  exit 1
fi

if ! grep -qE 'phm (AliveMissed|DeadlineMissed)' "${LOG}"; then
  echo "${TAG} FAIL: expected AliveMissed/DeadlineMissed in ${LOG}" >&2
  cat "${LOG}" >&2 || true
  exit 1
fi
if ! grep -q 'phm recovered' "${LOG}"; then
  echo "${TAG} FAIL: expected phm recovered in ${LOG}" >&2
  cat "${LOG}" >&2 || true
  exit 1
fi
if ! grep -q 'Offer→Running process=adapter.vehicle_can_gateway' "${LOG}"; then
  echo "${TAG} FAIL: expected exec Offer→Running in ${LOG}" >&2
  exit 1
fi

echo "${TAG} smoke_sil_phm_fault OK (miss → recover → Trajectory e2e)"
