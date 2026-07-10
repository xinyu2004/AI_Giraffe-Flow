#!/usr/bin/env bash
# Optional aarch64 compile/link smoke (skips if cross g++ missing).
# Builds core/com/osal only (no iceoryx) so host middleware/.deps-prefix is not overwritten.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! command -v aarch64-linux-gnu-g++ >/dev/null 2>&1; then
  echo "[cross_link_smoke] SKIP: aarch64-linux-gnu-g++ not installed"
  exit 0
fi

export PATH="${ROOT}/.venv/bin:${PATH}"

echo "[cross_link_smoke] configuring build-aarch64 (OSAL/core/com only) ..."
cmake -B build-aarch64 \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/aarch64-linux-gnu.cmake \
  -DGF_BUILD_TESTS=ON \
  -DGF_WITH_ICEORYX=OFF \
  -DGF_FORCE_NO_ICEORYX=ON \
  -DGF_USE_GENERATED=OFF

echo "[cross_link_smoke] building (link smoke) ..."
cmake --build build-aarch64 -j"$(nproc)" --target gf_osal_smoke gf_core_smoke gf_com_loopback_smoke

echo "[cross_link_smoke] OK (binaries are aarch64; not executed on host)"
file build-aarch64/middleware/osal/gf_osal_smoke || true
