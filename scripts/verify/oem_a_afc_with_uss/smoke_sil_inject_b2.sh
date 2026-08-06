#!/usr/bin/env bash
# Deprecated shim — SKU verify lives under the project tree.
echo "WARN: deprecated scripts/verify/oem_a_afc_with_uss/smoke_sil_inject_b2.sh → projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_inject_b2.sh" >&2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "${ROOT}/projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_inject_b2.sh" "$@"
