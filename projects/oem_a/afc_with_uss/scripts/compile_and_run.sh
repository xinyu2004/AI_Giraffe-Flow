#!/usr/bin/env bash
# Deprecated alias — use smoke_sil.sh (SIL compile + run).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "note: compile_and_run.sh → smoke_sil.sh (SIL)" >&2
exec bash "${DIR}/smoke_sil.sh" "$@"
