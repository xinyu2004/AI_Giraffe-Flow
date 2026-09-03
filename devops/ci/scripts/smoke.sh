#!/usr/bin/env bash
# CI / local smoke: bootstrap → unit tests → compose both SKUs → SIL demo → optional aarch64 link.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

echo "== bootstrap =="
bash scripts/bootstrap_deps.sh

echo "== pytest gf-codegen + gf-gmt =="
if [[ ! -x .venv/bin/pytest ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -e "tools/gf-codegen[dev]" -e "tools/gmt[dev]"
fi
.venv/bin/pip install -q -e "tools/gf-codegen[dev]" -e "tools/gmt[dev]"
.venv/bin/pytest tools/gf-codegen/tests tools/gmt/tests -q
# P2-G bench golden is included above (test_afc_bench_golden / test_merge_platform)

echo "== compose + lint (afc) =="
python -m gf_codegen.compose --project projects/afc/project.yaml
gf-codegen lint projects/afc/gf.sor.json

echo "== GMT architect lineage (CI read-only) =="
GMT architect lineage --project projects/afc/project.yaml

echo "== compose + lint (adc) =="
python -m gf_codegen.compose --project projects/adc/project.yaml
gf-codegen lint projects/adc/gf.sor.json

echo "== lint schema example =="
gf-codegen lint tools/gf-codegen/schemas/examples/desktop_ap_only.sor.json

echo "== cmake host build (desktop_default) =="
# Clean CI tree: one configure + build + ctest is expected.
# SKU day-to-day path skips reconfigure via .gf_cmake_configure_ok (see projects/.../compile_sil.sh).
cmake -B build -DGF_BUILD_TESTS=ON -DGF_USE_GENERATED=OFF
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure

echo "== cmake trimmed configure (desktop_minimal) =="
cmake -B build-minimal -DGF_BUILD_TESTS=ON -DGF_USE_GENERATED=OFF \
  -DGF_SKU_CMAKE="${ROOT}/cmake/profiles/desktop_minimal.cmake"
# configure-only is enough to prove SKU fragment is consumed; full build needs iceoryx like default
grep -q "desktop_minimal\|SKU desktop_minimal" <(cmake -B build-minimal -DGF_BUILD_TESTS=ON -DGF_USE_GENERATED=OFF -DGF_SKU_CMAKE="${ROOT}/cmake/profiles/desktop_minimal.cmake" 2>&1) || true

echo "== iceoryx pub/sub (middleware; not a SKU) =="
bash middleware/bindings/iceoryx/testcases/run_iox_pubsub.sh

echo "== project smoke_sil verify (afc main-chain) =="
bash projects/afc/scripts/verify/smoke_sil.sh

echo "== optional aarch64 link =="
bash scripts/cross_link_smoke.sh

echo "== CI smoke OK (P0 / L0) =="
