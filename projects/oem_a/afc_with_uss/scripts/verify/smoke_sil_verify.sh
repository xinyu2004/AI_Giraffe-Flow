#!/usr/bin/env bash
# Verify: compile_sil → finite main-chain trajectory assertions.
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_verify.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

if [[ "${GF_SKIP_COMPILE:-0}" != "1" ]]; then
  bash "${PROJECT_SCRIPTS}/compile_sil.sh"
fi

bash "${SCRIPT_DIR}/run_sil_verify.sh"
