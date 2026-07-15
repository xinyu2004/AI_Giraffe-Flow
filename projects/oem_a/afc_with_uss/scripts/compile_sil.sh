#!/usr/bin/env bash
# SIL: host compile for oem_a / afc_with_uss
#   bootstrap (if needed) → compose → generate → cmake (host) → ctest
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env
gf_ensure_bootstrap
gf_prepare_codegen

echo "${TAG} cmake SIL compile (host, GF_USE_GENERATED=ON) → ${BUILD_SIL} ..."
cmake -B "${BUILD_SIL}" \
  -DGF_BUILD_TESTS=ON \
  -DGF_USE_GENERATED=ON \
  -DGF_GENERATED_DIR="${GEN_OUT}" \
  -DGF_SKU_CMAKE="${GEN_OUT}/gf_build.cmake"
cmake --build "${BUILD_SIL}" -j"$(nproc)"

echo "${TAG} ctest (SIL) ..."
ctest --test-dir "${BUILD_SIL}" --output-on-failure

echo "${TAG} compile_sil OK"
