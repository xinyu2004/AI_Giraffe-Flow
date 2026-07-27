#!/usr/bin/env bash
# Verify: B2 module inject — only DUT (sensing.uss) + inject EgoMotion; no gateway/fcm/planning.
#
# Usage:
#   bash scripts/verify/oem_a_afc_with_uss/smoke_sil_inject_b2.sh
#   GF_SKIP_COMPILE=1 bash scripts/verify/oem_a_afc_with_uss/smoke_sil_inject_b2.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_verify_common.sh
source "${SCRIPT_DIR}/_verify_common.sh"

gf_project_env

OUT_DIR="${GF_OBS_OUT:-${ROOT}/build/observability}"
SESSION="${GF_INJECT_SESSION:-${OUT_DIR}/session_inject_ego_b2.jsonl}"
mkdir -p "${OUT_DIR}"

if [[ "${GF_SKIP_COMPILE:-0}" != "1" ]]; then
  bash "${PROJECT_SCRIPTS}/compile_sil.sh"
fi

INJ="${GF_BUILD_DIR:-${BUILD_SIL}}/apps/tools/iox_obs_inject/gf_iox_obs_inject"
if [[ ! -x "${INJ}" ]]; then
  echo "${TAG} ERROR: missing ${INJ} — vehicle-debug should compile tools/iox_obs_inject" >&2
  exit 1
fi

# Refresh default B2 session (distinct speeds from B1). Custom GF_INJECT_SESSION is kept.
if [[ -z "${GF_INJECT_SESSION:-}" ]]; then
  echo "${TAG} writing B2 EgoMotion session → ${SESSION}"
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
            "speed_mps": 7.0 + i * 0.05,
            "yaw_rate_degps": 0.1,
            "steer_angle_deg": 1.0,
            "gear": 4,
        },
    })
p.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")
print("events", len(rows))
PY
elif [[ ! -f "${SESSION}" ]]; then
  echo "${TAG} ERROR: GF_INJECT_SESSION not a file: ${SESSION}" >&2
  exit 1
fi

LOG_DIR="${GF_BUILD_DIR:-${BUILD_SIL}}/iox_sil_logs"
rm -f "${LOG_DIR}/fcm.log" "${LOG_DIR}/planning.log" "${LOG_DIR}/gateway.log" \
  "${LOG_DIR}/uss.log" "${LOG_DIR}/inject.log" 2>/dev/null || true

echo "${TAG} run_sil inject B2 (DUT=sensing.uss only) ..."
GF_SKIP_COMPILE=1 \
  GF_INJECT_SESSION="${SESSION}" \
  GF_INJECT_DUT=sensing.uss \
  bash "${PROJECT_SCRIPTS}/run_sil.sh"

if [[ ! -f "${LOG_DIR}/inject.log" ]]; then
  echo "${TAG} ERROR: missing inject.log" >&2
  exit 1
fi
if ! grep -q "sent_ego=" "${LOG_DIR}/inject.log"; then
  echo "${TAG} ERROR: inject did not report sent_ego" >&2
  cat "${LOG_DIR}/inject.log" >&2 || true
  exit 1
fi
if [[ ! -f "${LOG_DIR}/uss.log" ]]; then
  echo "${TAG} ERROR: missing uss.log (DUT should have run)" >&2
  exit 1
fi
# Distinct B2 speeds (7.x) should appear in uss output
if ! grep -qE "speed=7\." "${LOG_DIR}/uss.log"; then
  echo "${TAG} ERROR: uss did not log injected speed≈7.x" >&2
  tail -n 20 "${LOG_DIR}/uss.log" >&2 || true
  exit 1
fi
# Must not have started sibling apps
for unexpected in fcm.log planning.log gateway.log; do
  if [[ -f "${LOG_DIR}/${unexpected}" ]]; then
    echo "${TAG} ERROR: B2 should not create ${unexpected}" >&2
    exit 1
  fi
done

echo "${TAG} uss.log tail:"
tail -n 5 "${LOG_DIR}/uss.log" || true
echo "${TAG} inject B2 OK (DUT=sensing.uss)"
