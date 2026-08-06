#!/usr/bin/env bash
# Verify: finite main-chain trajectory + exec/phm assertions (not product path).
# Product run: projects/oem_a/afc_with_uss/scripts/run_sil.sh
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/verify/run_sil_verify.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

ROOT="${ROOT}"
BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-15}"
TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-60}"
export GF_PLATFORM_DIR="${GF_PLATFORM_DIR:-${PROJECT_DIR}/platform}"
export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-400}"

export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
_COLLECTOR_DEFAULT="${BUILD}/runtime/collector/events.ndjson"
mkdir -p "${BUILD}/runtime/logs" "${BUILD}/runtime/collector" "${BUILD}/runtime/per"
export GF_COLLECTOR_STORE="${GF_COLLECTOR_STORE:-${_COLLECTOR_DEFAULT}}"
export GF_PER_DIR="${GF_PER_DIR:-${BUILD}/runtime/per}"

ROUDI="${BUILD}/iox-roudi"
IOX_TOML="${PROJECT_DIR}/generated/iox_roudi.toml"
GW="${BUILD}/apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
FCM="${BUILD}/apps/perception/fcm/gf_perception_fcm"
USS="${BUILD}/apps/sensing/uss/gf_sensing_uss"
PLAN="${BUILD}/apps/planning/driving/gf_planning_driving"

IOX_ON=0
if [[ -f "${PROJECT_DIR}/req.yaml" ]] && grep -Eq '^[[:space:]]*-[[:space:]]*iceoryx[[:space:]]*$' "${PROJECT_DIR}/req.yaml"; then
  IOX_ON=1
fi

NEED_BINS=("${GW}" "${FCM}" "${USS}" "${PLAN}")
if [[ "${IOX_ON}" == "1" ]]; then
  NEED_BINS=("${ROUDI}" "${NEED_BINS[@]}")
fi
for bin in "${NEED_BINS[@]}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "Missing executable: ${bin}" >&2
    echo "Build first: bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh" >&2
    exit 1
  fi
done

if [[ "${IOX_ON}" == "1" && ! -f "${IOX_TOML}" ]]; then
  echo "Missing ${IOX_TOML} — run compose (bounds.iceoryx.mempools)" >&2
  exit 1
fi

if [[ ! -f "${GF_PLATFORM_DIR}/exec.yaml" && ! -f "${GF_PLATFORM_DIR}/platform/exec.yaml" ]]; then
  echo "Missing exec.yaml under ${GF_PLATFORM_DIR} (or …/platform/)" >&2
  exit 1
fi

LOG_DIR="${BUILD}/runtime/logs"
mkdir -p "${LOG_DIR}"

cleanup() {
  local code=$?
  set +e
  for pid in "${GW_PID:-}" "${PLAN_PID:-}" "${FCM_PID:-}" "${USS_PID:-}" "${ROUDI_PID:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null
  done
  wait 2>/dev/null
  exit "${code}"
}
trap cleanup EXIT INT TERM

echo "[run_sil_verify] platform=${GF_PLATFORM_DIR} fault_ms=${GF_PHM_FAULT_MS} target=${GF_PHM_FAULT_TARGET:-planning}"
ROUDI_PID=""
if [[ "${IOX_ON}" == "1" ]]; then
  echo "[run_sil_verify] RouDi (bounds → ${IOX_TOML}) ..."
  echo "[run_sil_verify] NOTE: change iceoryx.mgmt → compose + cmake reconfigure + rebuild iceoryx"
  "${ROUDI}" -c "${IOX_TOML}" >"${LOG_DIR}/roudi.log" 2>&1 &
  ROUDI_PID=$!
  sleep 1
  if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
    echo "[run_sil_verify] RouDi failed; see ${LOG_DIR}/roudi.log" >&2
    cat "${LOG_DIR}/roudi.log" >&2 || true
    exit 1
  fi
  # Best-effort: same as run_sil.sh — reports/iox_shm_report.json (+ mgmt snapshot for gf-config).
  python - "${LOG_DIR}/roudi.log" "${PROJECT_DIR}/reports/iox_shm_report.json" "${IOX_TOML}" \
    "${PROJECT_DIR}/generated/iox_mgmt.cmake" <<'PY' || true
import json, re, sys
from pathlib import Path
log, out, toml, cmake = (Path(sys.argv[i]) for i in range(1, 5))
text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
mgmt = None
payload = None
for m in re.finditer(
    r"(?:Trying to reserve|Acquired|Reserving)\s+(\d+)\s+bytes.*?\[([^\]]+)\]",
    text,
    re.I,
):
    n, name = int(m.group(1)), m.group(2).lower()
    if "mgmt" in name or name == "iceoryx_mgmt":
        mgmt = n
    elif "mgmt" not in name:
        payload = n if payload is None else max(payload, n)
# bounds.iceoryx.mgmt.* keys (same as gf-config / mem_budget)
cmake_to_bounds = {
    "IOX_MAX_PUBLISHERS": "max_publishers",
    "IOX_MAX_SUBSCRIBERS": "max_subscribers",
    "IOX_MAX_SUBSCRIBERS_PER_PUBLISHER": "max_subscribers_per_publisher",
    "IOX_MAX_PUBLISHER_HISTORY": "max_publisher_history",
    "IOX_MAX_CHUNKS_ALLOCATED_PER_PUBLISHER_SIMULTANEOUSLY": "max_chunks_allocated_per_publisher",
    "IOX_MAX_CHUNKS_HELD_PER_SUBSCRIBER_SIMULTANEOUSLY": "max_chunks_held_per_subscriber",
    "IOX_MAX_INTERFACE_NUMBER": "max_interface_number",
}
iox_mgmt = {}
if cmake.is_file():
    for m in re.finditer(
        r"set\s*\(\s*(IOX_MAX_[A-Z0-9_]+)\s+(\d+)\s*CACHE\s+STRING",
        cmake.read_text(encoding="utf-8", errors="replace"),
        re.I,
    ):
        bk = cmake_to_bounds.get(m.group(1).upper())
        if bk:
            iox_mgmt[bk] = int(m.group(2))
report = {
    "schema_version": "0.2",
    "source": "roudi.log",
    "toml": str(toml),
    "mgmt_bytes": mgmt,
    "payload_segment_bytes": payload,
    "mgmt": iox_mgmt,
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
PY
else
  echo "[run_sil_verify] RouDi skipped (req.bindings has no iceoryx)" >&2
  exit 1
fi

# Which process gets GF_PHM_FAULT_MS (others get 0). Default: planning (SG-02).
FAULT_TARGET="${GF_PHM_FAULT_TARGET:-planning}"
fault_env() {
  local proc="$1"
  if [[ "${FAULT_TARGET}" == "${proc}" ]]; then
    echo "${GF_PHM_FAULT_MS}"
  else
    echo "0"
  fi
}

echo "[run_sil_verify] fcm / uss / planning ..."
GF_PHM_FAULT_MS="$(fault_env fcm)" "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
FCM_PID=$!
GF_PHM_FAULT_MS="$(fault_env uss)" "${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
USS_PID=$!
GF_PHM_FAULT_MS="$(fault_env planning)" "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
PLAN_PID=$!
sleep 0.5

echo "[run_sil_verify] gateway (expect ${TRAJ_COUNT} Trajectory) ..."
GF_PHM_FAULT_MS="$(fault_env gateway)" "${GW}" "${TRAJ_COUNT}" >"${LOG_DIR}/gateway.log" 2>&1 &
GW_PID=$!

echo "[run_sil_verify] waiting (timeout ${TIMEOUT_SEC}s) ..."
SECONDS=0
while kill -0 "${GW_PID}" 2>/dev/null; do
  if (( SECONDS >= TIMEOUT_SEC )); then
    echo "[run_sil_verify] TIMEOUT" >&2
    for f in gateway planning fcm uss; do
      echo "--- ${f}.log ---" >&2
      cat "${LOG_DIR}/${f}.log" >&2 || true
    done
    tail -40 "${LOG_DIR}/roudi.log" >&2 || true
    exit 1
  fi
  sleep 0.2
done

wait "${GW_PID}"
GW_RC=$?
if [[ "${GW_RC}" -ne 0 ]]; then
  echo "[run_sil_verify] gateway exited ${GW_RC}" >&2
  cat "${LOG_DIR}/gateway.log" >&2 || true
  exit "${GW_RC}"
fi

assert_log() {
  local file="$1" pat="$2" label="$3"
  if ! grep -qE "${pat}" "${file}"; then
    echo "[run_sil_verify] FAIL ${label}: missing /${pat}/ in ${file}" >&2
    cat "${file}" >&2 || true
    exit 1
  fi
}

assert_log "${LOG_DIR}/gateway.log" "Offer→Running process=adapter.vehicle_can_gateway" "X-1 gateway"
assert_log "${LOG_DIR}/planning.log" "Offer→Running process=planning.driving" "X-1 planning"
assert_log "${LOG_DIR}/fcm.log" "Offer→Running process=perception.fcm" "X-1 fcm"
assert_log "${LOG_DIR}/uss.log" "Offer→Running process=sensing.uss" "X-1 uss"
assert_log "${LOG_DIR}/gateway.log" "phm entity=gateway_alive" "X-2 gateway phm"
assert_log "${LOG_DIR}/planning.log" "phm entity=planning_alive" "X-2 planning phm"

if [[ "${GF_PHM_FAULT_MS}" != "0" ]]; then
  case "${FAULT_TARGET}" in
    planning) FAULT_LOG="${LOG_DIR}/planning.log" ;;
    gateway) FAULT_LOG="${LOG_DIR}/gateway.log" ;;
    uss) FAULT_LOG="${LOG_DIR}/uss.log" ;;
    fcm) FAULT_LOG="${LOG_DIR}/fcm.log" ;;
    *)
      echo "[run_sil_verify] unknown GF_PHM_FAULT_TARGET=${FAULT_TARGET}" >&2
      exit 1
      ;;
  esac
  assert_log "${FAULT_LOG}" "FAULT inject|AliveMissed|DeadlineMissed" "X-3 fault (${FAULT_TARGET})"
  if [[ "${FAULT_TARGET}" == "planning" ]]; then
    assert_log "${FAULT_LOG}" "recovered|fault window ended" "X-3 recover"
  fi
fi

echo "[run_sil_verify] OK — Trajectory×${TRAJ_COUNT} + exec/phm checks"
echo "logs: ${LOG_DIR}/"
tail -20 "${LOG_DIR}/gateway.log" || true
exit 0
