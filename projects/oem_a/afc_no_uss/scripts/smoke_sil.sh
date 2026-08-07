#!/usr/bin/env bash
# Minimal SIL smoke for afc_no_uss (no USS / no ORT / no CARLA).
#   bash projects/oem_a/afc_no_uss/scripts/smoke_sil.sh
#   GF_SKIP_COMPILE=0 bash …/smoke_sil.sh   # force rebuild inside run_sil
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_common.sh"

gf_project_env
BUILD="${BUILD_SIL}"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"

if [[ ! -x "${GW}" || ! -x "${FCM}" || ! -x "${PLAN}" ]]; then
  echo "${TAG} smoke_sil: binaries missing → compile_sil first"
  bash "${SCRIPT_DIR}/compile_sil.sh"
fi

# Avoid re-running full cmake inside the timed window (timeout would interrupt build).
export GF_SKIP_COMPILE="${GF_SKIP_COMPILE:-1}"
SECONDS_WIN="${GF_SIL_SECONDS:-12}"

echo "${TAG} smoke_sil: run_sil ~${SECONDS_WIN}s (GF_SKIP_COMPILE=${GF_SKIP_COMPILE})"
set +e
# INT first so run_sil trap cleans RouDi/apps; KILL if iceoryx apps ignore and wait 60s.
timeout --signal=INT --kill-after=5 "${SECONDS_WIN}" bash "${SCRIPT_DIR}/run_sil.sh"
rc=$?
set -e
# 124 = timeout (expected); 137 = kill-after SIGKILL; 0 = gateway exited early
if [[ "${rc}" -ne 0 && "${rc}" -ne 124 && "${rc}" -ne 137 ]]; then
  echo "${TAG} ERROR: run_sil exit ${rc}" >&2
  exit "${rc}"
fi

LOG_DIR="${BUILD}/runtime/logs"
if [[ ! -d "${LOG_DIR}" ]]; then
  echo "${TAG} ERROR: missing ${LOG_DIR}" >&2
  exit 1
fi
echo "${TAG} logs: ${LOG_DIR}"
for f in fcm.log planning.log gateway.log; do
  if [[ ! -f "${LOG_DIR}/${f}" ]]; then
    echo "${TAG} ERROR: missing ${f}" >&2
    exit 1
  fi
done
if ! grep -q 'Trajectory' "${LOG_DIR}/planning.log" \
  && ! grep -q 'Trajectory' "${LOG_DIR}/gateway.log"; then
  echo "${TAG} ERROR: no Trajectory in planning.log / gateway.log" >&2
  tail -50 "${LOG_DIR}/planning.log" >&2 || true
  tail -30 "${LOG_DIR}/gateway.log" >&2 || true
  exit 1
fi
echo "${TAG} smoke_sil OK"
exit 0
