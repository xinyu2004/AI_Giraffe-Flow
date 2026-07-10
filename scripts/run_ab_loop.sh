#!/usr/bin/env bash
# Deprecated alias — use project SIL smoke:
#   bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "note: scripts/run_ab_loop.sh → projects/oem_a/afc_with_uss/scripts/smoke_sil.sh" >&2
exec bash "${ROOT}/projects/oem_a/afc_with_uss/scripts/smoke_sil.sh" "$@"
