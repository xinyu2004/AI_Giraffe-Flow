#!/usr/bin/env bash
# SIL: run host iceoryx dual-process demo (RouDi + uss_feed + demo_pipeline).
# Prerequisites: compile_sil.sh (or equivalent host build with iceoryx).
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

export GF_BUILD_DIR="${BUILD_SIL}"
echo "${TAG} iceoryx dual-process demo (SIL) ..."
bash "${ROOT}/scripts/run_iox_demo.sh"

echo "${TAG} run_sil OK"
