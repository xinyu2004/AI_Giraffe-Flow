#!/usr/bin/env bash
# SIL: host compile for oem_a / afc_no_uss
#   bootstrap (if needed) → compose → generate → cmake (host) → ctest
#
# Usage:
#   bash projects/oem_a/afc_no_uss/scripts/compile_sil.sh
#   GF_CXX=clang++ GF_CC=clang GF_BUILD_DIR=$PWD/build-clang bash …/compile_sil.sh
#   GF_SIL_TOOLCHAIN_FILE=cmake/toolchains/host-clang.cmake GF_BUILD_DIR=$PWD/build-clang bash …/compile_sil.sh
#
# Env (P2.5):
#   GF_BUILD_DIR              SIL build tree (default projects/.../build-sil)
#   GF_CC / GF_CXX            host compilers (e.g. clang / clang++)
#   GF_SIL_TOOLCHAIN_FILE     optional CMake toolchain (overrides GF_CC/CXX)
#   GF_DEPS_PREFIX            optional deps prefix when switching compilers
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env
gf_ensure_bootstrap
gf_prepare_codegen

SIL_CMAKE_ARGS=()
gf_sil_cmake_compiler_args SIL_CMAKE_ARGS

echo "${TAG} cmake SIL compile (host, GF_USE_GENERATED=ON) → ${BUILD_SIL} ..."
# Fresh trees: iceoryx downloads cpptoml into dependencies/install; pass PREFIX so
# the same configure pass (or the immediate retry) can find_package(cpptoml).
DEP_PREFIX="${BUILD_SIL}/dependencies/install"
cmake -S "${ROOT}" -B "${BUILD_SIL}" \
  "${SIL_CMAKE_ARGS[@]}" \
  -DGF_BUILD_TESTS=ON \
  -DGF_USE_GENERATED=ON \
  -DGF_GENERATED_DIR="${GEN_OUT}" \
  -DGF_SKU_CMAKE="${GEN_OUT}/gf_build.cmake" \
  -DCMAKE_PREFIX_PATH="${DEP_PREFIX}${CMAKE_PREFIX_PATH:+;${CMAKE_PREFIX_PATH}}" \
  || cmake -S "${ROOT}" -B "${BUILD_SIL}" \
    "${SIL_CMAKE_ARGS[@]}" \
    -DGF_BUILD_TESTS=ON \
    -DGF_USE_GENERATED=ON \
    -DGF_GENERATED_DIR="${GEN_OUT}" \
    -DGF_SKU_CMAKE="${GEN_OUT}/gf_build.cmake" \
    -DCMAKE_PREFIX_PATH="${DEP_PREFIX}${CMAKE_PREFIX_PATH:+;${CMAKE_PREFIX_PATH}}"
cmake --build "${BUILD_SIL}" -j"$(nproc)"

echo "${TAG} ctest (SIL) ..."
ctest --test-dir "${BUILD_SIL}" --output-on-failure

echo "${TAG} compile_sil OK"
