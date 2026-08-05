#!/usr/bin/env bash
# Deprecated alias — use smoke_phm_dem_doip.sh
echo "[afc_with_uss] WARN: smoke_obs_demo.sh renamed → smoke_phm_dem_doip.sh" >&2
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke_phm_dem_doip.sh" "$@"
