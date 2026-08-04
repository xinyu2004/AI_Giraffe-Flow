# Giraffe Measure Tool (GMT)

**中文:** [README_zh.md](README_zh.md)

Host-only: **architect CI**, **measure**, **Foxglove bridge**, **GMT GUI** (project → Live / Tag / replay / inject).

In multi-process SIL, terminal logs rarely answer “who published what, when.” GMT attaches the same tap stream to a host timeline and Foxglove: **scrub / speed** align DAG and variables, **playhead inject** drives Ego frame-by-frame (gateway off, no dual publish), then **Tag → MCAP** when you need a clip. Few ports, one `run_sil` companion—it **does not replace modules**; it makes them repeatedly verifiable.

| Entry | Role |
|-------|------|
| **`gf-config`** | Authoring GUI (tab 1 canvas = design-time graph) |
| `GMT architect lineage\|dag` | CI / export |
| `GMT measure record\|tag\|export\|import-ndjson` | Record, trim, MCAP/**VCD**, tap NDJSON import |
| `GMT bridge foxglove` | Studio live / JSONL (8765) |
| `GMT bridge live` | GMT GUI live WebSocket (8766) |
| **`GMT gui`** | Live / Tag / animated DAG / **Graphics** / **playhead inject** / **OTA/UDS (DoIP)** / export |

```bash
pip install -e tools/gmt -e tools/gf-codegen
pip install -e 'tools/gmt[gui]'

GMT gui
GMT gui --project projects/oem_a/afc_with_uss
GMT gui --project projects/oem_a/afc_with_uss/project.yaml
```

**Main path:** set **Host** → both top-bar channels may connect at once:

| Channel | Port | Protocol | Use |
|---------|------|----------|-----|
| **Live** | 8766 | WebSocket | live_tap observe; optional record to disk |
| **Inject** | 8767 | TCP | playhead (GMT windows / inject frames) |

- With “follow playhead inject”: **Live follow-latest is forced off**; Live can still observe/record  
- Inject result: top bar **green=published / red=skipped**, reason in status bar  
- Inject tab: event table; click row to seek; optional loop  
- **OTA/UDS tab** (shared DoIP + UDS log): radio **OTA / DEM / Collector** (config stays in gf-config)
  - **OTA**: Start OTA → `gf_doip_ota_server` (SIL; not real flash); compact module area so the UDS log sits under the button
  - **DEM**: `0x19` read DTCs · `0x14` clear (DEM-lite; not a Classic DEM editor)
  - **Collector**: local NDJSON or UDS `0x31 01 F201` dump of the on-target ring
- Graphics (CANoe-style): one row per signal; wheel / ± zoom; drag name-column edge for width; orange playhead  
- Wall clock: one `session_meta` anchor + `(t_ns - t0_ns)`  
- Without `project.yaml`: **inject disabled**; Live still works  

`GF_INJECT_LIVE=0` forces live_tap off during inject.

- **Connect Live:** WS into memory; **no disk by default**; “follow latest” controls tail stickiness  
- **Record:** top-bar button; default `session_live.jsonl` (prompt new/overwrite if non-empty)  
- Disconnect: stop record; keep in-memory session for scrub / Tag  
- Tag: `M` mark; `[` / `]` segment; `Ctrl+R` / `Ctrl+Shift+R` connect/disconnect  
- GMT **does not start SIL**  

Prerequisite: `gf-config` tab A `live_tap` on + `compile_sil` done.  
`run_sil` fans tap to Live (8766) and Foxglove (8765).

### Inject (playhead)

Full session stays in GMT; board inject holds A/B windows only. SIL may omit `GF_INJECT_SESSION`.

```bash
GF_INJECT_MODE=playhead \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# Scenario demo: GF_INJECT_LIVE=all (keep Ego → BEV)
```

GMT: open session → **Inject** → connect `host:8767` → “follow playhead” → scrub.

**continuous:** board reads a file. See [`iox_obs_inject`](../../apps/tools/iox_obs_inject/README.md).

```bash
GF_INJECT_SESSION=…/overtake_acc_aeb.jsonl \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

### ADAS scenario demo

Primary file `overtake_acc_aeb.jsonl` (lane change → ACC → AEB). Script frames enrich BEV Image only; Studio need not subscribe `/gf/AdasDemo`.

```bash
python scripts/gen_adas_scenarios.py
GMT bridge foxglove --ws --synth-bev \
  --jsonl projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl --port 8765

GMT gui --project projects/oem_a/afc_with_uss \
  --session projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl
```

### GTKWave (offline timing)

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_gmt_vcd.sh
# or: GMT measure export --format vcd --in …jsonl --out …vcd
```

CLI entry: **`GMT`**. GMT GUI **does not write wiring** (authoring stays in gf-config).

Parent: [tools/README.md](../README.md)
