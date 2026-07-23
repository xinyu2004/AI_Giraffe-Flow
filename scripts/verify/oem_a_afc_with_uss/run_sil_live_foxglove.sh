#!/usr/bin/env bash
# Deprecated verify alias → product run_sil (live Foxglove when live_tap on).
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/run_sil_live_foxglove.sh
echo "note: run_sil_live_foxglove.sh → projects/.../scripts/run_sil.sh (product path)" >&2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "${ROOT}/projects/oem_a/afc_with_uss/scripts/run_sil.sh" "$@"
