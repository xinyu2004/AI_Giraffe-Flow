#!/usr/bin/env bash
# Seed Collector events + DEM-lite DTCs + multi-level logs for SIL + GMT manual test.
#
# Usage (after compile_sil):
#   bash scripts/verify/oem_a_afc_with_uss/smoke_obs_demo.sh
#
# Interactive GMT (keep DoIP + apps):
#   export GF_OBS_DEMO=1
#   export GF_COLLECTOR_STORE=$PWD/build/iox_multiproc_logs/collector_shared.ndjson
#   bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
#   GMT gui --project projects/oem_a/afc_with_uss
#   → OTA/UDS 连接 → DEM 读 DTC / Collector 本机或 UDS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
LOG_DIR="${BUILD}/iox_multiproc_logs"
STORE="${LOG_DIR}/collector_shared.ndjson"
DOIP="${BUILD}/gf_doip_ota_server"
if [[ ! -x "${DOIP}" ]]; then
  DOIP="${BUILD}/middleware/diag/gf_doip_ota_server"
fi
mkdir -p "${LOG_DIR}"
rm -f "${STORE}"
: >"${LOG_DIR}/doip_obs_demo.log"

export GF_OBS_DEMO=1
export GF_LOG_LEVEL=VERBOSE
export GF_COLLECTOR_STORE="${STORE}"
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

echo "${TAG} obs_demo: store=${STORE} DoIP seed + multiproc SIL"

"${DOIP}" >>"${LOG_DIR}/doip_obs_demo.log" 2>&1 &
DOIP_PID=$!
sleep 0.4
if ! kill -0 "${DOIP_PID}" 2>/dev/null; then
  echo "${TAG} DoIP failed; see ${LOG_DIR}/doip_obs_demo.log" >&2
  cat "${LOG_DIR}/doip_obs_demo.log" >&2 || true
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

bash "${SCRIPT_DIR}/run_sil_multiproc.sh"

USS_LOG="${LOG_DIR}/uss.log"
if [[ ! -f "${USS_LOG}" ]]; then
  echo "${TAG} missing ${USS_LOG}" >&2
  exit 1
fi

missing_levels=()
for lvl in FATAL ERROR WARN INFO DEBUG VERBOSE; do
  if ! grep -qE "log: \\[${lvl}\\].*obs_demo" "${LOG_DIR}"/*.log 2>/dev/null; then
    missing_levels+=("${lvl}")
  fi
done
if ((${#missing_levels[@]})); then
  echo "${TAG} FAIL: missing log levels: ${missing_levels[*]}" >&2
  grep -h 'log: \[' "${LOG_DIR}"/*.log 2>/dev/null | head -40 >&2 || true
  exit 1
fi

if [[ ! -s "${STORE}" ]] || ! grep -qE 'AliveMissed|ota_failed' "${STORE}"; then
  echo "${TAG} FAIL: expected collector events in ${STORE}" >&2
  cat "${STORE}" >&2 || true
  exit 1
fi
if ! grep -qE 'obs_demo: seeded' "${LOG_DIR}/doip_obs_demo.log"; then
  echo "${TAG} FAIL: DoIP did not seed obs_demo" >&2
  cat "${LOG_DIR}/doip_obs_demo.log" >&2 || true
  exit 1
fi

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
need = {0xC01234, 0xC01235, 0xC0A001}
missing = need - got
if missing:
    raise SystemExit(f"FAIL DEM missing {[hex(x) for x in missing]} got {[hex(x) for x in got]}")
ev = c.read_collector_events(offset=0, max_n=32)
print("Collector F201 events:", len(ev))
if len(ev) < 3:
    raise SystemExit(f"FAIL F201 expected >=3 events, got {len(ev)}")
c.close()
print("UDS DEM+Collector OK")
PY

echo ""
echo "${TAG} smoke_obs_demo OK"
echo "  SIL logs : ${LOG_DIR}/*.log   (grep 'log: \\[')"
echo "  NDJSON   : ${STORE}           → GMT Collector「本机文件」"
echo "  DoIP was : 127.0.0.1:${GF_DOIP_PORT} (stopped on exit)"
echo ""
echo "Interactive:"
echo "  export GF_OBS_DEMO=1 GF_COLLECTOR_STORE=${STORE}"
echo "  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh"
echo "  GMT gui --project projects/oem_a/afc_with_uss"
