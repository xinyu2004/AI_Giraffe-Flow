#!/usr/bin/env bash
# Shared helpers for oem_a / afc_with_uss SIL & HIL scripts.
# shellcheck shell=bash

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "${PROJECT_DIR}/../../.." && pwd)"
PROJECT_YAML="${PROJECT_DIR}/project.yaml"
SOR_JSON="${PROJECT_DIR}/gf.sor.json"
GEN_OUT="${PROJECT_DIR}/generated"
TAG="[afc_with_uss]"

DEPS_PREFIX="${GF_DEPS_PREFIX:-${ROOT}/middleware/.deps-prefix}"
THIRD_PARTY="${ROOT}/middleware/third_party"
BUILD_SIL="${GF_BUILD_DIR:-${ROOT}/build}"
BUILD_HIL="${GF_BUILD_DIR_HIL:-${ROOT}/build-hil}"

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

gf_prepare_codegen() {
  echo "${TAG} compose (python -m gf_codegen.compose) ..."
  python -m gf_codegen.compose --project "${PROJECT_YAML}"

  echo "${TAG} generate → ${GEN_OUT} ..."
  gf-codegen generate "${SOR_JSON}" --out "${GEN_OUT}"
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
