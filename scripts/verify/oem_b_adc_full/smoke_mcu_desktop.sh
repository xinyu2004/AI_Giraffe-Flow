#!/usr/bin/env bash
# P1 Track M: desktop MCU IPC 联调（无真 MCU、无 iceoryx）
#   peer (模拟 CP) ←Unix socket→ gateway (AP)
#
# Usage:
#   bash scripts/verify/oem_b_adc_full/smoke_mcu_desktop.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD="${GF_BUILD_DIR:-${ROOT}/build-mcu-desktop}"
ROUNDS="${GF_MCU_PEER_ROUNDS:-5}"
TIMEOUT_SEC="${GF_MCU_TIMEOUT_SEC:-30}"
SOCK="${GF_CP_IPC_PATH:-/tmp/gf_cp_ipc.sock}"
PROFILE="${ROOT}/cmake/profiles/mcu_desktop.cmake"

export GF_CP_IPC_PATH="${SOCK}"
export GF_MCU_PEER_ROUNDS="${ROUNDS}"
export GF_MCU_GATEWAY_ROUNDS="${ROUNDS}"

rm -f "${SOCK}"

echo "[smoke_mcu_desktop] cmake → ${BUILD}"
cmake -B "${BUILD}" -S "${ROOT}" \
  -DGF_BUILD_TESTS=ON \
  -DGF_USE_GENERATED=OFF \
  -DGF_FORCE_NO_ICEORYX=ON \
  -DGF_SKU_CMAKE="${PROFILE}"
cmake --build "${BUILD}" -j"$(nproc)" \
  --target gf_cp_ipc_peer gf_mcu_cp_gateway gf_cross_domain_ipc_smoke

echo "[smoke_mcu_desktop] unit smoke ..."
ctest --test-dir "${BUILD}" -R gf_cross_domain_ipc_smoke --output-on-failure

PEER="${BUILD}/apps/simulators/cp_ipc_peer/gf_cp_ipc_peer"
GW="${BUILD}/apps/adapters/mcu_cp_gateway/gf_mcu_cp_gateway"
LOG_DIR="${BUILD}/mcu_desktop_logs"
mkdir -p "${LOG_DIR}"
PEER_LOG="${LOG_DIR}/peer.log"
GW_LOG="${LOG_DIR}/gateway.log"

cleanup() {
  local code=$?
  set +e
  [[ -n "${GW_PID:-}" ]] && kill "${GW_PID}" 2>/dev/null
  [[ -n "${PEER_PID:-}" ]] && kill "${PEER_PID}" 2>/dev/null
  wait 2>/dev/null
  rm -f "${SOCK}"
  exit "${code}"
}
trap cleanup EXIT INT TERM

echo "[smoke_mcu_desktop] start peer ..."
"${PEER}" >"${PEER_LOG}" 2>&1 &
PEER_PID=$!
sleep 0.3

echo "[smoke_mcu_desktop] start gateway (rounds=${ROUNDS}) ..."
"${GW}" >"${GW_LOG}" 2>&1 &
GW_PID=$!

SECONDS=0
while kill -0 "${PEER_PID}" 2>/dev/null; do
  if (( SECONDS >= TIMEOUT_SEC )); then
    echo "[smoke_mcu_desktop] TIMEOUT" >&2
    echo "--- peer ---" >&2
    cat "${PEER_LOG}" >&2 || true
    echo "--- gateway ---" >&2
    cat "${GW_LOG}" >&2 || true
    exit 1
  fi
  sleep 0.1
done

wait "${PEER_PID}"
PEER_RC=$?
wait "${GW_PID}" || true
GW_PID=

if [[ "${PEER_RC}" -ne 0 ]]; then
  echo "[smoke_mcu_desktop] peer failed rc=${PEER_RC}" >&2
  cat "${PEER_LOG}" >&2 || true
  cat "${GW_LOG}" >&2 || true
  exit 1
fi

if ! grep -q "gf-cp-ipc-peer: OK" "${PEER_LOG}"; then
  echo "[smoke_mcu_desktop] peer OK marker missing" >&2
  cat "${PEER_LOG}" >&2 || true
  exit 1
fi
if ! grep -q "gf-mcu-cp-gateway: OK" "${GW_LOG}"; then
  echo "[smoke_mcu_desktop] gateway OK marker missing" >&2
  cat "${GW_LOG}" >&2 || true
  exit 1
fi

echo "[smoke_mcu_desktop] OK (see ${LOG_DIR})"
