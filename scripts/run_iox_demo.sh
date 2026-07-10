#!/usr/bin/env bash
# Start RouDi + USS feed publisher + demo_pipeline subscriber (P0 B3 smoke).
# Prerequisites:
#   bash scripts/bootstrap_deps.sh
#   cmake -B build -DGF_BUILD_TESTS=ON && cmake --build build -j$(nproc)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${GF_BUILD_DIR:-${ROOT}/build}"
RECV_COUNT="${GF_DEMO_RECV_COUNT:-5}"
TIMEOUT_SEC="${GF_DEMO_TIMEOUT_SEC:-30}"

# Source-built attr/acl live here; ensure runtime can find libacl/libattr.
export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

ROUDI="${BUILD}/iox-roudi"
PUB="${BUILD}/apps/simulators/uss_feed/gf_uss_feed"
SUB="${BUILD}/apps/demo_pipeline/gf_demo_pipeline"

for bin in "${ROUDI}" "${PUB}" "${SUB}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "Missing executable: ${bin}" >&2
    echo "Build first, e.g.:" >&2
    echo "  cmake -B build -DGF_BUILD_TESTS=ON && cmake --build build -j\$(nproc)" >&2
    exit 1
  fi
done

LOG_DIR="${BUILD}/iox_demo_logs"
mkdir -p "${LOG_DIR}"
ROUDI_LOG="${LOG_DIR}/roudi.log"
PUB_LOG="${LOG_DIR}/uss_feed.log"
SUB_LOG="${LOG_DIR}/demo_pipeline.log"

cleanup() {
  local code=$?
  set +e
  [[ -n "${PUB_PID:-}" ]] && kill "${PUB_PID}" 2>/dev/null
  [[ -n "${SUB_PID:-}" ]] && kill "${SUB_PID}" 2>/dev/null
  [[ -n "${ROUDI_PID:-}" ]] && kill "${ROUDI_PID}" 2>/dev/null
  wait 2>/dev/null
  exit "${code}"
}
trap cleanup EXIT INT TERM

echo "[run_iox_demo] starting RouDi ..."
"${ROUDI}" >"${ROUDI_LOG}" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "[run_iox_demo] RouDi failed to start; see ${ROUDI_LOG}" >&2
  cat "${ROUDI_LOG}" >&2 || true
  exit 1
fi

echo "[run_iox_demo] starting subscriber (expect ${RECV_COUNT} samples) ..."
"${SUB}" "${RECV_COUNT}" >"${SUB_LOG}" 2>&1 &
SUB_PID=$!
sleep 0.5

echo "[run_iox_demo] starting publisher ..."
"${PUB}" >"${PUB_LOG}" 2>&1 &
PUB_PID=$!

echo "[run_iox_demo] waiting (timeout ${TIMEOUT_SEC}s) ..."
SECONDS=0
while kill -0 "${SUB_PID}" 2>/dev/null; do
  if (( SECONDS >= TIMEOUT_SEC )); then
    echo "[run_iox_demo] TIMEOUT — subscriber did not finish" >&2
    echo "--- subscriber log ---" >&2
    cat "${SUB_LOG}" >&2 || true
    echo "--- publisher log ---" >&2
    cat "${PUB_LOG}" >&2 || true
    echo "--- roudi log (tail) ---" >&2
    tail -50 "${ROUDI_LOG}" >&2 || true
    exit 1
  fi
  sleep 0.2
done

wait "${SUB_PID}"
SUB_RC=$?
if [[ "${SUB_RC}" -ne 0 ]]; then
  echo "[run_iox_demo] subscriber exited ${SUB_RC}" >&2
  cat "${SUB_LOG}" >&2 || true
  exit "${SUB_RC}"
fi

echo "[run_iox_demo] OK — received ${RECV_COUNT} sample(s)"
echo "logs: ${LOG_DIR}/"
cat "${SUB_LOG}"
exit 0
