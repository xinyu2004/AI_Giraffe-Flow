#!/usr/bin/env bash
# P2 Track B: CycloneDDS real pub/sub smoke (≥1 event). Does NOT run iceoryx SIL.
#
# Prerequisites:
#   bash scripts/bootstrap_deps.sh   # fetches middleware/third_party/cyclonedds @ 0.10.5
#
# Usage:
#   bash scripts/smoke_bd_cyclone.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${GF_BUILD_DIR:-${ROOT}/build-bd-cyclone}"
PROFILE="${ROOT}/cmake/profiles/bd_cyclone.cmake"
CDDS="${ROOT}/middleware/third_party/cyclonedds"

if [[ -x "${ROOT}/.venv/bin/cmake" ]]; then
  export PATH="${ROOT}/.venv/bin:${PATH}"
fi

if [[ ! -f "${CDDS}/CMakeLists.txt" ]]; then
  echo "[smoke_bd_cyclone] CycloneDDS missing → bootstrap ..."
  bash "${ROOT}/scripts/bootstrap_deps.sh"
fi
if [[ ! -f "${CDDS}/CMakeLists.txt" ]]; then
  echo "[smoke_bd_cyclone] still no ${CDDS}; abort" >&2
  exit 1
fi

echo "[smoke_bd_cyclone] cmake → ${BUILD}"
cmake -B "${BUILD}" -S "${ROOT}" \
  -DGF_BUILD_TESTS=ON \
  -DGF_USE_GENERATED=OFF \
  -DGF_FORCE_NO_ICEORYX=ON \
  -DGF_SKU_CMAKE="${PROFILE}" \
  -DGF_DDS_BACKEND=cyclone

echo "[smoke_bd_cyclone] build gf_dds_binding_smoke (+ CycloneDDS) ..."
cmake --build "${BUILD}" -j"$(nproc)" --target gf_dds_binding_smoke

echo "[smoke_bd_cyclone] run ..."
OUT="$("${BUILD}/middleware/bindings/dds/gf_dds_binding_smoke")"
echo "${OUT}"
echo "${OUT}" | grep -q 'backend=cyclonedds'
echo "${OUT}" | grep -q 'OK'

echo "[smoke_bd_cyclone] OK (main SIL remains iceoryx; vsomeip stays stub)"
