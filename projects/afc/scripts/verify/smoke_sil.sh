#!/usr/bin/env bash
# Verify (not product path): compile_sil → AFC main-chain (gateway / FCM / planning).
# iceoryx binding smoke is middleware: testcases/run_iox_pubsub.sh (ctest gf_iox_*).
#
# Usage:
#   bash projects/afc/scripts/verify/smoke_sil.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

bash "${PROJECT_SCRIPTS}/compile_sil.sh"
export GF_BUILD_DIR="${GF_BUILD_DIR:-${BUILD_SIL}}"
echo "${TAG} verify AFC main-chain ..."
bash "${SCRIPT_DIR}/run_mainchain_verify.sh"
echo "${TAG} smoke_sil (verify) OK"
