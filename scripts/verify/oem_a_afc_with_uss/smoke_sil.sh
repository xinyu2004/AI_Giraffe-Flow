#!/usr/bin/env bash
# Verify (not product path): compile_sil → dual-process iceoryx demo.
# Product path: projects/.../scripts/compile_sil.sh + run_sil.sh
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/smoke_sil.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

bash "${PROJECT_SCRIPTS}/compile_sil.sh"
export GF_BUILD_DIR="${GF_BUILD_DIR:-${BUILD_SIL}}"
echo "${TAG} verify dual-process demo (SIL) ..."
bash "${ROOT}/scripts/run_iox_demo.sh"
echo "${TAG} smoke_sil (verify) OK"
