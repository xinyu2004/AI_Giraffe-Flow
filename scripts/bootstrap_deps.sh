#!/usr/bin/env bash
# Thin wrapper — installer lives next to the pin manifest.
# See dep-manifest/README.md
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT}/dep-manifest/bootstrap.sh" "$@"
