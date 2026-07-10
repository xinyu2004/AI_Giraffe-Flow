#!/usr/bin/env bash
# Shared helpers for oem_a / afc_with_uss SIL & HIL scripts.
# shellcheck shell=bash

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "${PROJECT_DIR}/../../.." && pwd)"
PROJECT_YAML="${PROJECT_DIR}/project.yaml"
SOR_JSON="${PROJECT_DIR}/gf.sor.json"
GEN_OUT="${PROJECT_DIR}/generated"
TAG="[afc_with_uss]"

DEPS_PREFIX="${ROOT}/middleware/.deps-prefix"
THIRD_PARTY="${ROOT}/middleware/third_party"
BUILD_SIL="${ROOT}/build"
BUILD_HIL="${ROOT}/build-hil"

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
    bash "${ROOT}/scripts/bootstrap_deps.sh" ${GF_BOOTSTRAP_EXTRA:-}
  fi
}

gf_prepare_codegen() {
  echo "${TAG} compose ..."
  gf-codegen compose --project "${PROJECT_YAML}"

  echo "${TAG} generate → ${GEN_OUT} ..."
  gf-codegen generate "${SOR_JSON}" --out "${GEN_OUT}"
}
