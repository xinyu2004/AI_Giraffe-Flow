#!/usr/bin/env bash
# Wrap CycloneDDS idlc when available; otherwise exit 0 with SKIP message.
# Usage: bash scripts/run_idlc.sh <file.idl> [out_dir]
set -euo pipefail

IDL="${1:?usage: run_idlc.sh <file.idl> [out_dir]}"
OUT="${2:-$(dirname "${IDL}")/idlc_out}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

IDLC=""
for cand in \
  "${GF_IDLC:-}" \
  "${ROOT}/middleware/.deps-prefix/bin/idlc" \
  "${ROOT}/middleware/third_party/cyclonedds/bin/idlc" \
  "$(command -v idlc 2>/dev/null || true)"; do
  if [[ -n "${cand}" && -x "${cand}" ]]; then
    IDLC="${cand}"
    break
  fi
done

if [[ -z "${IDLC}" ]]; then
  echo "[run_idlc] SKIP: idlc not found (install CycloneDDS / bootstrap later)"
  echo "[run_idlc] IDL kept at ${IDL}"
  exit 0
fi

mkdir -p "${OUT}"
echo "[run_idlc] ${IDLC} -l c -o ${OUT} ${IDL}"
"${IDLC}" -l c -o "${OUT}" "${IDL}"
echo "[run_idlc] OK → ${OUT}"
