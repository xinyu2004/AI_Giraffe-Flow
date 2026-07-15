#!/usr/bin/env bash
# HIL: cross-compile for board (default aarch64-linux-gnu).
#   bootstrap (cross) → compose → generate → cmake (toolchain)
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/compile_hil.sh
#   GF_CROSS_PREFIX=aarch64-linux-gnu bash .../compile_hil.sh
#
# Note: cross bootstrap writes middleware/.deps-prefix with the cross toolchain
# (overwrites a prior host SIL staging). Re-run compile_sil / bootstrap without
# GF_CROSS_PREFIX when switching back to host.
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

gf_prepare_codegen

echo "${TAG} cmake HIL compile → ${BUILD_HIL} ..."
cmake -B "${BUILD_HIL}" \
  -DCMAKE_TOOLCHAIN_FILE="${TOOLCHAIN}" \
  -DGF_BUILD_TESTS=ON \
  -DGF_USE_GENERATED=ON \
  -DGF_GENERATED_DIR="${GEN_OUT}" \
  -DGF_SKU_CMAKE="${GEN_OUT}/gf_build.cmake"
cmake --build "${BUILD_HIL}" -j"$(nproc)"

echo "${TAG} compile_hil OK (binaries are for board; not executed on host)"
file "${BUILD_HIL}/apps/demo_pipeline/gf_demo_pipeline" 2>/dev/null || true
