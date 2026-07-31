#!/usr/bin/env bash
# Generate FuSa artifacts for this SKU → fusa/packs/oem_a_afc_with_uss/.
# Does NOT call fusa/scripts/run_cases.sh (matrix runs separately).
# If a recent cases_*.log / modules_*.log exists under fusa/runs/, copy it in.
#
# Usage (repo root or any cwd):
#   bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
#   GF_FUSA_PACK_RUN_SMOKE=1 bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
#   GF_FUSA_PACK_UPDATE_GOLDEN=1 bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

PROJ="${ROOT}/projects/oem_a/afc_with_uss"
PACK="${ROOT}/fusa/packs/oem_a_afc_with_uss"
BUILD="${GF_BUILD_DIR:-${ROOT}/build}"
OBS="${GF_OBS_OUT:-${ROOT}/build/observability}"
LOG_DIR="${BUILD}/iox_multiproc_logs"
TAG="[fusa_artifacts]"

mkdir -p "${PACK}"/{compose,lineage,mcap,logs,smoke,runs}

echo "${TAG} compose ..."
python -m gf_codegen.compose --project "${PROJ}/project.yaml"
cp -f "${PROJ}/gf.sor.json" "${PACK}/compose/gf.sor.json"
cp -f "${PROJ}/reports/signal_lineage_report.yaml" "${PACK}/lineage/signal_lineage_report.yaml"

if [[ "${GF_FUSA_PACK_UPDATE_GOLDEN:-0}" == "1" ]]; then
  mkdir -p "${PROJ}/golden"
  cp -f "${PROJ}/gf.sor.json" "${PROJ}/golden/gf.sor.json"
  echo "${TAG} golden ← ${PROJ}/golden/gf.sor.json"
fi

if [[ "${GF_FUSA_PACK_RUN_SMOKE:-0}" == "1" ]]; then
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

# Optional: attach latest matrix log if present (does not invoke run_cases)
LATEST_CASES=""
if [[ -d "${ROOT}/fusa/runs" ]]; then
  LATEST_CASES="$(ls -1t "${ROOT}/fusa/runs"/cases_*.log "${ROOT}/fusa/runs"/modules_*.log 2>/dev/null | head -n1 || true)"
fi
if [[ -n "${LATEST_CASES}" && -f "${LATEST_CASES}" ]]; then
  cp -f "${LATEST_CASES}" "${PACK}/runs/cases_latest.log"
  echo "${TAG} attached ${LATEST_CASES##*/} → packs/.../runs/cases_latest.log"
fi

GIT_REV="$(git -C "${ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  echo "# oem_a / afc_with_uss FuSa Artifacts Manifest"
  echo
  echo "Generated: ${TS}  ·  git: ${GIT_REV}"
  echo
  echo "## Layout"
  echo
  echo "| Path | Status |"
  echo "|------|--------|"
  for rel in compose/gf.sor.json lineage/signal_lineage_report.yaml mcap/session.mcap \
             logs/gateway.log logs/fcm.log logs/uss.log logs/planning.log \
             smoke/multiproc.txt smoke/observability.txt runs/cases_latest.log; do
    if [[ -f "${PACK}/${rel}" ]]; then
      echo "| \`${rel}\` | present |"
    else
      echo "| \`${rel}\` | missing |"
    fi
  done
  echo
  echo "## How to refresh"
  echo
  echo '```bash'
  echo "# matrix (optional, separate):"
  echo "bash fusa/scripts/run_cases.sh"
  echo "# this SKU pack:"
  echo "GF_FUSA_PACK_UPDATE_GOLDEN=1 GF_FUSA_PACK_RUN_SMOKE=1 \\"
  echo "  bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh"
  echo '```'
  echo
  echo "## Related"
  echo
  echo "- FuSa entry: [fusa/README.md](../../../../fusa/README.md)"
  echo "- Golden: \`projects/oem_a/afc_with_uss/golden/gf.sor.json\` (gitignored by default)"
  echo "- Review: [docs/zh/operations/P2_REVIEW_CHECKLIST.md](../../../../docs/zh/operations/P2_REVIEW_CHECKLIST.md)"
} > "${PACK}/MANIFEST.md"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "${PACK}" && find . -type f ! -name MANIFEST.md ! -name SHA256SUMS | sort | xargs -r sha256sum) > "${PACK}/SHA256SUMS"
fi

echo "${TAG} OK → ${PACK}/"
ls -la "${PACK}" "${PACK}"/* 2>/dev/null | head -60
