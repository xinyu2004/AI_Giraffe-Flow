# frame_ingest / camera_slot / carla_scenarios roles

## Product path

```text
gf-config (Save → Verify → optional Generate) → compile_sil → runtime/{bin,lib} → run_sil → GMT
```

- **Frame source**: freeze SOP default `isp` (into `frame_ingest_config.hpp`); SIL overrides with **`GF_FRAME_SOURCE`**: `isp` / `carla` / `replay` / `colorbar` (legacy `synth`) / `none`. Orthogonal to `GF_INJECT_MODE` (ego/SOA inject). Secondary override: `GF_ACTIVE_SOURCE`.
- **ego_source**: `gateway` / `carla` / `inject` — same freeze; binaries read constexpr. **Do not** grep the hpp from `run_sil`.
- **`carla_scenarios/`**: independent Client A scenario machine — **zero** compose / stamp / runtime contract. Do not call frame-source selection a "scenario".
- **compile / run do not compose**: after camera_slots edits, **Verify** in gf-config; `compile_sil` / `run_sil` only build/run existing `generated/`.

## Syncing to carla_scenarios (camera contract)

gf-config does **not** push into the scenario machine. Compose emits a read-only contract; scenarios open it by path:

```text
gf-config Save/Verify
  → compose
  → projects/<sku>/generated/camera_contract.json   ← slots / WxH / pixel / mount
  → projects/<sku>/generated/include/gf_gen/frame_ingest_config.hpp  ← board/SIL behavior
```

Scenario side (`carla_scenarios/src/lib/_camera_mount.py`) — **contract only** (no local presets, no `GF_CAMERA_MOUNT_*` authoring):

1. **`GF_CAMERA_CONTRACT=/abs/path/camera_contract.json`**  
2. Else **`$GF_PROJECT_DIR/generated/camera_contract.json`**  
3. Else repo-relative `projects/oem_a/afc_no_uss/generated/camera_contract.json` if present  
4. Missing / incomplete → **hard exit** (no invented numbers)

No copy into `carla_scenarios/` — re-compose after camera_slots edits. SIL camera writer (`carla_bridge`) prefers ingest `GF_CAMERA_MOUNT_*` from hpp; falls back to the same `camera_contract.json`.

## Resident `gf_frame_ingest` (C++)

When the frame source is not `none`, compose freezes `host.frame_ingest` into `deploy_config.hpp` and **EM** starts it.

### Board vs host SIL (zero-Python policy)

| Environment | `gf_frame_ingest` | Python |
|-------------|-------------------|--------|
| **Board / onboard `runtime/`** | C++ only: Create GfChannel + ISP/V4L adapters | **Forbidden** (no interpreter, no `share/**/*.py`) |
| **Host SIL** | Create slots, then may spawn modules (`--module-only`) | Allowed: `carla` / `colorbar` / `replay` |

Policy (zh source of truth): [CONFIG_RUNTIME_POLICY.md](../../zh/operations/CONFIG_RUNTIME_POLICY.md) and backlog `BL-BOARD-NO-PY`. **Everything that ships with board `runtime/` / GMT onboard deps must stay Python-free** — not only the ISP source path.

SIL details:

- Freeze `kBridgeEnabled=false` or `kActiveSource=none` → **exit 0 immediately**
- Else Create GfChannel, spawn Python module (`--module-only`) — **SIL only**
- Shared lib at `runtime/lib/libgf_gf_channel.so` (RPATH / `LD_LIBRARY_PATH`)
- Stale staged `modules/carla_bridge` copies: see `BL-STAGE-PY-MTIME`

| Role | Owns | Does not |
|------|------|----------|
| **gf_frame_ingest (C++)** | Read hpp; Create slots; board adapters / SIL may spawn | World layout / ACC plot |
| **carla module (SIL only)** | Camera→YUV, ego, apply cmd | Spawn hero |
| **GfChannel** | shm image slots | ARA events |
| **FCM** | Open+Latest | Create |
| **carla_scenarios (host only)** | Client A place+IC | Camera write / compose |

## runtime = SIL root = HIL footprint estimate

```bash
du -sh projects/oem_a/afc_no_uss/build-sil/runtime
```

## compile stamp

`run_sil` still always calls `compile_sil`. Stamp match → `up-to-date` (skip compose/build/ctest/stage). Force: `GF_FORCE_COMPILE=1`.

## carla.env

| File | Reader |
|------|--------|
| SKU `carla.env` | `run_sil` only |
| `carla_scenarios/carla.env` | scenario machine **only** — SIL does not load it |

## Acceptance

- No script grep of `frame_ingest_config.hpp`
- Unchanged inputs → `compile_sil: up-to-date`
- `runtime/` has `bin/gf_frame_ingest` + `lib/libgf_gf_channel.so`
