#!/usr/bin/env bash
# Thin wrapper around run_sil. Preferred path: gf-config frame_ingest → compile → run_sil.sh
# This script only sets CARLA_HOST defaults for real-UE sessions.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_common.sh"
gf_project_env

export CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
export CARLA_PORT="${CARLA_PORT:-2000}"
echo "${TAG} run_carla_sil → run_sil (frame_ingest from frame_ingest_config.hpp)"
echo "${TAG} Prefer: gf-config「帧摄入」→ Verify → compile_sil → run_sil.sh"
echo "${TAG} Foxglove: ws://127.0.0.1:8765"

exec bash "${SCRIPT_DIR}/run_sil.sh"
