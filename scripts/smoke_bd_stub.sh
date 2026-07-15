#!/usr/bin/env bash
# P1 Track B/D: DDS (+ optional SOME/IP stub) offline smoke
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${GF_BUILD_DIR:-${ROOT}/build-bd-stub}"
PROFILE="${ROOT}/cmake/profiles/bd_stub.cmake"

if [[ -x "${ROOT}/.venv/bin/cmake" ]]; then
  export PATH="${ROOT}/.venv/bin:${PATH}"
fi

echo "[smoke_bd_stub] cmake → ${BUILD}"
cmake -B "${BUILD}" -S "${ROOT}" \
  -DGF_BUILD_TESTS=ON \
  -DGF_USE_GENERATED=OFF \
  -DGF_FORCE_NO_ICEORYX=ON \
  -DGF_SKU_CMAKE="${PROFILE}"

cmake --build "${BUILD}" -j"$(nproc)" \
  --target gf_dds_binding_smoke gf_someip_binding_smoke

echo "[smoke_bd_stub] ctest ..."
ctest --test-dir "${BUILD}" -R 'gf_(dds|someip)_binding_smoke' --output-on-failure

echo "[smoke_bd_stub] emit-idl ..."
SOR_JSON="${ROOT}/tools/codegen/tests/fixtures/emit_idl_sample.sor.json"
IDL_OUT="${BUILD}/idl"
mkdir -p "${IDL_OUT}"
if command -v gf-codegen >/dev/null 2>&1; then
  gf-codegen emit-idl "${SOR_JSON}" --out "${IDL_OUT}"
else
  PYTHONPATH="${ROOT}/tools/codegen/src${PYTHONPATH:+:${PYTHONPATH}}" \
    "${ROOT}/.venv/bin/python" -c "from gf_codegen.cli import main; raise SystemExit(main(['emit-idl', '${SOR_JSON}', '--out', '${IDL_OUT}']))"
fi
test -f "${IDL_OUT}/gf_types.idl"

echo "[smoke_bd_stub] idlc wrapper (skip if missing) ..."
bash "${ROOT}/scripts/run_idlc.sh" "${IDL_OUT}/gf_types.idl" "${IDL_OUT}/gen" || true

echo "[smoke_bd_stub] OK"
