#!/usr/bin/env bash
# Verify: compile_sil → finite multiproc trajectory assertions.
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/smoke_sil_multiproc.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

bash "${PROJECT_SCRIPTS}/compile_sil.sh"
bash "${SCRIPT_DIR}/run_sil_multiproc.sh"
