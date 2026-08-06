#!/usr/bin/env bash
# Deprecated shim — SKU verify lives under the project tree.
echo "WARN: deprecated scripts/verify/oem_a_afc_with_uss/run_sil_live_foxglove.sh → projects/oem_a/afc_with_uss/scripts/verify/run_sil_live_foxglove.sh" >&2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "${ROOT}/projects/oem_a/afc_with_uss/scripts/verify/run_sil_live_foxglove.sh" "$@"
