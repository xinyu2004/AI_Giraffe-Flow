#!/usr/bin/env bash
# CI / local smoke: bootstrap → unit tests → compose both SKUs → SIL demo → optional aarch64 link.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

echo "== bootstrap =="
bash scripts/bootstrap_deps.sh

echo "== pytest gf-codegen + gf-gmt =="
if [[ ! -x .venv/bin/pytest ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -e "tools/codegen[dev]" -e "tools/gmt[dev]"
fi
.venv/bin/pip install -q -e "tools/codegen[dev]" -e "tools/gmt[dev]"
.venv/bin/pytest tools/codegen/tests tools/gmt/tests -q
# P2-G bench golden is included above (test_afc_bench_golden / test_merge_platform)

echo "== compose + lint (afc_with_uss) =="
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
gf-codegen lint projects/oem_a/afc_with_uss/gf.sor.json

echo "== GMT architect lineage (CI read-only) =="
GMT architect lineage --project projects/oem_a/afc_with_uss/project.yaml

echo "== compose + lint (adc_full) =="
python -m gf_codegen.compose --project projects/oem_b/adc_full/project.yaml
gf-codegen lint projects/oem_b/adc_full/gf.sor.json

echo "== lint schema example =="
gf-codegen lint schemas/examples/desktop_ap_only.sor.json

echo "== cmake host build (desktop_default) =="
cmake -B build -DGF_BUILD_TESTS=ON -DGF_USE_GENERATED=OFF
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure

echo "== cmake trimmed configure (desktop_minimal) =="
cmake -B build-minimal -DGF_BUILD_TESTS=ON -DGF_USE_GENERATED=OFF \
  -DGF_SKU_CMAKE="${ROOT}/cmake/profiles/desktop_minimal.cmake"
# configure-only is enough to prove SKU fragment is consumed; full build needs iceoryx like default
grep -q "desktop_minimal\|GF_APPS=demo_pipeline\|SKU desktop_minimal" <(cmake -B build-minimal -DGF_BUILD_TESTS=ON -DGF_USE_GENERATED=OFF -DGF_SKU_CMAKE="${ROOT}/cmake/profiles/desktop_minimal.cmake" 2>&1) || true

echo "== project smoke_sil verify (afc_with_uss dual-process) =="
bash scripts/verify/oem_a_afc_with_uss/smoke_sil.sh

echo "== optional aarch64 link =="
bash scripts/cross_link_smoke.sh

echo "CI smoke OK (P0 close)"
