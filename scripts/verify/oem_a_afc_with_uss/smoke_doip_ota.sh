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
ctest --test-dir "$BUILD" -R 'gf_diag_doip_smoke|gf_uds_nrc_smoke|gf_doip_session_smoke|gf_ucm_ota_smoke|gf_ucm_package_manager_smoke' --output-on-failure

SERVER="$(find "$BUILD" -maxdepth 4 -type f -name gf_doip_ota_server 2>/dev/null | head -n1 || true)"

if [[ -n "$SERVER" && -x "$SERVER" ]]; then
  PORT="${GF_DOIP_PORT:-13401}"
  export GF_DOIP_PORT="$PORT"
  export GF_OTA_TRANSFER_MODE="${GF_OTA_TRANSFER_MODE:-request_file_transfer}"
  export GF_OTA_REQUIRE_PROG_SESSION=1
  export GF_OTA_REQUIRE_SECURITY=1
  export GF_DIAG_S3_SERVER_MS=5000
  export GF_DIAG_TP_PERIOD_MS=2000
  "$SERVER" &
  spid=$!
  cleanup() { kill "$spid" 2>/dev/null || true; wait "$spid" 2>/dev/null || true; }
  trap cleanup EXIT
  sleep 0.4
  ART="/tmp/gf_smoke_ota.bin"
  python3 - <<'PY'
from pathlib import Path
p = Path("/tmp/gf_smoke_ota.bin")
p.write_bytes(b"GFSW\x01\x00" + b"smoke-ota-payload\n" + b"\x00" * 32)
print("artifact", p, p.stat().st_size)
PY
  python3 - <<PY
from gf_gmt.doip_client import DoipClient
c = DoipClient()
c.connect("127.0.0.1", int("$PORT"))
c.routing_activation()
assert c.tester_present()[0] == 0x7E
r = c.run_ota_sequence("pkg.smoke", "$ART", mode="request_file_transfer")
assert r and r[0] == 0x77, r.hex()
print("CASE DOIP-LIVE PASS 0x38→0x36→0x37")
c.close()
PY
  cleanup
  trap - EXIT
fi

echo "smoke_doip_ota OK"
