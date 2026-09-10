#!/usr/bin/env bash
# Camera-protocol smoke without CARLA UE (developer only — not a SKU freeze).
# Uses C++ gf_carla_io (cosim listen; needs giraffe_client for real UE truth).
#   bash projects/adc/scripts/smoke_carla_sil.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_common.sh"

gf_project_env
BUILD="${BUILD_SIL}"
for bin in \
  "${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway" \
  "${BUILD}/apps/perception/fcm/gf_perception_fcm" \
  "${BUILD}/apps/planning/driving/gf_planning_driving" \
  "${BUILD}/apps/carla_io/gf_carla_io" \
  "${BUILD}/apps/frame_ingest/gf_frame_ingest"; do
  if [[ ! -x "${bin}" ]]; then
    echo "${TAG} smoke_carla_sil: binaries missing → compile_sil"
    bash "${SCRIPT_DIR}/compile_sil.sh"
    break
  fi
done

export GF_SKIP_COMPILE="${GF_SKIP_COMPILE:-1}"
export GF_FRAME_SOURCE=carla
export GF_EGO_SOURCE=carla
export GF_PIXEL_FORMAT="${GF_PIXEL_FORMAT:-nv12}"
export GF_PERCEPTION_BACKEND=stub
SECONDS_WIN="${GF_SIL_SECONDS:-12}"

echo "${TAG} smoke_carla_sil: gf_carla_io cosim listen ~${SECONDS_WIN}s (dev only)"
set +e
timeout --signal=INT --kill-after=5 "${SECONDS_WIN}" bash "${SCRIPT_DIR}/run_sil.sh"
rc=$?
set -e
if [[ "${rc}" -ne 0 && "${rc}" -ne 124 && "${rc}" -ne 137 ]]; then
  echo "${TAG} ERROR: run_sil exit ${rc}" >&2
  exit "${rc}"
fi
echo "${TAG} smoke_carla_sil OK (dev; verify FCM/Trajectory via DLT or GMT)"
exit 0
