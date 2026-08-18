#!/usr/bin/env bash
# TEMPLATE: copy to SKU scripts/obs_inject.sh then fork.
# OBS live whitelist + inject B1/B2 helpers (host GMT). Not used by systemd/init EM.
# shellcheck shell=bash
#
# Expects from run.sh: TAG, PROJECT_DIR, INJECT_ON, and GF_* inject/obs env.

gf_obs_resolve_live_services() {
  local obs_json="${GF_OBS_JSON:-${PROJECT_DIR}/generated/observability.json}"
  if [[ ! -f "${obs_json}" ]]; then
    LIVE_SVCS=""
    export LIVE_SVCS
    return 0
  fi
  LIVE_SVCS="$(
    OBS_JSON="${obs_json}" python3 - <<'PY'
import json, os
p = os.environ["OBS_JSON"]
try:
    data = json.load(open(p, encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit(0)
live = data.get("live") or data.get("live_tap") or {}
if isinstance(live, dict):
    svcs = live.get("services") or live.get("allowlist") or []
elif isinstance(live, list):
    svcs = live
else:
    svcs = []
if isinstance(svcs, str):
    svcs = [s.strip() for s in svcs.split(",") if s.strip()]
print(",".join(svcs) if isinstance(svcs, list) else "")
PY
  )"
  export LIVE_SVCS
}

gf_inject_resolve_apps_services() {
  if [[ "${INJECT_ON:-0}" != "1" ]]; then
    return 0
  fi
  if [[ -n "${GF_INJECT_APPS:-}" ]]; then
    export RUN_APPS="${GF_INJECT_APPS}"
  fi
  if [[ -z "${GF_INJECT_SERVICES:-}" ]]; then
    export GF_INJECT_SERVICES="EgoMotion"
  fi
}
