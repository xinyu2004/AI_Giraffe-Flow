#!/usr/bin/env bash
# P2-G: refresh evidence_pack/p2_afc_with_uss (+ optional golden SOR).
#
# Usage (repo root):
#   bash scripts/collect_p2_evidence.sh
#   GF_EVIDENCE_RUN_SMOKE=1 bash scripts/collect_p2_evidence.sh   # also multiproc + observability
#   GF_EVIDENCE_UPDATE_GOLDEN=1 bash scripts/collect_p2_evidence.sh  # copy SOR → golden/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

PACK="${ROOT}/evidence_pack/p2_afc_with_uss"
PROJ="${ROOT}/projects/oem_a/afc_with_uss"
BUILD="${GF_BUILD_DIR:-${ROOT}/build}"
OBS="${GF_OBS_OUT:-${ROOT}/build/observability}"
LOG_DIR="${BUILD}/iox_multiproc_logs"
TAG="[collect_p2_evidence]"

mkdir -p "${PACK}"/{compose,lineage,mcap,logs,smoke}

echo "${TAG} compose ..."
python -m gf_codegen.compose --project "${PROJ}/project.yaml"
cp -f "${PROJ}/gf.sor.json" "${PACK}/compose/gf.sor.json"
cp -f "${PROJ}/reports/signal_lineage_report.yaml" "${PACK}/lineage/signal_lineage_report.yaml"

if [[ "${GF_EVIDENCE_UPDATE_GOLDEN:-0}" == "1" ]]; then
  mkdir -p "${PROJ}/golden"
  cp -f "${PROJ}/gf.sor.json" "${PROJ}/golden/gf.sor.json"
  echo "${TAG} golden ← ${PROJ}/golden/gf.sor.json"
fi

if [[ "${GF_EVIDENCE_RUN_SMOKE:-0}" == "1" ]]; then
  echo "${TAG} smoke_sil_multiproc ..."
  bash "${ROOT}/scripts/verify/oem_a_afc_with_uss/smoke_sil_multiproc.sh" | tee "${PACK}/smoke/multiproc.txt"
  echo "${TAG} smoke_sil_observability ..."
  GF_SKIP_COMPILE=1 bash "${ROOT}/scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh" | tee "${PACK}/smoke/observability.txt"
fi

if [[ -f "${OBS}/session.mcap" ]]; then
  cp -f "${OBS}/session.mcap" "${PACK}/mcap/session.mcap"
  [[ -f "${OBS}/session_tagged.jsonl" ]] && cp -f "${OBS}/session_tagged.jsonl" "${PACK}/mcap/session_tagged.jsonl" || true
fi

if [[ -d "${LOG_DIR}" ]]; then
  for f in gateway.log fcm.log uss.log planning.log; do
    [[ -f "${LOG_DIR}/${f}" ]] && cp -f "${LOG_DIR}/${f}" "${PACK}/logs/${f}" || true
  done
fi

GIT_REV="$(git -C "${ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  echo "# P2 AFC+USS Evidence Pack Manifest"
  echo
  echo "Generated: ${TS}  ·  git: ${GIT_REV}"
  echo
  echo "## Layout"
  echo
  echo "| Path | Status |"
  echo "|------|--------|"
  for rel in compose/gf.sor.json lineage/signal_lineage_report.yaml mcap/session.mcap \
             logs/gateway.log logs/fcm.log logs/uss.log logs/planning.log \
             smoke/multiproc.txt smoke/observability.txt; do
    if [[ -f "${PACK}/${rel}" ]]; then
      echo "| \`${rel}\` | present |"
    else
      echo "| \`${rel}\` | missing (re-run with GF_EVIDENCE_RUN_SMOKE=1 if needed) |"
    fi
  done
  echo
  echo "## How to refresh"
  echo
  echo '```bash'
  echo "GF_EVIDENCE_UPDATE_GOLDEN=1 GF_EVIDENCE_RUN_SMOKE=1 bash scripts/collect_p2_evidence.sh"
  echo '```'
  echo
  echo "## Related"
  echo
  echo "- Golden: \`projects/oem_a/afc_with_uss/golden/gf.sor.json\` (gitignored by default)"
  echo "- Review: [docs/zh/operations/P2_REVIEW_CHECKLIST.md](../../docs/zh/operations/P2_REVIEW_CHECKLIST.md)"
  echo "- Observability demo: [docs/zh/operations/OBSERVABILITY_DEMO.md](../../docs/zh/operations/OBSERVABILITY_DEMO.md)"
} > "${PACK}/MANIFEST.md"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "${PACK}" && find . -type f ! -name MANIFEST.md ! -name SHA256SUMS | sort | xargs -r sha256sum) > "${PACK}/SHA256SUMS"
fi

echo "${TAG} OK → ${PACK}/"
ls -la "${PACK}" "${PACK}"/* 2>/dev/null | head -60
