#!/usr/bin/env bash
# L3 release gate (cautious): L0 → full toolchain SIL → L1 → DoIP → T4 → FuSa evidence pack.
# No SWU / flash smoke.
#
# Usage:
#   bash devops/ci/scripts/smoke_release.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"
CI="${ROOT}/devops/ci/scripts"
VERIFY="${ROOT}/projects/afc/scripts/verify"

echo "== release: L0 =="
bash "${CI}/smoke.sh"

echo "== release: toolchain SIL (observability / inject / inject_b2 / vcd) =="
# Ensure SKU SIL exists for observability (L0 uses host build + smoke_sil which may create it)
if [[ ! -d "${ROOT}/projects/afc/build-sil" ]]; then
  bash "${ROOT}/projects/afc/scripts/compile_sil.sh"
fi
GF_SKIP_COMPILE=1 GF_CI_INJECT_B2=1 bash "${CI}/smoke_toolchain.sh"

echo "== release: L1 cyclone + iox =="
bash "${ROOT}/scripts/smoke_bd_cyclone.sh"
bash "${ROOT}/scripts/run_iox_demo.sh"

echo "== release: DoIP path (no flash) =="
bash "${VERIFY}/smoke_doip_ota.sh"

echo "== release: FuSa T4 =="
GF_FUSA_T4=1 bash "${ROOT}/fusa/scripts/run_cases.sh"

echo "== release: generate FuSa evidence pack =="
# Packs SOR/lineage/mcap/VCD/inject sessions + latest cases_*.log; fails if required evidence missing.
GF_FUSA_PACK_RELEASE=1 bash "${ROOT}/projects/afc/scripts/generate_fusa_artifacts.sh"

echo "CI release gate OK → fusa/packs/afc/"
