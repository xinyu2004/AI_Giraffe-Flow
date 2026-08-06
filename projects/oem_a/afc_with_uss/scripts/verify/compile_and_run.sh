#!/usr/bin/env bash
# Deprecated alias → smoke_sil.sh (verify dual-process).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "WARN: deprecated compile_and_run.sh → smoke_sil.sh" >&2
exec bash "${DIR}/smoke_sil.sh" "$@"
