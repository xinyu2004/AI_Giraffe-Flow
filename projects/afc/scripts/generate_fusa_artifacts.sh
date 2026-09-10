#!/usr/bin/env bash
# Generate FuSa evidence / artifacts for this SKU → fusa/packs/afc/.
# Does NOT call fusa/scripts/run_cases.sh (matrix runs separately; release gate does).
# If a recent cases_*.log / modules_*.log exists under fusa/runs/, copy it in.
#
# Usage (repo root or any cwd):
#   bash projects/afc/scripts/generate_fusa_artifacts.sh
#   GF_FUSA_PACK_RUN_SMOKE=1 bash …/generate_fusa_artifacts.sh
#   GF_FUSA_PACK_UPDATE_GOLDEN=1 bash …/generate_fusa_artifacts.sh
#   GF_FUSA_PACK_RELEASE=1 bash …/generate_fusa_artifacts.sh   # L3 发版证据包（校验必有物）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

PROJ="${ROOT}/projects/afc"
PACK="${ROOT}/fusa/packs/afc"
# shellcheck source=_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
OBS="${GF_OBS_OUT:-$(gf_obs_dir)}"
LOG_DIR="${BUILD}/runtime/logs"
TAG="[fusa_evidence]"
RELEASE="${GF_FUSA_PACK_RELEASE:-0}"

mkdir -p "${PACK}"/{compose,lineage,mcap,logs,smoke,runs,toolchain,release}

echo "${TAG} compose ..."
python -m gf_codegen.compose --project "${PROJ}/giraffe.yaml"
cp -f "${PROJ}/gf.sor.json" "${PACK}/compose/gf.sor.json"
cp -f "${PROJ}/reports/signal_lineage_report.yaml" "${PACK}/lineage/signal_lineage_report.yaml"

if [[ "${GF_FUSA_PACK_UPDATE_GOLDEN:-0}" == "1" ]]; then
  mkdir -p "${PROJ}/golden"
  cp -f "${PROJ}/gf.sor.json" "${PROJ}/golden/gf.sor.json"
  echo "${TAG} golden ← ${PROJ}/golden/gf.sor.json"
fi

if [[ "${GF_FUSA_PACK_RUN_SMOKE:-0}" == "1" ]]; then
  echo "${TAG} smoke_sil ..."
  bash "${ROOT}/projects/afc/scripts/verify/smoke_sil.sh" | tee "${PACK}/smoke/sil.txt"
  echo "${TAG} smoke_sil_observability ..."
  GF_SKIP_COMPILE=1 bash "${ROOT}/projects/afc/scripts/verify/smoke_sil_observability.sh" | tee "${PACK}/smoke/observability.txt"
fi

# Observability / toolchain outputs (from prior L0b/L3 smokes)
if [[ -f "${OBS}/session.mcap" ]]; then
  cp -f "${OBS}/session.mcap" "${PACK}/mcap/session.mcap"
  [[ -f "${OBS}/session_tagged.jsonl" ]] && cp -f "${OBS}/session_tagged.jsonl" "${PACK}/mcap/session_tagged.jsonl" || true
fi
for f in session_inject_ego.jsonl session_inject_ego_b2.jsonl session_stub.vcd session_tagged.jsonl; do
  [[ -f "${OBS}/${f}" ]] && cp -f "${OBS}/${f}" "${PACK}/toolchain/${f}" || true
done

if [[ -d "${LOG_DIR}" ]]; then
  for f in gateway.log fcm.log planning.log giraffe_modules.log; do
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

if [[ "${RELEASE}" == "1" ]]; then
  {
    echo "# Release FuSa evidence gate"
    echo
    echo "Generated: ${TS}  ·  git: ${GIT_REV}"
    echo
    echo "Produced by \`devops/ci/scripts/smoke_release.sh\` → \`GF_FUSA_PACK_RELEASE=1\`."
    echo
    echo "## Gate steps (expected before this pack)"
    echo
    echo "1. L0 \`smoke.sh\`"
    echo "2. Toolchain SIL: observability · inject · inject_b2 · gmt_vcd"
    echo "3. L1 cyclone + iox"
    echo "4. DoIP path (\`smoke_doip_ota.sh\` — no flash/SWU)"
    echo "5. FuSa T4 (\`GF_FUSA_T4=1 run_cases.sh\`)"
    echo "6. This evidence pack"
    echo
    echo "## Policy"
    echo
    echo "- Pack is **release evidence**, not an ASIL certificate claim."
    echo "- GMT observability/inject are toolchain/debug-path; packed for reproducibility."
    echo "- See [fusa/POLICY.md](../../../../fusa/POLICY.md) · [devops/ci/README.md](../../../../devops/ci/README.md)."
  } > "${PACK}/release/RELEASE_GATE.md"

  missing=0
  for req in \
    "${PACK}/compose/gf.sor.json" \
    "${PACK}/lineage/signal_lineage_report.yaml" \
    "${PACK}/mcap/session.mcap" \
    "${PACK}/runs/cases_latest.log" \
    "${PACK}/toolchain/session_stub.vcd"
  do
    if [[ ! -f "${req}" ]]; then
      echo "${TAG} ERROR: release evidence missing: ${req#"${PACK}/"}" >&2
      missing=1
    fi
  done
  if [[ "${missing}" -ne 0 ]]; then
    echo "${TAG} ERROR: GF_FUSA_PACK_RELEASE=1 requires toolchain + T4 outputs; re-run smoke_release.sh" >&2
    exit 1
  fi
  echo "${TAG} release evidence checks OK"
fi

{
  echo "# afc FuSa Evidence Manifest"
  echo
  echo "Generated: ${TS}  ·  git: ${GIT_REV}"
  if [[ "${RELEASE}" == "1" ]]; then
    echo "Mode: **release** (\`GF_FUSA_PACK_RELEASE=1\`)"
  else
    echo "Mode: local / optional pack"
  fi
  echo
  echo "## Layout"
  echo
  echo "| Path | Status |"
  echo "|------|--------|"
  for rel in compose/gf.sor.json lineage/signal_lineage_report.yaml mcap/session.mcap \
             logs/gateway.log logs/fcm.log logs/planning.log \
             smoke/sil.txt smoke/observability.txt runs/cases_latest.log \
             toolchain/session_stub.vcd toolchain/session_inject_ego.jsonl \
             release/RELEASE_GATE.md; do
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
  echo "# release (preferred):"
  echo "bash devops/ci/scripts/smoke_release.sh"
  echo "# or pack only after gate already green:"
  echo "GF_FUSA_PACK_RELEASE=1 bash projects/afc/scripts/generate_fusa_artifacts.sh"
  echo "# local optional smokes into pack:"
  echo "GF_FUSA_PACK_UPDATE_GOLDEN=1 GF_FUSA_PACK_RUN_SMOKE=1 \\"
  echo "  bash projects/afc/scripts/generate_fusa_artifacts.sh"
  echo '```'
  echo
  echo "## Related"
  echo
  echo "- FuSa entry: [fusa/README.md](../../../../fusa/README.md)"
  echo "- CI release: [devops/ci/README.md](../../../../devops/ci/README.md)"
  echo "- Golden: \`projects/afc/golden/gf.sor.json\` (gitignored by default)"
} > "${PACK}/MANIFEST.md"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "${PACK}" && find . -type f ! -name MANIFEST.md ! -name SHA256SUMS | sort | xargs -r sha256sum) > "${PACK}/SHA256SUMS"
fi

echo "${TAG} OK → ${PACK}/"
ls -la "${PACK}" "${PACK}"/* 2>/dev/null | head -80
