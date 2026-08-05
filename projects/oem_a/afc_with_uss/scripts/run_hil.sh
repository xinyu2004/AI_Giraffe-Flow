#!/usr/bin/env bash
# HIL: run on board (P0 stub — deploy + remote smoke not wired yet).
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/run_hil.sh
#
# Later: scp/ssh deploy of build-hil artifacts + board RouDi smoke.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

if [[ ! -d "${BUILD_HIL}" ]]; then
  echo "${TAG} ERROR: ${BUILD_HIL} missing. Run compile_hil.sh first." >&2
  exit 1
fi

echo "${TAG} run_hil: STUB only — board deploy/run is not automated (P2.5-H / P3)."
echo "${TAG}   build dir : ${BUILD_HIL}"
echo "${TAG}   use SIL for day-to-day: bash ${SCRIPT_DIR}/run_sil.sh"
echo "${TAG}   later    : scp ${BUILD_HIL} + deps to board → RouDi → same apps as SIL"
echo "${TAG}   optional : bash ${ROOT}/scripts/verify/oem_a_afc_with_uss/deploy_hil.sh  (also stub)"
exit 0
