#!/usr/bin/env bash
# CD placeholder: package SIL tree paths for handoff (no cloud upload).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD="${GF_BUILD_DIR:-$ROOT/projects/oem_a/afc_with_uss/build-sil}"
OUT="${GF_CD_OUT:-$ROOT/devops/cd/out}"

echo "CD package_sil (stub)"
echo "  ROOT=$ROOT"
echo "  BUILD=$BUILD"
echo "  OUT=$OUT (not created by stub)"
echo "Next: copy selected binaries + platform yaml into OUT; no secrets."
exit 0
