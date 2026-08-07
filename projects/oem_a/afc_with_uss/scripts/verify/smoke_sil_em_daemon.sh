#!/usr/bin/env bash
# Trust SIL-EM-02: OS EM daemon fork/exec + PHM restart exit → relaunch.
#
# Usage (after compile_sil):
#   bash projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_em_daemon.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
export GF_PLATFORM_DIR="${GF_PLATFORM_DIR:-${PROJECT_DIR}/platform}"
export GF_BUILD_DIR="${BUILD}"
export GF_EM_LAUNCH="${GF_EM_LAUNCH:-${GF_PLATFORM_DIR}/em_launch.yaml}"
export GF_EM_LOG_DIR="${GF_EM_LOG_DIR:-${BUILD}/em_daemon_logs}"
export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-400}"
export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

ROUDI="${BUILD}/iox-roudi"
EM="${BUILD}/middleware/exec/gf_em_daemon"

for bin in "${ROUDI}" "${EM}" \
  "${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway" \
  "${BUILD}/apps/perception/fcm/gf_perception_fcm" \
  "${BUILD}/apps/sensing/uss/gf_sensing_uss" \
  "${BUILD}/apps/planning/driving/gf_planning_driving"
do
  if [[ ! -x "${bin}" ]]; then
    echo "${TAG} missing: ${bin}" >&2
    echo "${TAG} build: bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh" >&2
    exit 1
  fi
done

mkdir -p "${GF_EM_LOG_DIR}"
cleanup() {
  local code=$?
  set +e
  [[ -n "${EM_PID:-}" ]] && kill "${EM_PID}" 2>/dev/null
  [[ -n "${ROUDI_PID:-}" ]] && kill "${ROUDI_PID}" 2>/dev/null
  wait 2>/dev/null
  exit "${code}"
}
trap cleanup EXIT INT TERM

IOX_TOML="${PROJECT_DIR}/generated/iox_roudi.toml"
if [[ ! -f "${IOX_TOML}" ]]; then
  echo "${TAG} ERROR: missing ${IOX_TOML} (compose with iceoryx)" >&2
  exit 1
fi
# CI module smoke (≠ product acceptance). Product launch uses gateway forever ["0"];
# rewrite a temp launch with args ["15"] so this smoke can terminate.
export GF_IOX_TOML="${IOX_TOML}"
export GF_EM_EXEC="${GF_EM_EXEC:-${PROJECT_DIR}/generated/exec.yaml}"
_SRC_LAUNCH="${PROJECT_DIR}/generated/em_launch.yaml"
if [[ ! -f "${_SRC_LAUNCH}" ]]; then
  _SRC_LAUNCH="${GF_PLATFORM_DIR}/em_launch.yaml"
fi
SMOKE_LAUNCH="${GF_EM_LOG_DIR}/em_launch.smoke.yaml"
python3 - "${_SRC_LAUNCH}" "${SMOKE_LAUNCH}" <<'PY'
import sys, yaml
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
doc = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
for p in doc.get("processes") or []:
    if isinstance(p, dict) and p.get("name") == "adapter.vehicle_can_gateway":
        p["args"] = ["15"]
dst.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
PY
export GF_EM_LAUNCH="${SMOKE_LAUNCH}"
echo "${TAG} gf_em_daemon first (HOST); launch=${GF_EM_LAUNCH} (fault_ms=${GF_PHM_FAULT_MS}) ..."
if ! grep -q 'host.iox_roudi' "${GF_EM_LAUNCH}" 2>/dev/null; then
  echo "${TAG} RouDi (legacy pre-start; launch has no host.iox_roudi) ..."
  "${ROUDI}" -c "${IOX_TOML}" >"${GF_EM_LOG_DIR}/roudi.log" 2>&1 &
  ROUDI_PID=$!
  sleep 1
fi
GF_EM_DEADLINE_MS="${GF_EM_DEADLINE_MS:-90000}" \
  "${EM}" \
  --platform "${GF_PLATFORM_DIR}" \
  --launch "${GF_EM_LAUNCH}" \
  --build-dir "${BUILD}" \
  --log-dir "${GF_EM_LOG_DIR}" \
  --deadline-ms "${GF_EM_DEADLINE_MS:-90000}" \
  >"${GF_EM_LOG_DIR}/em_daemon.stdout" 2>&1 &
EM_PID=$!

# Wait until gateway finishes (managed child) or timeout
SECONDS=0
while kill -0 "${EM_PID}" 2>/dev/null; do
  if (( SECONDS >= ${GF_EM_DEADLINE_MS:-90000} / 1000 + 5 )); then
    echo "${TAG} TIMEOUT waiting for em_daemon" >&2
    cat "${GF_EM_LOG_DIR}/em_daemon.stdout" >&2 || true
    exit 1
  fi
  sleep 0.5
done
wait "${EM_PID}" || true

assert_log() {
  local file="$1" pat="$2" label="$3"
  if ! grep -qE "${pat}" "${file}"; then
    echo "${TAG} FAIL ${label}: /${pat}/ in ${file}" >&2
    cat "${file}" >&2 || true
    exit 1
  fi
}

assert_log "${GF_EM_LOG_DIR}/em_daemon.stdout" "em_daemon: spawned name=planning.driving" "spawn planning"
assert_log "${GF_EM_LOG_DIR}/em_daemon.stdout" "em_daemon: relaunch name=planning.driving|restart#" "relaunch planning"
assert_log "${GF_EM_LOG_DIR}/planning_driving.log" "em os_restart_exit|AliveMissed|DeadlineMissed" "planning fault→os restart"
assert_log "${GF_EM_LOG_DIR}/adapter_vehicle_can_gateway.log" "Trajectory#" "gateway got traj"

echo "${TAG} smoke_sil_em_daemon OK"
echo "${TAG} logs: ${GF_EM_LOG_DIR}/"
