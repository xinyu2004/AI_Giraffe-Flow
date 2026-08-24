#!/usr/bin/env bash
# L0b / L3 toolchain SIL: observability → inject → gmt_vcd (+ optional inject_b2).
# Prefers GF_SKIP_COMPILE=1 when L0 (smoke.sh) already built SIL.
#
# Usage:
#   bash devops/ci/scripts/smoke_toolchain.sh
#   GF_SKIP_COMPILE=1 bash devops/ci/scripts/smoke_toolchain.sh
#   GF_CI_INJECT_B2=1 bash devops/ci/scripts/smoke_toolchain.sh   # release default
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

VERIFY="${ROOT}/projects/afc/scripts/verify"
export GF_SKIP_COMPILE="${GF_SKIP_COMPILE:-1}"

echo "== toolchain: observability =="
bash "${VERIFY}/smoke_sil_observability.sh"

echo "== toolchain: inject =="
bash "${VERIFY}/smoke_sil_inject.sh"

if [[ "${GF_CI_INJECT_B2:-0}" == "1" ]]; then
  echo "== toolchain: inject_b2 =="
  bash "${VERIFY}/smoke_sil_inject_b2.sh"
fi

echo "== toolchain: gmt_vcd =="
bash "${VERIFY}/smoke_gmt_vcd.sh"

echo "CI toolchain smoke OK"
