#!/usr/bin/env bash
# SIL: host compile for afc
#   bootstrap → require generated/ (gf-config) → cmake → build(Ninja/Make 增量) → ctest(可选) → stage(mtime)
#
# 无内容 SHA stamp。差异编译交给构建系统（mtime + depfile）；壳只对 stage 做 -newer；compose 仅 gf-config。
#
# Usage:
#   bash projects/afc/scripts/compile_sil.sh
#   GF_CXX=clang++ GF_CC=clang GF_BUILD_DIR=$PWD/build-clang bash …/compile_sil.sh
#
# Env:
#   GF_BUILD_DIR              SIL build tree (default projects/.../build-sil)
#   GF_CC / GF_CXX            host compilers
#   GF_SIL_TOOLCHAIN_FILE     optional CMake toolchain
#   GF_DEPS_PREFIX            optional deps prefix
#   GF_FORCE_COMPILE=1        force cmake configure + stage（build 仍由 Ninja 增量）
#   GF_CTEST=1                run ctest（默认跳过；CI 请显式打开）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

# Prefer cmake build root even if caller exported GF_BUILD_DIR=…/runtime
BUILD_SIL="$(gf_sil_build_root)"
export GF_BUILD_DIR="${BUILD_SIL}"

gf_ensure_bootstrap
gf_require_generated

SIL_CMAKE_ARGS=()
gf_sil_cmake_compiler_args SIL_CMAKE_ARGS

# Prefer Ninja when creating a fresh build tree (better incremental than Unix Makefiles).
if [[ ! -f "${BUILD_SIL}/CMakeCache.txt" ]] && command -v ninja >/dev/null 2>&1; then
  SIL_CMAKE_ARGS+=("-G" "Ninja")
  echo "${TAG} CMake generator=Ninja"
fi

if gf_sil_need_cmake_configure; then
  echo "${TAG} cmake configure → ${BUILD_SIL} ..."
  DEP_PREFIX="${ROOT}/middleware/.deps-prefix"
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
  gf_sil_touch_cmake_configure_sentinel
else
  echo "${TAG} cmake configure: up-to-date (mtime; skip — avoids dirtying iceoryx rebuild)"
fi

echo "${TAG} cmake --build (incremental via Ninja/Make) ..."
cmake --build "${BUILD_SIL}" -j"$(nproc)"

if [[ "${GF_CTEST:-0}" == "1" ]]; then
  echo "${TAG} ctest (SIL) ..."
  _CTEST_LDLIB="${BUILD_SIL}/lib"
  if [[ -d "${BUILD_SIL}/_dep-manifest/dlt-daemon/src/lib" ]]; then
    _CTEST_LDLIB="${_CTEST_LDLIB}:${BUILD_SIL}/_dep-manifest/dlt-daemon/src/lib"
  fi
  export LD_LIBRARY_PATH="${_CTEST_LDLIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  ctest --test-dir "${BUILD_SIL}" --output-on-failure
else
  echo "${TAG} ctest skipped (set GF_CTEST=1 to run)"
fi

if gf_sil_need_stage; then
  bash "${SCRIPT_DIR}/stage_sil_runtime.sh"
else
  echo "${TAG} stage: up-to-date (mtime; skip) → $(gf_sil_runtime_dir)"
fi

echo "${TAG} compile_sil OK — returning to caller"
