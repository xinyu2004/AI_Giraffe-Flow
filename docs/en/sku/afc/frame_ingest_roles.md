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
3. Else repo-relative `projects/afc/generated/camera_contract.json` if present  
4. Missing / incomplete → **hard exit** (no invented numbers)

No copy into `carla_scenarios/` for authoring — compose writes `carla_scenarios/config/<product>/camera_contract.json`. SIL camera writer is **`gf_carla_io`** ← **`giraffe_client`** (not `tools/carla_bridge`).

## Resident `gf_frame_ingest` (C++)

When the frame source is not `none`, compose freezes `host.frame_ingest` into `deploy_config.hpp` and **EM** starts it.

### Board vs host SIL (zero-Python policy)

| Environment | `gf_frame_ingest` | Python |
|-------------|-------------------|--------|
| **Board / onboard `runtime/`** | C++ only: Create GfChannel + ISP/V4L adapters | **Forbidden** (no interpreter, no `share/**/*.py`) |
| **Host SIL** | Create slots, then **exec** C++ module (`gf_carla_io` / `gf_frame_replay` / `gf_frame_colorbar`) | **No** Python on this path |

Policy (zh source of truth): [CONFIG_RUNTIME_POLICY.md](../../zh/operations/CONFIG_RUNTIME_POLICY.md) and backlog `BL-BOARD-NO-PY`. **Everything that ships with board `runtime/` / GMT onboard deps must stay Python-free** — not only the ISP source path.

SIL details:

- Freeze `kBridgeEnabled=false` or `kActiveSource=none` → **exit 0 immediately**
- Else Create GfChannel, exec C++ module — **SIL `GF_FRAME_SOURCE`**
- Shared lib at `runtime/lib/libgf_channel.so` (RPATH / `LD_LIBRARY_PATH`)

| Role | Owns | Does not |
|------|------|----------|
| **gf_frame_ingest (C++)** | Read hpp; Create slots; board adapters / SIL may spawn | World layout / ACC plot |
| **gf_carla_io + giraffe_client (SIL)** | Camera/truth TCP ↔ GfChannel; apply cmd | Spawn hero (that's `scenario_client`) |
| **GfChannel** | shm image slots | ARA events |
| **FCM** | Open+Latest | Create |
| **carla_scenarios (host only)** | Client A place+IC | Camera write / compose |

## runtime = SIL root = HIL footprint estimate

```bash
du -sh projects/afc/build-sil/runtime
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
