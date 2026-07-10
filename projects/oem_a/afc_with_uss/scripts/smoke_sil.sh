#!/usr/bin/env bash
# SIL one-shot: compile_sil → run_sil
#
# Usage:
#   bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/compile_sil.sh"
bash "${SCRIPT_DIR}/run_sil.sh"
