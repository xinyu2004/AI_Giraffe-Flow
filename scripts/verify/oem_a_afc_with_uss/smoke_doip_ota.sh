#!/usr/bin/env bash
# P3-4 smoke: DoIP session + UCM OTA + Collector fail path (SIL, no true flash).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BUILD="${GF_BUILD_DIR:-$ROOT/build}"
export PYTHONPATH="${ROOT}/tools/gmt/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -d "$BUILD" ]]; then
  echo "build dir missing: $BUILD (set GF_BUILD_DIR or cmake -B build)"
  exit 1
fi

cd "$ROOT"
ctest --test-dir "$BUILD" -R 'gf_diag_doip_smoke|gf_doip_session_smoke|gf_ucm_ota_smoke|gf_ucm_package_manager_smoke' --output-on-failure

SERVER="$(find "$BUILD" -maxdepth 4 -type f -name gf_doip_ota_server 2>/dev/null | head -n1 || true)"

if [[ -n "$SERVER" && -x "$SERVER" ]]; then
  PORT="${GF_DOIP_PORT:-13401}"
  export GF_DOIP_PORT="$PORT"
  "$SERVER" &
  spid=$!
  cleanup() { kill "$spid" 2>/dev/null || true; wait "$spid" 2>/dev/null || true; }
  trap cleanup EXIT
  sleep 0.4
  python3 - <<PY
from gf_gmt.doip_client import DoipClient
c = DoipClient()
c.connect("127.0.0.1", int("$PORT"))
c.routing_activation()
assert c.tester_present()[0] == 0x7E
r = c.start_ota("pkg.smoke", "/tmp/gf_smoke.swu")
assert r[0] == 0x71 and r[4] == 0x00, r.hex()
print("CASE DOIP-LIVE PASS server round-trip")
c.close()
PY
  cleanup
  trap - EXIT
fi

echo "smoke_doip_ota OK"
