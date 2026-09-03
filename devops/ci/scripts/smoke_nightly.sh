#!/usr/bin/env bash
# L2 nightly: L0 → L1 (cyclone + iox) → DoIP path → FuSa SIL matrix.
# Does NOT flash / build SWU. DoIP stays here (not on every PR).
#
# Usage:
#   bash devops/ci/scripts/smoke_nightly.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"
CI="${ROOT}/devops/ci/scripts"
VERIFY="${ROOT}/projects/afc/scripts/verify"

echo "== nightly: L0 =="
bash "${CI}/smoke.sh"

echo "== nightly: L1 cyclone =="
bash "${ROOT}/scripts/smoke_bd_cyclone.sh"

echo "== nightly: L1 iox binding =="
bash "${ROOT}/middleware/bindings/iceoryx/testcases/run_iox_pubsub.sh"

echo "== nightly: DoIP path (no flash) =="
# smoke.sh already compiled host build; DoIP needs SKU build-sil — compile if missing
if [[ ! -d "${ROOT}/projects/afc/build-sil" ]]; then
  bash "${ROOT}/projects/afc/scripts/compile_sil.sh"
fi
bash "${VERIFY}/smoke_doip_ota.sh"

echo "== nightly: FuSa SIL matrix =="
GF_FUSA_SIL=1 bash "${ROOT}/fusa/scripts/run_cases.sh"

echo "CI nightly OK"
