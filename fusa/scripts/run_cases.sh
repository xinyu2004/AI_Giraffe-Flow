#!/usr/bin/env bash
# Run FuSa case matrix (L1, optional L2/L3) → fusa/runs/.
# Does not call project pack scripts; pack separately if needed.
#
# Usage:
#   bash fusa/scripts/run_cases.sh
#   GF_FUSA_CODEGEN=1 bash fusa/scripts/run_cases.sh
#   GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh
#
# Env:
#   GF_BUILD_DIR       default <repo>/build
#   GF_FUSA_CODEGEN    1 = run gf-codegen pytest subset
#   GF_FUSA_SIL        1 = L3 FuSa SIL suite (SIL-01/02/03/EM-02/06 + SIL-SM-01)
#   GF_FUSA_SIL_MCU    0 = skip SIL-06 MCU desktop (default 1)
#   GF_FUSA_T4         1 = production-release profile smoke (compose+build-prod+SIL-02)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

BUILD="${GF_BUILD_DIR:-${ROOT}/build}"
OUT_DIR="${ROOT}/fusa/runs"
mkdir -p "${OUT_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${OUT_DIR}/cases_${STAMP}.log"
TAG="[fusa]"

echo "${TAG} log → ${LOG}"
{
  echo "# Giraffe Flow FuSa run ${STAMP}"
  echo "# matrix: fusa/cases/README.md"
  echo "# policy: fusa/POLICY.md"
  echo
} >"${LOG}"

if [[ ! -d "${BUILD}" ]]; then
  echo "${TAG} ERROR: build dir missing: ${BUILD} (run cmake/compile_sil first)" >&2
  exit 1
fi

run_bin() {
  local name="$1"
  local bin
  bin="$(find "${BUILD}" -type f -name "${name}" -perm -111 2>/dev/null | head -n1 || true)"
  if [[ -z "${bin}" ]]; then
    echo "${TAG} SKIP ${name} (not built)"
    echo "# SKIP ${name}" >>"${LOG}"
    return 0
  fi
  echo "${TAG} RUN ${name}"
  {
    echo "===== ${name} ====="
    "${bin}"
    echo
  } >>"${LOG}" 2>&1
}

# L1 library smokes
for name in \
  gf_core_smoke \
  gf_osal_smoke \
  gf_osal_process_smoke \
  gf_com_loopback_smoke \
  gf_exec_smoke \
  gf_exec_em_smoke \
  gf_em_daemon_smoke \
  gf_sm_fg_smoke \
  gf_phm_alive_deadline_smoke \
  gf_collector_smoke \
  gf_collector_xproc_smoke \
  gf_log_smoke \
  gf_per_smoke \
  gf_tsync_smoke \
  gf_diag_doip_smoke \
  gf_ucm_package_manager_smoke \
  gf_iox_binding_smoke \
  gf_someip_binding_smoke \
  gf_dds_binding_smoke \
  gf_cross_domain_ipc_smoke
do
  run_bin "${name}"
done

if [[ "${GF_FUSA_CODEGEN:-0}" == "1" ]]; then
  echo "${TAG} L2 codegen pytest"
  {
    echo "===== L2 gf-codegen ====="
    python -m pytest \
      tools/gf-codegen/tests/test_observability.py \
      tools/gf-codegen/tests/test_compose_afc_with_uss.py \
      tools/gf-codegen/tests/test_afc_bench_golden.py \
      tools/gf-codegen/tests/test_lint_golden.py \
      -q --tb=line
    echo
  } >>"${LOG}" 2>&1
fi

if [[ "${GF_FUSA_SIL:-0}" == "1" ]]; then
  # L3 FuSa matrix: fusa/cases/sil_verify_cases.md (not debug-path)
  echo "${TAG} L3 SIL FuSa suite"
  run_sil() {
    local id="$1"
    local script="$2"
    echo "${TAG} RUN ${id} → ${script}"
    {
      echo "===== L3 ${id} ====="
      echo "# script: ${script}"
      bash "${script}"
      echo "# ${id} OK"
      echo
    } >>"${LOG}" 2>&1
  }
  run_sil "SIL-01" scripts/verify/oem_a_afc_with_uss/smoke_sil.sh
  run_sil "SIL-02" scripts/verify/oem_a_afc_with_uss/smoke_sil_multiproc.sh
  run_sil "SIL-03" scripts/verify/oem_a_afc_with_uss/smoke_sil_phm_fault.sh
  run_sil "SIL-SM-01" scripts/verify/oem_a_afc_with_uss/smoke_sil_sm_fg.sh
  run_sil "SIL-EM-02" scripts/verify/oem_a_afc_with_uss/smoke_sil_em_daemon.sh
  if [[ "${GF_FUSA_SIL_MCU:-1}" == "1" ]]; then
    run_sil "SIL-06" scripts/verify/oem_b_adc_full/smoke_mcu_desktop.sh
  else
    echo "${TAG} SKIP SIL-06 (GF_FUSA_SIL_MCU=0)"
    echo "# SKIP SIL-06" >>"${LOG}"
  fi
fi

if [[ "${GF_FUSA_T4:-0}" == "1" ]]; then
  echo "${TAG} T4 production-release profile"
  {
    echo "===== L3 SIL-T4 / SG-05 ====="
    bash scripts/verify/oem_a_afc_with_uss/smoke_production_profile.sh
    echo "# SIL-T4 OK"
    echo
  } >>"${LOG}" 2>&1
fi

echo "${TAG} CASE summary:"
grep -E '^CASE ' "${LOG}" | tee /dev/stderr | wc -l | xargs -I{} echo "${TAG} {} CASE lines"
echo "${TAG} matrix: fusa/cases/README.md"
echo "${TAG} OK → ${LOG}"
