#!/usr/bin/env bash
# HIL deploy stub (verify / future board path — not product four-script set).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"
gf_project_env
echo "${TAG} deploy_hil: P0 stub — set GF_HIL_HOST / GF_HIL_DIR when board path is ready."
echo "${TAG}   build-hil: ${BUILD_HIL}"
exit 0
