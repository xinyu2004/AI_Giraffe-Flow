#!/usr/bin/env bash
# HIL: cross-compile for board (default aarch64-linux-gnu).
#   bootstrap (cross) → compose(mtime) → cmake(按需) → build(增量)
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/compile_hil.sh
#   GF_CROSS_PREFIX=aarch64-linux-gnu bash .../compile_hil.sh
#
# Note: cross bootstrap writes middleware/.deps-prefix with the cross toolchain
# (overwrites a prior host SIL staging). Re-run compile_sil / bootstrap without
# GF_CROSS_PREFIX when switching back to host.
#
# Env:
#   GF_FORCE_COMPILE=1   force cmake configure configure
#   GF_CTEST=1           unused on HIL (binaries not executed on host)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

CROSS_PREFIX="${GF_CROSS_PREFIX:-aarch64-linux-gnu}"
TOOLCHAIN="${GF_TOOLCHAIN_FILE:-${ROOT}/cmake/toolchains/aarch64-linux-gnu.cmake}"

gf_project_env

if ! command -v "${CROSS_PREFIX}-g++" >/dev/null 2>&1; then
  echo "${TAG} ERROR: ${CROSS_PREFIX}-g++ not found. Install cross toolchain or set GF_CROSS_PREFIX." >&2
  exit 1
fi

echo "${TAG} HIL cross prefix=${CROSS_PREFIX}"
echo "${TAG} toolchain=${TOOLCHAIN}"

export GF_CROSS_PREFIX="${CROSS_PREFIX}"
echo "${TAG} bootstrap (cross → middleware/.deps-prefix) ..."
bash "${ROOT}/scripts/bootstrap_deps.sh"

gf_require_generated

# Sentinel / need_configure keyed off build-hil
export GF_BUILD_DIR="${BUILD_HIL}"

HIL_CMAKE_ARGS=(
  "-DCMAKE_TOOLCHAIN_FILE=${TOOLCHAIN}"
  "-DGF_BUILD_TESTS=ON"
  "-DGF_USE_GENERATED=ON"
  "-DGF_GENERATED_DIR=${GEN_OUT}"
  "-DGF_SKU_CMAKE=${GEN_OUT}/gf_build.cmake"
)
if [[ ! -f "${BUILD_HIL}/CMakeCache.txt" ]] && command -v ninja >/dev/null 2>&1; then
  HIL_CMAKE_ARGS+=("-G" "Ninja")
  echo "${TAG} CMake generator=Ninja"
fi

if gf_sil_need_cmake_configure; then
  echo "${TAG} cmake configure HIL → ${BUILD_HIL} ..."
  cmake -S "${ROOT}" -B "${BUILD_HIL}" "${HIL_CMAKE_ARGS[@]}"
  gf_sil_touch_cmake_configure_sentinel
else
  echo "${TAG} cmake configure HIL: up-to-date (mtime; skip)"
fi

echo "${TAG} cmake --build HIL (incremental) ..."
cmake --build "${BUILD_HIL}" -j"$(nproc)"

echo "${TAG} compile_hil OK (binaries are for board; not executed on host)"
file "${BUILD_HIL}/apps/demo_pipeline/gf_demo_pipeline" 2>/dev/null || true
