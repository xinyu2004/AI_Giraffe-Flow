#!/usr/bin/env bash
# CI / local smoke: bootstrap → unit tests → project smoke_sil → optional aarch64 link.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

echo "== bootstrap =="
bash scripts/bootstrap_deps.sh

echo "== pytest gf-codegen =="
if [[ ! -x .venv/bin/pytest ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -e "tools/codegen[dev]"
fi
.venv/bin/pytest tools/codegen/tests -q

echo "== cmake host build =="
cmake -B build -DGF_BUILD_TESTS=ON -DGF_USE_GENERATED=OFF
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure

echo "== project smoke_sil (afc_with_uss) =="
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh

echo "== optional aarch64 link =="
bash scripts/cross_link_smoke.sh

echo "CI smoke OK"
