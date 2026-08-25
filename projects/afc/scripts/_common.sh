#!/usr/bin/env bash
# Shared helpers for AFC SIL & HIL scripts.
# shellcheck shell=bash

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "${PROJECT_DIR}/../.." && pwd)"
PROJECT_YAML="${PROJECT_DIR}/project.yaml"
SOR_JSON="${PROJECT_DIR}/gf.sor.json"
GEN_OUT="${PROJECT_DIR}/generated"
TAG="[afc]"

DEPS_PREFIX="${GF_DEPS_PREFIX:-${ROOT}/middleware/.deps-prefix}"
THIRD_PARTY="${ROOT}/middleware/third_party"
# Default per-SKU trees; GF_BUILD_DIR / GF_BUILD_DIR_HIL are reserved overrides only.
BUILD_SIL="${GF_BUILD_DIR:-${PROJECT_DIR}/build-sil}"
BUILD_HIL="${GF_BUILD_DIR_HIL:-${PROJECT_DIR}/build-hil}"

gf_project_env() {
  cd "${ROOT}"
  export PATH="${ROOT}/.venv/bin:${PATH}"
  echo "${TAG} repo=${ROOT}"
  echo "${TAG} project=${PROJECT_DIR}"
}

gf_ensure_bootstrap() {
  local need=0
  if [[ ! -f "${DEPS_PREFIX}/include/sys/acl.h" ]]; then
    need=1
  fi
  if [[ ! -d "${THIRD_PARTY}/iceoryx/iceoryx_meta" ]]; then
    need=1
  fi
  if [[ "${need}" -eq 1 ]]; then
    echo "${TAG} bootstrap (if needed) ..."
    # shellcheck disable=SC2086
    GF_DEPS_PREFIX="${DEPS_PREFIX}" \
      GF_CC="${GF_CC:-}" GF_CXX="${GF_CXX:-}" \
      bash "${ROOT}/scripts/bootstrap_deps.sh" ${GF_BOOTSTRAP_EXTRA:-}
  fi
}

# SIL cmake build root vs staged runtime root.
# run_sil may export GF_BUILD_DIR=$runtime for EM; stage still uses the cmake tree.
gf_sil_build_root() {
  local d="${GF_BUILD_DIR:-${BUILD_SIL}}"
  if [[ "$(basename "${d}")" == "runtime" ]]; then
    dirname "${d}"
  else
    echo "${d}"
  fi
}

# GMT Record / MCAP artifacts — under cmake SIL tree, never under staged runtime/
# (run_sil sets GF_BUILD_DIR=runtime for EM; obs must not bloat the board tree).
# No automatic live JSONL tee; use GMT GUI Record → gmt_record.jsonl (default name).
gf_obs_dir() {
  echo "${GF_OBS_OUT:-$(gf_sil_build_root)/observability}"
}

gf_sil_runtime_dir() {
  if [[ -n "${GF_RUNTIME_DIR:-}" ]]; then
    echo "${GF_RUNTIME_DIR}"
  else
    echo "$(gf_sil_build_root)/runtime"
  fi
}

# True (exit 0) if marker missing, or any file/dir tree has a file newer than marker.
# Same idea as Make: compare mtimes, no content hash.
gf_sil_marker_stale() {
  local marker="$1"
  shift
  [[ -e "${marker}" ]] || return 0
  local p
  for p in "$@"; do
    if [[ -f "${p}" && "${p}" -nt "${marker}" ]]; then
      return 0
    fi
    if [[ -d "${p}" ]]; then
      if find "${p}" -type f -newer "${marker}" -print -quit 2>/dev/null | grep -q .; then
        return 0
      fi
    fi
  done
  return 1
}

# Authoring (gf-config Verify/Generate) owns compose + codegen. Compile only builds.
gf_require_generated() {
  local missing=0
  local f
  for f in \
    "${GEN_OUT}/gf_build.cmake" \
    "${GEN_OUT}/include/gf_gen/deploy_config.hpp" \
    "${SOR_JSON}"
  do
    if [[ ! -f "${f}" ]]; then
      echo "${TAG} ERROR: missing ${f}" >&2
      missing=1
    fi
  done
  if [[ "${missing}" -ne 0 ]]; then
    echo "${TAG} ERROR: generated/ incomplete — finish gf-config first:" >&2
    echo "${TAG}   1) Save (Ctrl+S)  2) Verify (Ctrl+R)  → compose → generated/*.hpp + gf.sor.json" >&2
    echo "${TAG}   3) Generate (Ctrl+G) when Proxy/Skeleton needed" >&2
    echo "${TAG} Authoring ends after Verify (+ Generate). compile_* / run_* do not compose." >&2
    return 1
  fi
  echo "${TAG} generated/ present (gf-config Verify/Generate) — compile will not compose"
  return 0
}

# Octave → oct_gen (mtime). Prefer console entry like gf-config; ⊥ gf-codegen.
gf_octavecoder_sync() {
  local sku="${1:-afc}"
  local coder_src="${ROOT}/tools/gf-octavecoder/src"
  if [[ ! -d "${coder_src}/gf_octavecoder" ]]; then
    echo "${TAG} WARN: gf-octavecoder missing; skip oct_gen" >&2
    return 0
  fi
  echo "${TAG} gf-octavecoder generate sku=${sku} ..."
  if command -v gf-octavecoder >/dev/null 2>&1; then
    gf-octavecoder generate --repo-root "${ROOT}" --sku "${sku}"
    return $?
  fi
  # Dev fallback before pip install -e tools/gf-octavecoder
  local py="${ROOT}/.venv/bin/python"
  [[ -x "${py}" ]] || py="$(command -v python3)"
  echo "${TAG} WARN: gf-octavecoder not on PATH — using python -m (pip install -e tools/gf-octavecoder)" >&2
  PYTHONPATH="${coder_src}${PYTHONPATH:+:${PYTHONPATH}}" \
    "${py}" -m gf_octavecoder generate --repo-root "${ROOT}" --sku "${sku}"
}

# Stage when runtime incomplete, or build products newer than staged copies.
gf_sil_need_stage() {
  local rt build em_src em_dst
  rt="$(gf_sil_runtime_dir)"
  build="$(gf_sil_build_root)"
  [[ "${GF_FORCE_COMPILE:-0}" == "1" ]] && return 0
  em_dst="${rt}/bin/gf_em_daemon"
  [[ -x "${em_dst}" ]] || return 0
  [[ -x "${rt}/bin/iox-roudi" ]] || return 0
  [[ -e "${rt}/lib/libgf_channel.so" || -e "${rt}/lib/libgf_channel.so.0" ]] || return 0
  em_src="${build}/middleware/exec/gf_em_daemon"
  [[ -f "${em_src}" && "${em_src}" -nt "${em_dst}" ]] && return 0
  if [[ -d "${build}/lib" ]]; then
    if find "${build}/lib" -maxdepth 1 -name 'libgf_*.so*' -newer "${em_dst}" -print -quit 2>/dev/null | grep -q .; then
      return 0
    fi
  fi
  return 1
}

# cmake -S/-B every run dirties Unix Makefiles and rebuilds iceoryx/etc. for no reason.
# CMake often does NOT bump CMakeCache.txt mtime when values are unchanged — so we use
# our own sentinel touched after a successful configure.
gf_sil_cmake_configure_sentinel() {
  echo "$(gf_sil_build_root)/.gf_cmake_configure_ok"
}

gf_sil_need_cmake_configure() {
  local build sentinel
  build="$(gf_sil_build_root)"
  sentinel="$(gf_sil_cmake_configure_sentinel)"
  [[ "${GF_FORCE_COMPILE:-0}" == "1" ]] && return 0
  [[ -f "${build}/CMakeCache.txt" ]] || return 0
  [[ -f "${sentinel}" ]] || return 0
  if [[ -f "${GEN_OUT}/gf_build.cmake" && "${GEN_OUT}/gf_build.cmake" -nt "${sentinel}" ]]; then
    return 0
  fi
  if [[ -f "${ROOT}/CMakeLists.txt" && "${ROOT}/CMakeLists.txt" -nt "${sentinel}" ]]; then
    return 0
  fi
  if find "${ROOT}/cmake" "${ROOT}/middleware" "${PROJECT_DIR}/apps" \
    \( -name 'CMakeLists.txt' -o -name '*.cmake' \) \
    ! -path '*/third_party/*' ! -path '*/.deps-prefix/*' \
    -newer "${sentinel}" -print -quit 2>/dev/null | grep -q .; then
    return 0
  fi
  return 1
}

gf_sil_touch_cmake_configure_sentinel() {
  local s
  s="$(gf_sil_cmake_configure_sentinel)"
  mkdir -p "$(dirname "${s}")"
  touch "${s}"
}

# Fill nameref array with host compiler / toolchain cmake flags.
# Env: GF_SIL_TOOLCHAIN_FILE | GF_CC / GF_CXX  (HIL uses compile_hil's GF_CROSS_* instead)
gf_sil_cmake_compiler_args() {
  local -n _out="$1"
  _out=()
  if [[ -n "${GF_SIL_TOOLCHAIN_FILE:-}" ]]; then
    if [[ ! -f "${GF_SIL_TOOLCHAIN_FILE}" ]]; then
      echo "${TAG} ERROR: GF_SIL_TOOLCHAIN_FILE not found: ${GF_SIL_TOOLCHAIN_FILE}" >&2
      return 1
    fi
    echo "${TAG} SIL toolchain file=${GF_SIL_TOOLCHAIN_FILE}"
    _out+=("-DCMAKE_TOOLCHAIN_FILE=${GF_SIL_TOOLCHAIN_FILE}")
    return 0
  fi
  if [[ -n "${GF_CC:-}" ]]; then
    echo "${TAG} SIL CC=${GF_CC}"
    _out+=("-DCMAKE_C_COMPILER=${GF_CC}")
  fi
  if [[ -n "${GF_CXX:-}" ]]; then
    echo "${TAG} SIL CXX=${GF_CXX}"
    _out+=("-DCMAKE_CXX_COMPILER=${GF_CXX}")
  fi
}
