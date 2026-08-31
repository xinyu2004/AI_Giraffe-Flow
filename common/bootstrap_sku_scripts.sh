#!/usr/bin/env bash
# Copy common/launch templates into a SKU scripts/ dir — only if the target is missing.
# After copy, the SKU owns the file; further edits must NOT be pushed back here.
#
# Usage (from repo root):
#   bash common/bootstrap_sku_scripts.sh afc
#   bash common/bootstrap_sku_scripts.sh afc
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKU_REL="${1:-}"
if [[ -z "${SKU_REL}" ]]; then
  echo "usage: bash common/bootstrap_sku_scripts.sh <oem>/<sku>" >&2
  exit 2
fi

SKU_DIR="${ROOT}/projects/${SKU_REL}"
DEST="${SKU_DIR}/scripts"
SRC="${ROOT}/common/launch"
if [[ ! -d "${SKU_DIR}" ]]; then
  echo "ERROR: SKU not found: ${SKU_DIR}" >&2
  exit 1
fi
mkdir -p "${DEST}"

# template → preferred SKU filename (first existing wins skip)
declare -A MAP=(
  [project_env.sh]="_common.sh"
  [compile.sh]="compile_sil.sh"
  [run.sh]="run_sil.sh"
  [gmt_depend.sh]="GMT_depend_launch.sh"
  [obs_inject.sh]="obs_inject.sh"
)

copied=0
skipped=0
for tmpl in project_env.sh compile.sh run.sh gmt_depend.sh obs_inject.sh; do
  src="${SRC}/${tmpl}"
  [[ -f "${src}" ]] || { echo "ERROR: missing template ${src}" >&2; exit 1; }
  dest_name="${MAP[${tmpl}]}"
  dest="${DEST}/${dest_name}"
  if [[ -e "${dest}" ]]; then
    echo "[bootstrap] skip (exists): ${dest_name}"
    skipped=$((skipped + 1))
    continue
  fi
  cp -a "${src}" "${dest}"
  # Soften template TAG if still placeholder
  if grep -q '__SKU_TAG__' "${dest}" 2>/dev/null; then
    sku_base="$(basename "${SKU_REL}")"
    sed -i "s/__SKU_TAG__/[${sku_base}]/g" "${dest}"
  fi
  echo "[bootstrap] copied → ${dest_name}"
  copied=$((copied + 1))
done

# Optional thin wrappers if missing
if [[ ! -e "${DEST}/compile_hil.sh" && -f "${DEST}/compile_sil.sh" ]]; then
  cat >"${DEST}/compile_hil.sh" <<'EOF'
#!/usr/bin/env bash
# Cross-compile entry — forked from compile_sil; edit freely (no link to common/).
set -euo pipefail
echo "TODO: implement compile_hil for this SKU (start from compile_sil.sh)" >&2
exit 1
EOF
  chmod +x "${DEST}/compile_hil.sh"
  echo "[bootstrap] stub → compile_hil.sh"
  copied=$((copied + 1))
fi
if [[ ! -e "${DEST}/run_hil.sh" ]]; then
  cat >"${DEST}/run_hil.sh" <<'EOF'
#!/usr/bin/env bash
# Board hint — product entry is systemd/init → gf_em_daemon (see common/deploy/).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="[sku]"
echo "${TAG} day-to-day: bash ${SCRIPT_DIR}/run_sil.sh"
echo "${TAG} on target: systemctl enable --now giraffe-em   # or init.d; runtime self-contained"
EOF
  chmod +x "${DEST}/run_hil.sh"
  echo "[bootstrap] stub → run_hil.sh"
  copied=$((copied + 1))
fi

echo "[bootstrap] done sku=${SKU_REL} copied=${copied} skipped=${skipped}"
