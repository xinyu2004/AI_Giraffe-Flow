#!/usr/bin/env bash
# ROADMAP T4 / SG-05: production-release closes debug-path; FuSa main chain still runs.
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/smoke_production_profile.sh
#   GF_FUSA_T4_SKIP_COMPILE=1 …          # compose asserts only (fast)
#   GF_T4_BUILD_DIR=$PWD/build …         # default: reuse repo build/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

REQ="${PROJECT_DIR}/req.yaml"
BACKUP="${REQ}.t4.bak.$$"
# Reuse the normal SIL build tree (shares iceoryx / deps). Dedicated build-prod
# without GF_DEPS_PREFIX often fails fresh iceoryx configure.
PROD_BUILD="${GF_T4_BUILD_DIR:-${GF_BUILD_DIR:-${ROOT}/build}}"
SKIP_COMPILE="${GF_FUSA_T4_SKIP_COMPILE:-0}"
NEED_RESTORE_BUILD=0

restore() {
  local code=$?
  if [[ -f "${BACKUP}" ]]; then
    mv -f "${BACKUP}" "${REQ}"
    echo "${TAG} restored profile in ${REQ}; recomposing vehicle-debug ..."
    gf_prepare_codegen || true
    if [[ "${NEED_RESTORE_BUILD}" == "1" && "${code}" -eq 0 ]]; then
      echo "${TAG} recompile vehicle-debug apps into ${PROD_BUILD} ..."
      GF_BUILD_DIR="${PROD_BUILD}" bash "${PROJECT_DIR}/scripts/compile_sil.sh" || true
    fi
  fi
  exit "${code}"
}
trap restore EXIT INT TERM

cp -a "${REQ}" "${BACKUP}"
python - <<PY
from pathlib import Path
p = Path("${REQ}")
lines = []
for line in p.read_text().splitlines(True):
    if line.startswith("profile:"):
        lines.append("profile: production-release\n")
    else:
        lines.append(line)
p.write_text("".join(lines))
PY

echo "${TAG} compose production-release ..."
gf_prepare_codegen

python - <<PY
import json, pathlib, sys
d = json.loads(pathlib.Path("${GEN_OUT}/observability.json").read_text())
assert d.get("profile") == "production-release", d.get("profile")
live = d.get("live_tap") or {}
rec = d.get("record") or {}
assert live.get("enabled") is False, live
assert rec.get("mode") == "off", rec
cmake = pathlib.Path("${GEN_OUT}/gf_build.cmake").read_text()
assert 'GF_SKU_PROFILE "production-release"' in cmake
assert "set(GF_OBS_LIVE_TAP OFF)" in cmake
assert "iox_obs_tap" not in cmake and "iox_obs_inject" not in cmake
print("OK observability.json + gf_build.cmake (debug-path closed)")
PY

echo "${TAG} production compose asserts OK"

if [[ "${SKIP_COMPILE}" == "1" ]]; then
  echo "${TAG} SKIP compile (GF_FUSA_T4_SKIP_COMPILE=1)"
  echo "${TAG} smoke_production_profile OK (compose-only)"
  exit 0
fi

NEED_RESTORE_BUILD=1
echo "${TAG} compile_sil (production apps) → ${PROD_BUILD} ..."
GF_BUILD_DIR="${PROD_BUILD}" bash "${PROJECT_DIR}/scripts/compile_sil.sh"

# Prior vehicle-debug builds may leave stale tap/inject binaries; remove then prove
# production GF_APPS does not recreate them.
find "${PROD_BUILD}" -type f \( -name 'gf_iox_obs_tap' -o -name 'gf_iox_obs_inject' \) -delete 2>/dev/null || true
echo "${TAG} rebuild once more (should not recreate tap/inject) ..."
cmake --build "${PROD_BUILD}" -j"$(nproc)" >/dev/null

TAP="$(find "${PROD_BUILD}" -type f -name 'gf_iox_obs_tap' 2>/dev/null | head -n1 || true)"
INJ="$(find "${PROD_BUILD}" -type f -name 'gf_iox_obs_inject' 2>/dev/null | head -n1 || true)"
if [[ -n "${TAP}" || -n "${INJ}" ]]; then
  echo "${TAG} FAIL: debug-path binaries reappeared after production compile" >&2
  echo "  tap=${TAP:-none} inject=${INJ:-none}" >&2
  exit 1
fi
# Targets must not exist in the production CMake graph
if cmake --build "${PROD_BUILD}" --target gf_iox_obs_tap 2>/tmp/gf_t4_tap.err; then
  echo "${TAG} FAIL: gf_iox_obs_tap target still buildable" >&2
  exit 1
fi
if cmake --build "${PROD_BUILD}" --target gf_iox_obs_inject 2>/tmp/gf_t4_inj.err; then
  echo "${TAG} FAIL: gf_iox_obs_inject target still buildable" >&2
  exit 1
fi
echo "${TAG} OK: tap/inject not in production build graph"

echo "${TAG} SIL-02 multiproc on production build ..."
GF_BUILD_DIR="${PROD_BUILD}" GF_PHM_FAULT_MS=0 GF_MP_TRAJ_COUNT=8 \
  bash "${SCRIPT_DIR}/run_sil_multiproc.sh"

echo "${TAG} smoke_production_profile OK (debug-path closed + SIL-02 PASS)"
