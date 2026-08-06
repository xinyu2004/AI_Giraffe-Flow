#!/usr/bin/env bash
# Deprecated alias → verify smoke_sil (dual-process).
# Product path: projects/oem_a/afc_with_uss/scripts/{compile,run}_sil.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "WARN: deprecated scripts/run_ab_loop.sh → projects/oem_a/afc_with_uss/scripts/verify/smoke_sil.sh" >&2
exec bash "${ROOT}/projects/oem_a/afc_with_uss/scripts/verify/smoke_sil.sh" "$@"
