#!/usr/bin/env bash
# Verify (not product path).
# O-track: multiproc SIL → session JSONL → tag → MCAP (+ optional foxglove describe)
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh
#   # or if already built:
#   GF_SKIP_COMPILE=1 bash scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

OUT_DIR="${GF_OBS_OUT:-${ROOT}/build/observability}"
LOG_DIR="${GF_BUILD_DIR:-${BUILD_SIL}}/iox_multiproc_logs"
mkdir -p "${OUT_DIR}"

if [[ "${GF_SKIP_COMPILE:-0}" != "1" ]]; then
  bash "${PROJECT_SCRIPTS}/compile_sil.sh"
fi

# Short multiproc for CI-ish runs
export GF_MP_TRAJ_COUNT="${GF_MP_TRAJ_COUNT:-8}"
export GF_PHM_FAULT_MS="${GF_PHM_FAULT_MS:-0}"
bash "${SCRIPT_DIR}/run_sil_multiproc.sh"

echo "${TAG} measure record from ${LOG_DIR} ..."
OBS_JSON="${PROJECT_DIR}/generated/observability.json"
if [[ -f "${OBS_JSON}" ]]; then
  GMT measure record --from-logs "${LOG_DIR}" --out "${OUT_DIR}/session.jsonl" \
    --observability "${OBS_JSON}"
else
  echo "${TAG} WARN: missing ${OBS_JSON}; record without whitelist (legacy)" >&2
  GMT measure record --from-logs "${LOG_DIR}" --out "${OUT_DIR}/session.jsonl"
fi

echo "${TAG} measure tag ..."
# Keep all events; label the run
GMT measure tag --in "${OUT_DIR}/session.jsonl" --out "${OUT_DIR}/session_tagged.jsonl" \
  --label "afc_multiproc_smoke"

echo "${TAG} measure export → MCAP ..."
GMT measure export --in "${OUT_DIR}/session_tagged.jsonl" --out "${OUT_DIR}/session.mcap"

python - <<PY
from pathlib import Path
from gf_gmt.measure_export import MAGIC, list_mcap_topics
p = Path("${OUT_DIR}/session.mcap")
b = p.read_bytes()
assert b.startswith(MAGIC) and b.endswith(MAGIC)
topics = list_mcap_topics(p)
assert topics, "expected ≥1 topic in MCAP"
print("topics:", topics)
PY

echo "${TAG} bridge foxglove describe ..."
GMT bridge foxglove --mcap "${OUT_DIR}/session.mcap"

echo "${TAG} observability OK → ${OUT_DIR}/"
ls -la "${OUT_DIR}/session.jsonl" "${OUT_DIR}/session_tagged.jsonl" "${OUT_DIR}/session.mcap"
