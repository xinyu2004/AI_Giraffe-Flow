#!/usr/bin/env bash
# HIL: cross-compile for board (default aarch64-linux-gnu).
#   bootstrap (cross) → compose(mtime) → cmake(按需) → build(增量) → optional stage
#
# Usage:
#   bash projects/afc/scripts/compile_hil.sh
#   GF_CROSS_PREFIX=aarch64-linux-gnu bash .../compile_hil.sh
#
# Note: cross bootstrap overwrites middleware/.deps-prefix; re-run host bootstrap
# when switching back to SIL.
#
# Env:
#   GF_FORCE_COMPILE=1   force cmake configure configure
#   GF_STAGE_HIL=1       also stage build-hil/runtime (default 0)
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
  DEP_PREFIX="${ROOT}/middleware/.deps-prefix"
  cmake -S "${ROOT}" -B "${BUILD_HIL}" \
    "${HIL_CMAKE_ARGS[@]}" \
    -DCMAKE_PREFIX_PATH="${DEP_PREFIX}${CMAKE_PREFIX_PATH:+;${CMAKE_PREFIX_PATH}}" \
    || cmake -S "${ROOT}" -B "${BUILD_HIL}" "${HIL_CMAKE_ARGS[@]}"
  gf_sil_touch_cmake_configure_sentinel
else
  echo "${TAG} cmake configure HIL: up-to-date (mtime; skip)"
fi

echo "${TAG} cmake --build HIL (incremental) ..."
cmake --build "${BUILD_HIL}" -j"$(nproc)"

if [[ "${GF_STAGE_HIL:-0}" == "1" ]]; then
  if gf_sil_need_stage; then
    bash "${SCRIPT_DIR}/stage_sil_runtime.sh"
  else
    echo "${TAG} stage HIL: up-to-date → $(gf_sil_runtime_dir)"
  fi
fi

echo "${TAG} compile_hil OK (binaries for board; try runtime/bin/giraffe_launch on target)"
file "${BUILD_HIL}/middleware/exec/gf_em_daemon" 2>/dev/null || true
