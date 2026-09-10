#!/usr/bin/env bash
# X-3 verify: PHM fault injection — miss then recover, e2e still OK.
# Self-contained smoke (does NOT call product run_sil).
#
# Usage (after compile_sil):
#   bash projects/adc/scripts/verify/smoke_sil_phm_fault.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-500}"
export GF_PHM_FAULT_TARGET="${GF_PHM_FAULT_TARGET:-planning}"
export GF_MP_TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-8}"
export GF_MP_TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-60}"

echo "${TAG} PHM fault inject GF_PHM_FAULT_MS=${GF_PHM_FAULT_MS} target=${GF_PHM_FAULT_TARGET}"
bash "${SCRIPT_DIR}/run_mainchain_verify.sh"

echo "${TAG} smoke_sil_phm_fault OK (planning miss → recover → Trajectory e2e)"
