#!/usr/bin/env bash
# iceoryx pub/sub smoke (middleware only — no projects/).
# Usage: bash middleware/bindings/iceoryx/testcases/run_iox_pubsub.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../../.." && pwd)"
BUILD="${GF_BUILD_DIR:-${ROOT}/build}"
RECV_COUNT="${GF_IOX_SMOKE_RECV:-5}"
TIMEOUT_SEC="${GF_IOX_SMOKE_TIMEOUT:-30}"

export LD_LIBRARY_PATH="${ROOT}/middleware/.deps-prefix/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

ROUDI="${BUILD}/iox-roudi"
PUB="${BUILD}/middleware/bindings/iceoryx/gf_iox_smoke_pub"
SUB="${BUILD}/middleware/bindings/iceoryx/gf_iox_smoke_sub"
TOML="${HERE}/roudi_smoke.toml"

for bin in "${ROUDI}" "${PUB}" "${SUB}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "[iox_pubsub] missing: ${bin}" >&2
    echo "  cmake -B build -DGF_BUILD_TESTS=ON && cmake --build build -j\$(nproc)" >&2
    exit 1
  fi
done

LOG_DIR="${BUILD}/iox_pubsub_logs"
mkdir -p "${LOG_DIR}"
ROUDI_LOG="${LOG_DIR}/roudi.log"
PUB_LOG="${LOG_DIR}/pub.log"
SUB_LOG="${LOG_DIR}/sub.log"

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

echo "[iox_pubsub] RouDi -c ${TOML}"
"${ROUDI}" -c "${TOML}" >"${ROUDI_LOG}" 2>&1 &
ROUDI_PID=$!
sleep 1
if ! kill -0 "${ROUDI_PID}" 2>/dev/null; then
  echo "[iox_pubsub] RouDi failed; see ${ROUDI_LOG}" >&2
  cat "${ROUDI_LOG}" >&2 || true
  exit 1
fi

echo "[iox_pubsub] subscriber expect ${RECV_COUNT}"
"${SUB}" "${RECV_COUNT}" >"${SUB_LOG}" 2>&1 &
SUB_PID=$!
sleep 0.3

echo "[iox_pubsub] publisher"
"${PUB}" >"${PUB_LOG}" 2>&1 &
PUB_PID=$!

SECONDS=0
while kill -0 "${SUB_PID}" 2>/dev/null; do
  if (( SECONDS >= TIMEOUT_SEC )); then
    echo "[iox_pubsub] TIMEOUT" >&2
    echo "--- sub ---" >&2
    cat "${SUB_LOG}" >&2 || true
    echo "--- pub ---" >&2
    cat "${PUB_LOG}" >&2 || true
    echo "--- roudi ---" >&2
    tail -50 "${ROUDI_LOG}" >&2 || true
    exit 1
  fi
  sleep 0.2
done

wait "${SUB_PID}"
SUB_RC=$?
if [[ "${SUB_RC}" -ne 0 ]]; then
  echo "[iox_pubsub] subscriber exited ${SUB_RC}" >&2
  cat "${SUB_LOG}" >&2 || true
  exit "${SUB_RC}"
fi

echo "[iox_pubsub] OK — ${RECV_COUNT} sample(s)"
cat "${SUB_LOG}"
exit 0
