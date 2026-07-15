#!/usr/bin/env bash
# P1 Track E/U: exec/phm Alive-Deadline + ucm/diag DoIP stub smokes
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${GF_BUILD_DIR:-${ROOT}/build-eu-stub}"
PROFILE="${ROOT}/cmake/profiles/eu_stub.cmake"

# Prefer repo venv cmake (pip package) when system cmake is absent.
if [[ -x "${ROOT}/.venv/bin/cmake" ]]; then
  export PATH="${ROOT}/.venv/bin:${PATH}"
fi
if ! command -v cmake >/dev/null 2>&1; then
  echo "cmake not found; install cmake or use repo .venv" >&2
  exit 1
fi
if ! command -v ctest >/dev/null 2>&1; then
  echo "ctest not found; install cmake (includes ctest)" >&2
  exit 1
fi

echo "[smoke_eu_stub] cmake → ${BUILD}"
cmake -B "${BUILD}" -S "${ROOT}" \
  -DGF_BUILD_TESTS=ON \
  -DGF_USE_GENERATED=OFF \
  -DGF_FORCE_NO_ICEORYX=ON \
  -DGF_SKU_CMAKE="${PROFILE}"

cmake --build "${BUILD}" -j"$(nproc)" \
  --target gf_exec_smoke gf_phm_alive_deadline_smoke \
           gf_ucm_package_manager_smoke gf_diag_doip_smoke

echo "[smoke_eu_stub] ctest ..."
ctest --test-dir "${BUILD}" -R 'gf_(exec|phm|ucm|diag)_' --output-on-failure

echo "[smoke_eu_stub] OK"
