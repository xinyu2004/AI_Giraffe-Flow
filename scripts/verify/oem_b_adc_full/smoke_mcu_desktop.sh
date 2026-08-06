#!/usr/bin/env bash
# Deprecated shim — SKU verify lives under the project tree.
echo "WARN: deprecated scripts/verify/oem_b_adc_full/smoke_mcu_desktop.sh → projects/oem_b/adc_full/scripts/verify/smoke_mcu_desktop.sh" >&2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "${ROOT}/projects/oem_b/adc_full/scripts/verify/smoke_mcu_desktop.sh" "$@"
