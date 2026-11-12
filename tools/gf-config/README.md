# gf-config (host configuration GUI)

**中文:** [README_zh.md](README_zh.md)

PySide6 tool: edit **SKU** via `cfg/req.yaml`, **Simulink-like graph** via `cfg/wiring.yaml`, tab 2 via `cfg/gf_ara_cfg/*`, then Verify (`compose`) + lineage.

> **Flow:** edit tabs 1/2 → **Ctrl+S Save** (disk only) → **Verify (Ctrl+R)** builds SOR + lineage + `generated/*.hpp` (behavior freeze) → optional **Generate (Ctrl+G)** for Proxy/Skeleton.  
> **Authoring ends there.** Then `compile_sil` / `run_sil` (**no** auto-compose).  
> Headless / CI: `python -m gf_codegen.compose --project projects/afc/giraffe.yaml`.  
> Layout: [projects/CFG_LAYOUT.md](../../projects/CFG_LAYOUT.md) · entry file is **`giraffe.yaml`** (was `project.yaml`).  
> Boundaries: `gf-config` = authoring GUI · `gf-codegen` = lint / generate / import · GMT = read-only CI + measure

## `req.yaml` vs `wiring.yaml`

| | **req.yaml** | **wiring.yaml** |
|--|--------------|-----------------|
| **In one line** | What this vehicle / SKU **needs, trims, and accepts** | How processes **connect** (who provides / requires) |
| **Who edits** | Tab 1 thin SKU + tab 2 `runtime_modules` | Tab 1 canvas |
| **Typical content** | `variant` / `topology` / `product` · `capabilities` · `runtime_modules` · `bindings` · `observability` · `apps` · `acceptance` | `modules` (hpp) · `deployments` (provides/requires) · `dataflows` · `bindings` (module IO) |
| **Pipeline** | `merge_req` → SOR product variants + lineage gates | `apply_wiring` → SOR deployments / dataflows / types |
| **Does not own** | Concrete from→to edges | Whether com/phm is compiled in (SKU trim) |

```text
req.yaml (SKU contract) ──┐
                          ├── gf-config save → compose → gf.sor.json → Generate / lineage
wiring.yaml (wiring)    ──┘
```

**Mnemonic:** req = *what / how much*; wiring = *who talks to whom*.

## Install

```bash
cd /path/to/AI_Giraffe-Flow
source .venv/bin/activate
pip install -e "tools/gf-codegen[dev]"
pip install -e tools/gf-config
```

## Launch

```bash
gf-config projects/afc/giraffe.yaml
```

## Tabs (P3 · two pages)

| Tab | Role |
|-----|------|
| **1 · Signals & apps** (default) | **Left thin SKU open**; canvas; **right Lineage collapsed** (◀ to expand) |
| **2 · Platform config** | Top `runtime_modules` (incl. trimable **per / tsync**); subpages: exec/FG · **EM launch map** · PHM · diag · **log** · OTA · **Event collector** · **Time / gates** · **Memory bounds** |

### Tab 2 · TSN (`tsync.yaml`)

Entry: check **tsync**, then open **Time / gates**. Walkthrough: [docs/zh/tsn/index.html](../../docs/zh/tsn/index.html) (open in a browser; the page is in Chinese and follows the timeline).

- An untouched project does not grow a `network` key. Save writes it only after this page is edited.
- **Gate list** (`gate_list`): each row is `interval_us` plus `gate_states`. The sum must equal `cycle_us`. A short list would keep the last row's gates until the cycle ends; a long list would not run the tail. Verify rejects both (`platform_tsync_network`), and the nav stays marked.
- **Preemption** (`preemptable_mask`) and **per-queue max frame** (`max_sdu`) stay omitted at the default. They are intent, and are not applied to the NIC.
- **Stream filter and policing** (`stream_filters`, `flow_meters`) are 802.1Qci intent for the adjacent switch ingress: match a PCP, limit the frame, then a CIR/CBS token bucket. Giraffe does not execute them. Empty tables are omitted.
- Access and trunk — which frame is tagged on the way in and on the way out — are not fields on this page.
- The runtime parser still reads only `backend` and `pretend_synchronized`. CNC and AVTP are not pages.

Switch tabs via the tab bar. Verify / Generate returns to tab 1 Lineage.  
**Edit menu:** Undo / Redo (Ctrl+Z / Ctrl+Y) — jumps to the changed page (incl. platform subpages); status-bar hint is i18n’d.

**File menu:** Open · Save (Ctrl+S) · Save & Verify · Verify (Ctrl+R) · Generate (Ctrl+G) · Import hpp/fidl  

**View menu:** Fit (Ctrl+0) · Default zoom (Ctrl+H) · Reload (F5) · Lineage pane (Ctrl+L) · Delete selection (Del/Backspace on graph)

Daily: tab 1 graph / thin SKU → tab 2 modules → **Save** → **Verify** → **Generate** when needed.

### Tab 2 · Logging (`log.yaml`)

- **Default level** + **sinks** (`console` / `file` / `dlt`) + **DLT app_id** + **`file_max_bytes`** + per-module **contexts[]**.
- Check **dlt** → SIL/HIL starts `dlt-daemon` from config (no env kill-switch).
- New row: module may be empty; level defaults to `INFO` (enum tint kept).
- Verify fails on duplicate `context id` in `log.yaml`.

### Tab 2 · Memory bounds (`bounds.yaml` · BL-MEM-BOUND / BL-MEM-ROUDI)

- Cross-module caps: DLT · LoopbackBus · per · DoIP · DID · optional budget.
- **iceoryx / RouDi**: `mgmt` (→ `IOX_MAX_*`, rebuild iceoryx after change) + `mempools` (→ `generated/iox_roudi.toml`).
- SIL starts RouDi when `req.bindings` includes iceoryx (config-driven).
- Read-only estimate includes RAM/DISK/SHM formula lines (`gf_codegen.compose.mem_budget`).

## Tab 1 canvas — four steps

| # | Action | Effect |
|---|--------|--------|
| 1 | **Right-click empty → Add module** | New process (`deployments[]`) |
| 2 | **Right-click module → Delete** | Drop deployment + related dataflows |
| 3 | **Double-click module** | Edit In/Out ports, direction, service names |
| 4 | **Drag Out↔In** | Creates `dataflows` (either side can start); Out name wins (In renamed if needed) |
| — | **Ctrl+drag port** | Move port to another card edge (top/bottom/left/right); bare drag = wire |

Also: click edges (incl. missing dashed) to select; search box; import hpp / **fidl**; Ctrl+wheel zoom.

**FIDL import:** File → Import fidl… → pick struct / broadcast / method / interface ports → writes `wiring.modules[].fidl` and provides/requires (`gf_codegen.compose.parse_fidl`).  
**Export:** wiring/SOR → `.fidl` / `.fdepl` **not supported** yet (import first; full `.fdepl` needs SOME/IP ID model).

## Acceptance

- [x] Open `afc` shows ported graph  
- [x] Add/remove nodes / drag edges / Save writes `wiring.yaml`  
- [x] Tab 1 thin SKU + tab 2 runtime_modules / platform round-trip  
- [x] Tab 2 **EM launch map** edits `cfg/gf_ara_cfg/em_launch.yaml` (unlocked by `exec`)  
- [x] Verify shows Lineage pass/fail (incl. `platform_em_launch`)  
- [x] Log table: row-number select + duplicate context id fails Verify  
- [x] Undo/Redo navigates to the changed page (incl. platform subpages)  
- [x] CI does not require Qt  

## Tab 2 ↔ board modules (afc)

| `runtime_modules` | Subpage / YAML | On board |
| `core` / `com` / `osal` | (greyed, required) | CMake always-on, not trimable |
|-------------------|----------------|----------|
| `exec` (+`sm`) | Exec/FG · `exec.yaml` | FG + dependency topo |
| `exec` | EM launch · `em_launch.yaml` | `gf_em_daemon` OSAL Spawn |
| `phm` | Health · `phm.yaml` | Alive; `restart` → EM |
| `collector` / phm / diag | Event collector · `collector.yaml` | ring / cp_dem stub |
| `diag` / `log` / `ucm` | respective pages | DoIP·UDS / log / OTA orchestrator (SIL; flash still stub) |
| `per` | (no subpage yet) | checkbox → compile into image (KV) |
| `tsync` | Time / gates · `tsync.yaml` | gate list, preemption, max frame size, stream filters, and flow meters are written only after edit; a cycle or stream-filter mismatch stays marked on the nav |
