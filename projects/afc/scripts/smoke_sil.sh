#!/usr/bin/env bash
# Minimal SIL smoke for afc (no USS / no ORT / no CARLA).
#   bash projects/afc/scripts/smoke_sil.sh
#   GF_SKIP_COMPILE=0 bash …/smoke_sil.sh   # force rebuild inside run_sil
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_common.sh"

gf_project_env
BUILD="${BUILD_SIL}"
RUNTIME="${BUILD}/runtime"
GW="${RUNTIME}/bin/gf_vehicle_can_gateway"
FCM="${RUNTIME}/bin/gf_perception_fcm"
PLAN="${RUNTIME}/bin/gf_planning_driving"

if [[ ! -x "${GW}" || ! -x "${FCM}" || ! -x "${PLAN}" ]]; then
  echo "${TAG} smoke_sil: staged binaries missing → compile_sil first"
  bash "${SCRIPT_DIR}/compile_sil.sh"
  GW="${RUNTIME}/bin/gf_vehicle_can_gateway"
  FCM="${RUNTIME}/bin/gf_perception_fcm"
  PLAN="${RUNTIME}/bin/gf_planning_driving"
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

for bin in "${GW}" "${FCM}" "${PLAN}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "${TAG} ERROR: missing executable ${bin}" >&2
    exit 1
  fi
done

echo "${TAG} smoke_sil OK (timed run_sil; verify Trajectory/modules via DLT or GMT Live)"
exit 0
