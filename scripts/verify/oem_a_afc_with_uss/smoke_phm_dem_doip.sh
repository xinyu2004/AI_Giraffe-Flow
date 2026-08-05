#!/usr/bin/env bash
# PHM fault → Collector NDJSON + PER DTC → DoIP UDS 0x19 (no fake seed).
#
# Usage (after compile_sil):
#   bash scripts/verify/oem_a_afc_with_uss/smoke_phm_dem_doip.sh
#
# Interactive GMT:
#   bash projects/oem_a/afc_with_uss/scripts/run_sil.sh   # DoIP on → default PHM fault on uss
#   GMT gui --project projects/oem_a/afc_with_uss
#   → OTA/UDS Connect → wait ~1s → DEM Read DTCs; Collector local file for ring
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
LOG_DIR="${BUILD}/runtime/logs"
STORE="${BUILD}/runtime/collector/events.ndjson"
PER_DIR="${BUILD}/runtime/per"
DOIP_LOG="${LOG_DIR}/doip_phm_dem.log"
DOIP="${BUILD}/gf_doip_ota_server"
if [[ ! -x "${DOIP}" ]]; then
  DOIP="${BUILD}/middleware/diag/gf_doip_ota_server"
fi
mkdir -p "${LOG_DIR}" "${BUILD}/runtime/collector" "${PER_DIR}"
rm -f "${STORE}"
# Fresh PER so 0x19 only sees this run's PHM DTCs
find "${PER_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
: >"${DOIP_LOG}"

export GF_COLLECTOR_STORE="${STORE}"
export GF_PER_DIR="${PER_DIR}"
export GF_PLATFORM_DIR="${GF_PLATFORM_DIR:-${PROJECT_DIR}/platform}"
export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-500}"
export GF_PHM_FAULT_TARGET="${GF_PHM_FAULT_TARGET:-uss}"
export GF_MP_TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-6}"
export GF_MP_TIMEOUT_SEC="${GF_MP_TIMEOUT_SEC:-45}"
export GF_SM_ENTER_UPDATING_ON_FAULT="${GF_SM_ENTER_UPDATING_ON_FAULT:-0}"
export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export GF_DOIP_PORT="${GF_DOIP_PORT:-13400}"

if [[ ! -x "${DOIP}" ]]; then
  echo "${TAG} missing ${DOIP} — run compile_sil first" >&2
  exit 1
fi

echo "${TAG} phm_dem_doip: PER=${PER_DIR} store=${STORE} PHM fault→DEM"

"${DOIP}" >>"${DOIP_LOG}" 2>&1 &
DOIP_PID=$!
sleep 0.4
if ! kill -0 "${DOIP_PID}" 2>/dev/null; then
  echo "${TAG} DoIP failed; see ${DOIP_LOG}" >&2
  cat "${DOIP_LOG}" >&2 || true
  exit 1
fi

cleanup() {
  local code=$?
  set +e
  kill "${DOIP_PID}" 2>/dev/null || true
  wait "${DOIP_PID}" 2>/dev/null || true
  exit "${code}"
}
trap cleanup EXIT INT TERM

bash "${SCRIPT_DIR}/run_sil_verify.sh"

USS_LOG="${LOG_DIR}/uss.log"
if [[ ! -f "${USS_LOG}" ]]; then
  echo "${TAG} missing ${USS_LOG}" >&2
  exit 1
fi
# Fault window skips Alive → AliveMissed and/or DeadlineMissed (both in dtc_map).
if ! grep -qE 'AliveMissed|DeadlineMissed' "${USS_LOG}"; then
  echo "${TAG} FAIL: expected AliveMissed/DeadlineMissed in ${USS_LOG}" >&2
  grep -E 'phm|Alive|FAULT|collector|Deadline' "${USS_LOG}" | head -40 >&2 || true
  exit 1
fi

if [[ ! -s "${STORE}" ]] || ! grep -qE 'AliveMissed|DeadlineMissed' "${STORE}"; then
  echo "${TAG} FAIL: expected PHM event in collector store ${STORE}" >&2
  cat "${STORE}" 2>/dev/null | head -20 >&2 || true
  exit 1
fi

sleep 0.3

python3 - <<PY
import sys
sys.path.insert(0, "${ROOT}/tools/gmt/src")
from gf_gmt.doip_client import DoipClient

c = DoipClient()
c.connect("127.0.0.1", int("${GF_DOIP_PORT}"))
c.routing_activation()
rows = c.read_dtc_list(status_mask=0xFF)
got = {int(r["code"]) for r in rows}
print("DEM DTCs:", sorted(hex(x) for x in got))
# collector.yaml: AliveMissed=0xC01234, DeadlineMissed=0xC01235
expect_any = {0xC01234, 0xC01235}
if not (got & expect_any):
    raise SystemExit(
        f"FAIL DEM got {[hex(x) for x in got]}, want one of "
        f"{[hex(x) for x in expect_any]} "
        "(PHM→PER→ReloadDtcsFromPer; check GF_PER_DIR shared with DoIP)"
    )
print("UDS DEM OK (PHM DTC from shared PER)")
c.close()
PY

echo ""
echo "${TAG} smoke_phm_dem_doip OK"
echo "  SIL logs : ${LOG_DIR}/*.log"
echo "  NDJSON   : ${STORE}           → GMT Collector local file"
echo "  PER      : ${PER_DIR}         → DoIP 0x19 ReloadDtcsFromPer"
echo "  DoIP was : 127.0.0.1:${GF_DOIP_PORT} (stopped on exit)"
echo ""
echo "Interactive:"
echo "  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh"
echo "  GMT gui --project projects/oem_a/afc_with_uss"
