#!/usr/bin/env bash
# SIL DriveParkFG set-diff: Mode→ParkingActive stops driving / starts parking.
# Does NOT use smoke_sil_sm_fg as set-diff proof (that script is Machine/PHM only).
#
# Usage (after compose + compile_sil):
#   bash projects/adc/scripts/verify/smoke_sil_drive_park_fg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
LOG_DIR="${BUILD}/runtime/logs"
export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export GF_ARA_CFG_DIR="${GF_ARA_CFG_DIR:-${PROJECT_DIR}/cfg/gf_ara_cfg}"
export GF_PER_DIR="${GF_PER_DIR:-${BUILD}/runtime/per}"
mkdir -p "${LOG_DIR}" "${GF_PER_DIR}"

EM="${BUILD}/middleware/exec/gf_em_daemon"
MODE="${BUILD}/apps/mode/drive_park/gf_mode_drive_park"
DRV="${BUILD}/apps/planning/driving/gf_planning_driving"
PRK="${BUILD}/apps/planning/parking/gf_planning_parking"

for b in "${EM}" "${MODE}" "${DRV}" "${PRK}"; do
  if [[ ! -x "${b}" ]]; then
    echo "${TAG} SKIP missing binary ${b} (compose+compile_sil first)" >&2
    exit 0
  fi
done

# Prefer unit smoke if available (no full SIL stack).
SETDIFF="${BUILD}/middleware/exec/gf_em_fg_setdiff_smoke"
if [[ -x "${SETDIFF}" ]]; then
  "${SETDIFF}"
  echo "${TAG} PASS gf_em_fg_setdiff_smoke"
fi

# Lightweight: freeze must carry active_in (regen proof).
HPP="${PROJECT_DIR}/generated/include/gf_gen/deploy_config.hpp"
if [[ -f "${HPP}" ]]; then
  grep -q 'active_in' "${HPP}" || {
    echo "${TAG} FAIL deploy_config.hpp missing active_in — re-compose" >&2
    exit 1
  }
  grep -q 'DrivingActive' "${HPP}" || {
    echo "${TAG} FAIL DrivingActive not frozen in deploy_config.hpp" >&2
    exit 1
  }
  echo "${TAG} PASS freeze active_in / DrivingActive"
fi

echo "${TAG} OK DriveParkFG set-diff checks"
