#!/usr/bin/env bash
# Copy SKU sample goldens onto a HIL-like runtime path. Does not edit gf-config.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLES_DIR="${GF_SAMPLES_DIR:-${SCRIPT_DIR}}"
STAGE_ROOT="${GF_STAGE_ROOT:-/tmp/gf_stage}"
INJECT_MODE="continuous"

usage() {
  echo "usage: $0 [--inject continuous|playhead|dut] [--stage-root DIR]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --inject) INJECT_MODE="${2:-}"; shift 2 ;;
    --stage-root) STAGE_ROOT="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

case "${INJECT_MODE}" in
  continuous|playhead|dut) ;;
  *) echo "unknown inject mode: ${INJECT_MODE}" >&2; exit 2 ;;
esac

SRC="${SAMPLES_DIR}/inject/${INJECT_MODE}"
if [[ ! -d "${SRC}" ]]; then
  echo "missing ${SRC}" >&2
  exit 2
fi

DST="${STAGE_ROOT}/inject/${INJECT_MODE}"
mkdir -p "${DST}"
# Prefer rsync if present; else cp -a
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "${SRC}/" "${DST}/"
else
  rm -rf "${DST}"
  mkdir -p "${DST}"
  cp -a "${SRC}/." "${DST}/"
fi

# Optional collector / dtc
for extra in collector dtc; do
  if [[ -d "${SAMPLES_DIR}/${extra}" ]]; then
    mkdir -p "${STAGE_ROOT}/${extra}"
    cp -a "${SAMPLES_DIR}/${extra}/." "${STAGE_ROOT}/${extra}/"
  fi
done

SESSION="${DST}/session.jsonl"
FRAMES="${DST}/frames"
echo "staged inject=${INJECT_MODE}"
echo "  session=${SESSION}"
[[ -d "${FRAMES}" ]] && echo "  frames=${FRAMES}"
echo "exports:"
echo "  export GF_SAMPLES_DIR=${SAMPLES_DIR}"
echo "  export GF_STAGE_ROOT=${STAGE_ROOT}"
if [[ -f "${SESSION}" ]]; then
  echo "  export GF_INJECT_SESSION=${SESSION}"
fi
if [[ -d "${FRAMES}" ]]; then
  echo "  export GF_INJECT_FRAMES_DIR=${FRAMES}"
fi
echo "  export GF_EGO_SOURCE=inject"
echo "  export GF_INJECT_MODE=$([[ ${INJECT_MODE} == continuous ]] && echo continuous || echo playhead)"
