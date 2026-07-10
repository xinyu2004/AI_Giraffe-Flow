#!/usr/bin/env bash
# Deprecated alias — use smoke_sil.sh (avoid confusion with board bring-up).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "note: run_bringup.sh → smoke_sil.sh (SIL)" >&2
exec bash "${DIR}/smoke_sil.sh" "$@"
