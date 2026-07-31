#!/usr/bin/env bash
# Collect L1 (and optional L2/L3) trust-evidence logs under evidence/sil/.
#
# Usage:
#   bash scripts/verify/trust_evidence_modules.sh
#   GF_TRUST_EVIDENCE_CODEGEN=1 bash scripts/verify/trust_evidence_modules.sh
#   GF_TRUST_EVIDENCE_SIL=1 bash scripts/verify/trust_evidence_modules.sh
#
# Env:
#   GF_BUILD_DIR                 default <repo>/build
#   GF_TRUST_EVIDENCE_CODEGEN    1 = run gf-codegen pytest subset
#   GF_TRUST_EVIDENCE_SIL        1 = run selected SIL verify (heavy)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

BUILD="${GF_BUILD_DIR:-${ROOT}/build}"
OUT_DIR="${ROOT}/evidence/sil"
mkdir -p "${OUT_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${OUT_DIR}/modules_${STAMP}.log"
TAG="[trust_evidence]"

echo "${TAG} log → ${LOG}"
{
  echo "# Giraffe Flow trust-evidence run ${STAMP}"
  echo "# matrix: docs/reports/trust-evidence/README.md"
  echo "# policy: docs/zh/operations/TRUST_EVIDENCE.md"
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
  gf_com_loopback_smoke \
  gf_exec_smoke \
  gf_sm_fg_smoke \
  gf_phm_alive_deadline_smoke \
  gf_collector_smoke \
  gf_diag_doip_smoke \
  gf_ucm_package_manager_smoke \
  gf_iox_binding_smoke \
  gf_someip_binding_smoke \
  gf_dds_binding_smoke \
  gf_cross_domain_ipc_smoke
do
  run_bin "${name}"
done

if [[ "${GF_TRUST_EVIDENCE_CODEGEN:-0}" == "1" ]]; then
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

if [[ "${GF_TRUST_EVIDENCE_SIL:-0}" == "1" ]]; then
  echo "${TAG} L3 SIL (phm_fault only by default set)"
  {
    echo "===== L3 SIL-03 phm_fault ====="
    bash scripts/verify/oem_a_afc_with_uss/smoke_sil_phm_fault.sh
    echo
  } >>"${LOG}" 2>&1
fi

echo "${TAG} CASE summary:"
grep -E '^CASE ' "${LOG}" | tee /dev/stderr | wc -l | xargs -I{} echo "${TAG} {} CASE lines"
echo "${TAG} matrix: docs/reports/trust-evidence/README.md"
echo "${TAG} OK → ${LOG}"
