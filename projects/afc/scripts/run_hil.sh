#!/usr/bin/env bash
# HIL entry hint for afc — day-to-day still SIL; board uses giraffe_launch.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

echo "${TAG} HIL: cross-build then copy runtime/ to the board"
echo "${TAG}   bash ${SCRIPT_DIR}/compile_hil.sh"
echo "${TAG}   # optional: GF_STAGE_HIL=1 bash ${SCRIPT_DIR}/compile_hil.sh"
echo "${TAG}   # on target: ./bin/giraffe_launch"
echo "${TAG}   day-to-day host: bash ${SCRIPT_DIR}/run_sil.sh"
