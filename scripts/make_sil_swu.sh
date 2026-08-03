#!/usr/bin/env bash
# Create a SIL-only fake .swu for GMT OTA / UCM (magic GFSW — not real RAUC).
# Usage:
#   bash scripts/make_sil_swu.sh
#   bash scripts/make_sil_swu.sh /tmp/gf_demo.swu "optional payload note"
set -euo pipefail
OUT="${1:-/tmp/gf_demo.swu}"
NOTE="${2:-Giraffe Flow SIL demo package}"
python3 - <<PY
from pathlib import Path
import struct, time
out = Path("$OUT")
note = "$NOTE".encode("utf-8")
# Header: GFSW | ver=1 | flags=0 | unix_ts | note_len | note | pad to >=64
hdr = b"GFSW" + struct.pack("<HHI", 1, 0, int(time.time()))
body = note + b"\n" + (b"\x00" * 48)
raw = hdr + struct.pack("<I", len(body)) + body
out.write_bytes(raw)
print(f"wrote {out} ({out.stat().st_size} bytes, magic=GFSW)")
PY
