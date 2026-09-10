#!/usr/bin/env bash
# HIL entry: compile_hil always syncs build-hil/runtime/; copy that tree to the board.
# GF_FORCE_COMPILE=1 (here only) wipes runtime + cmake sentinel, then compile_hil.
# compile_hil itself does not read GF_FORCE_COMPILE.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

export GF_BUILD_DIR="${BUILD_HIL}"

if [[ "${GF_FORCE_COMPILE:-0}" == "1" ]]; then
  gf_sil_force_runtime_if_requested
  bash "${SCRIPT_DIR}/compile_hil.sh"
fi

RT="$(gf_sil_runtime_dir)"
echo "${TAG} HIL: bash ${SCRIPT_DIR}/compile_hil.sh"
echo "${TAG}   then copy ${RT}/ to the board → ./bin/giraffe_launch"
echo "${TAG}   wipe + rebuild: GF_FORCE_COMPILE=1 bash ${SCRIPT_DIR}/run_hil.sh"
echo "${TAG}   day-to-day host: bash ${SCRIPT_DIR}/run_sil.sh"
