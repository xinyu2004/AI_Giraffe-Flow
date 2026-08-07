#!/usr/bin/env bash
# Wave C protocol smoke (no CARLA UE): dry-run bridge + carla_file + cmd path.
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
export GF_CARLA_BRIDGE_DRY_RUN=1
export GF_FRAME_SOURCE=carla_file
export GF_CARLA_FRAME_PATH="${GF_CARLA_FRAME_PATH:-/tmp/gf_front_smoke.rgb}"
export GF_CARLA_CMD_PATH="${GF_CARLA_CMD_PATH:-/tmp/gf_carla_cmd_smoke.json}"
export GF_CARLA_DEMO_LC=1
export GF_CARLA_DEMO_LC_SEC=3
export GF_PERCEPTION_BACKEND=stub
SECONDS_WIN="${GF_SIL_SECONDS:-12}"

rm -f "${GF_CARLA_FRAME_PATH}" "${GF_CARLA_FRAME_PATH%.rgb}.json" "${GF_CARLA_CMD_PATH}" 2>/dev/null || true

echo "${TAG} smoke_carla_sil: dry-run bridge ~${SECONDS_WIN}s"
set +e
timeout --signal=INT --kill-after=5 "${SECONDS_WIN}" bash "${SCRIPT_DIR}/run_sil.sh"
rc=$?
set -e
if [[ "${rc}" -ne 0 && "${rc}" -ne 124 && "${rc}" -ne 137 ]]; then
  echo "${TAG} ERROR: run_sil exit ${rc}" >&2
  exit "${rc}"
fi

LOG_DIR="${BUILD}/runtime/logs"
if ! grep -qE 'fseq=|dyn=[1-9]' "${LOG_DIR}/fcm.log"; then
  echo "${TAG} ERROR: no frame-driven out (carla_file) in fcm.log" >&2
  tail -40 "${LOG_DIR}/fcm.log" >&2 || true
  exit 1
fi
if [[ ! -f "${GF_CARLA_CMD_PATH}" ]]; then
  echo "${TAG} ERROR: gateway did not write ${GF_CARLA_CMD_PATH}" >&2
  tail -40 "${LOG_DIR}/gateway.log" >&2 || true
  exit 1
fi
if ! grep -q 'lane_change' "${GF_CARLA_CMD_PATH}"; then
  echo "${TAG} ERROR: bad cmd json" >&2
  cat "${GF_CARLA_CMD_PATH}" >&2 || true
  exit 1
fi
if ! grep -q 'Trajectory' "${LOG_DIR}/planning.log" \
  && ! grep -q 'Trajectory' "${LOG_DIR}/gateway.log"; then
  echo "${TAG} ERROR: no Trajectory" >&2
  exit 1
fi
if [[ -f "${LOG_DIR}/carla_bridge.log" ]] && ! grep -q 'dry-run' "${LOG_DIR}/carla_bridge.log"; then
  echo "${TAG} WARN: carla_bridge.log missing dry-run marker" >&2
fi
echo "${TAG} smoke_carla_sil OK (dry-run; real CARLA = GF_CARLA_BRIDGE_DRY_RUN=0)"
exit 0
