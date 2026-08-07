#!/usr/bin/env bash
# Wave B: synth frame tip → Perception_MESSAGE_Out (frame-driven stub).
#   bash projects/oem_a/afc_no_uss/scripts/smoke_frame_sil.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_common.sh"

gf_project_env
BUILD="${BUILD_SIL}"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"

if [[ ! -x "${FCM}" || ! -x "${PLAN}" || ! -x "${GW}" ]]; then
  echo "${TAG} smoke_frame_sil: binaries missing → compile_sil first"
  bash "${SCRIPT_DIR}/compile_sil.sh"
fi

export GF_SKIP_COMPILE="${GF_SKIP_COMPILE:-1}"
export GF_FRAME_SOURCE="${GF_FRAME_SOURCE:-synth}"
export GF_PERCEPTION_BACKEND="${GF_PERCEPTION_BACKEND:-stub}"
export GF_FRAME_TIMEOUT_MS="${GF_FRAME_TIMEOUT_MS:-300}"
SECONDS_WIN="${GF_SIL_SECONDS:-12}"

echo "${TAG} smoke_frame_sil: source=${GF_FRAME_SOURCE} backend=${GF_PERCEPTION_BACKEND} ~${SECONDS_WIN}s"
set +e
timeout --signal=INT --kill-after=5 "${SECONDS_WIN}" bash "${SCRIPT_DIR}/run_sil.sh"
rc=$?
set -e
if [[ "${rc}" -ne 0 && "${rc}" -ne 124 && "${rc}" -ne 137 ]]; then
  echo "${TAG} ERROR: run_sil exit ${rc}" >&2
  exit "${rc}"
fi

LOG_DIR="${BUILD}/runtime/logs"
if [[ ! -f "${LOG_DIR}/fcm.log" ]]; then
  echo "${TAG} ERROR: missing fcm.log" >&2
  exit 1
fi
if ! grep -qE 'fseq=|dyn=[1-9]' "${LOG_DIR}/fcm.log"; then
  echo "${TAG} ERROR: no frame-driven out in fcm.log" >&2
  tail -60 "${LOG_DIR}/fcm.log" >&2 || true
  exit 1
fi
if ! grep -q 'Trajectory' "${LOG_DIR}/planning.log" \
  && ! grep -q 'Trajectory' "${LOG_DIR}/gateway.log"; then
  echo "${TAG} ERROR: no Trajectory downstream" >&2
  exit 1
fi
echo "${TAG} smoke_frame_sil OK"
exit 0
