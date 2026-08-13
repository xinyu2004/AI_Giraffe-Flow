#!/usr/bin/env bash
# Tip-protocol smoke without CARLA UE (developer only — not a SKU freeze).
# Uses carla_bridge CLI/env dry-run; product path requires real CARLA.
#   bash projects/oem_a/afc_no_uss/scripts/smoke_carla_sil.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_common.sh"

gf_project_env
BUILD="${BUILD_SIL}"
for bin in \
  "${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway" \
  "${BUILD}/apps/perception/fcm/gf_perception_fcm" \
  "${BUILD}/apps/planning/driving/gf_planning_driving"; do
  if [[ ! -x "${bin}" ]]; then
    echo "${TAG} smoke_carla_sil: binaries missing → compile_sil"
    bash "${SCRIPT_DIR}/compile_sil.sh"
    break
  fi
done

export GF_SKIP_COMPILE="${GF_SKIP_COMPILE:-1}"
export GF_START_CARLA_BRIDGE=1
# Debug-only: not frozen in frame_ingest (product path = real CARLA).
export GF_CARLA_BRIDGE_DRY_RUN=1
export GF_FRAME_SOURCE=carla_file
export GF_CARLA_FRAME_PATH="${GF_CARLA_FRAME_PATH:-/tmp/gf_front_smoke.yuv}"
export GF_CARLA_CMD_PATH="${GF_CARLA_CMD_PATH:-/tmp/gf_carla_cmd_smoke.json}"
export GF_PIXEL_FORMAT="${GF_PIXEL_FORMAT:-nv12}"
export GF_PERCEPTION_BACKEND=stub
SECONDS_WIN="${GF_SIL_SECONDS:-12}"

rm -f "${GF_CARLA_FRAME_PATH}" \
  "${GF_CARLA_FRAME_PATH%.yuv}.stream.json" \
  "${GF_CARLA_FRAME_PATH%.yuv}.meta.json" \
  "${GF_CARLA_CMD_PATH}" 2>/dev/null || true

echo "${TAG} smoke_carla_sil: tip dry-run bridge ~${SECONDS_WIN}s (dev only)"
set +e
timeout --signal=INT --kill-after=5 "${SECONDS_WIN}" bash "${SCRIPT_DIR}/run_sil.sh"
rc=$?
set -e
if [[ "${rc}" -ne 0 && "${rc}" -ne 124 && "${rc}" -ne 137 ]]; then
  echo "${TAG} ERROR: run_sil exit ${rc}" >&2
  exit "${rc}"
fi

LOG_DIR="${BUILD}/runtime/logs"
FCM_LOG="${LOG_DIR}/em/perception_fcm.log"
[[ -f "${FCM_LOG}" ]] || FCM_LOG="${LOG_DIR}/fcm.log"
if ! grep -qE 'fseq=|dyn=[1-9]|stream negotiate' "${FCM_LOG}" 2>/dev/null; then
  echo "${TAG} ERROR: no frame-driven out in ${FCM_LOG}" >&2
  tail -40 "${FCM_LOG}" >&2 || true
  exit 1
fi
if [[ ! -f "${GF_CARLA_CMD_PATH}" ]]; then
  echo "${TAG} ERROR: gateway did not write ${GF_CARLA_CMD_PATH}" >&2
  exit 1
fi
if ! grep -q 'Trajectory' "${LOG_DIR}/em/planning_driving.log" 2>/dev/null \
  && ! grep -q 'Trajectory' "${LOG_DIR}/planning.log" 2>/dev/null \
  && ! grep -q 'Trajectory' "${LOG_DIR}/em/adapter_vehicle_can_gateway.log" 2>/dev/null; then
  echo "${TAG} ERROR: no Trajectory" >&2
  exit 1
fi
echo "${TAG} smoke_carla_sil OK (dev tip dry-run; product = real CARLA + carla_scenarios/)"
exit 0
