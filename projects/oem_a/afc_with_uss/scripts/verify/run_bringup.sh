#!/usr/bin/env bash
# Deprecated alias → smoke_sil.sh (verify).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "WARN: deprecated run_bringup.sh → smoke_sil.sh" >&2
exec bash "${DIR}/smoke_sil.sh" "$@"
