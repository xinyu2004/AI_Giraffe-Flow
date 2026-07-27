#!/usr/bin/env bash
# Verify: B1 boundary inject — no gateway; EgoMotion from session → uss/planning.
#
# Prefers an existing session (from smoke_sil_observability). Builds a minimal
# EgoMotion-only session if missing.
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/smoke_sil_inject.sh
#   GF_SKIP_COMPILE=1 bash scripts/verify/oem_a_afc_with_uss/smoke_sil_inject.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

OUT_DIR="${GF_OBS_OUT:-${ROOT}/build/observability}"
SESSION="${GF_INJECT_SESSION:-${OUT_DIR}/session_inject_ego.jsonl}"
mkdir -p "${OUT_DIR}"

if [[ "${GF_SKIP_COMPILE:-0}" != "1" ]]; then
  bash "${PROJECT_SCRIPTS}/compile_sil.sh"
fi

INJ="${GF_BUILD_DIR:-${BUILD_SIL}}/apps/tools/iox_obs_inject/gf_iox_obs_inject"
if [[ ! -x "${INJ}" ]]; then
  echo "${TAG} ERROR: missing ${INJ} — vehicle-debug should compile tools/iox_obs_inject" >&2
  exit 1
fi

if [[ ! -f "${SESSION}" ]]; then
  echo "${TAG} writing minimal EgoMotion session → ${SESSION}"
  python - <<PY
import json
from pathlib import Path
p = Path("${SESSION}")
rows = []
t0 = 1_000_000_000
for i in range(20):
    rows.append({
        "t_ns": t0 + i * 100_000_000,
        "topic": "/gf/EgoMotion",
        "data": {
            "timestamp_ns": t0 + i * 100_000_000,
            "speed_mps": 5.0 + i * 0.05,
            "yaw_rate_degps": 0.1,
            "steer_angle_deg": 1.0,
            "gear": 4,
        },
    })
p.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")
print("events", len(rows))
PY
fi

echo "${TAG} run_sil inject B1 (no gateway) ..."
GF_SKIP_COMPILE=1 GF_INJECT_SESSION="${SESSION}" GF_INJECT_SERVICES=EgoMotion \
  bash "${PROJECT_SCRIPTS}/run_sil.sh"

LOG_DIR="${GF_BUILD_DIR:-${BUILD_SIL}}/iox_sil_logs"
if [[ ! -f "${LOG_DIR}/inject.log" ]]; then
  echo "${TAG} ERROR: missing inject.log" >&2
  exit 1
fi
if ! grep -q "sent_ego=" "${LOG_DIR}/inject.log"; then
  echo "${TAG} ERROR: inject did not report sent_ego" >&2
  cat "${LOG_DIR}/inject.log" >&2 || true
  exit 1
fi
# USS should have seen some motion if linked; soft-check
if [[ -f "${LOG_DIR}/uss.log" ]]; then
  echo "${TAG} uss.log tail:"
  tail -n 5 "${LOG_DIR}/uss.log" || true
fi

echo "${TAG} inject B1 OK"
