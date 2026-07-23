#!/usr/bin/env bash
# Deprecated alias → verify smoke_sil (dual-process).
# Product path: projects/oem_a/afc_with_uss/scripts/{compile,run}_sil.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "note: scripts/run_ab_loop.sh → scripts/verify/oem_a_afc_with_uss/smoke_sil.sh" >&2
exec bash "${ROOT}/scripts/verify/oem_a_afc_with_uss/smoke_sil.sh" "$@"
