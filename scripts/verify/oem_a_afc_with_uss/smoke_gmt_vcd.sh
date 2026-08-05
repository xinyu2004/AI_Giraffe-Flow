#!/usr/bin/env bash
# Verify: session JSONL → VCD (GTKWave path spike).
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/smoke_gmt_vcd.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

STUB="${ROOT}/tools/gmt/fixtures/session_stub.jsonl"
OUT_DIR="${GF_OBS_OUT:-$(gf_obs_dir)}"
OUT="${OUT_DIR}/session_stub.vcd"
mkdir -p "${OUT_DIR}"

echo "${TAG} GMT measure export --format vcd ..."
GMT measure export --format vcd --in "${STUB}" --out "${OUT}"

if [[ ! -f "${OUT}" ]]; then
  echo "${TAG} ERROR: missing ${OUT}" >&2
  exit 1
fi
grep -q '\$timescale 1 ns \$end' "${OUT}"
grep -q 'gf.EgoMotion.seq' "${OUT}"
grep -q '#1000000' "${OUT}"

echo "${TAG} VCD OK → ${OUT}"
if command -v gtkwave >/dev/null 2>&1; then
  echo "${TAG} open: gtkwave ${OUT}"
else
  echo "${TAG} (gtkwave not installed — file is ready for offline open)"
fi
