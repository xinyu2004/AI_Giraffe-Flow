# gf-config (host configuration GUI)

**中文:** [README_zh.md](README_zh.md)

PySide6 tool: edit **SKU** via `req.yaml`, edit the **Simulink-like signal graph** via `wiring.yaml`, then one-shot `compose` + lineage.

> **Flow:** edit tabs 1/2 → **Ctrl+S Save** (disk only) → **Verify (Ctrl+R)** builds SOR + lineage → optional **Generate (Ctrl+G)** for Proxy/Skeleton.  
> Headless / CI: `python -m gf_codegen.compose --project …`; codegen remains `gf-codegen generate`.  
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
gf-config projects/oem_a/afc_with_uss/project.yaml
```

## Tabs (P3 · two pages)

| Tab | Role |
|-----|------|
| **1 · Signals & apps** (default) | **Left thin SKU open**; canvas; **right Lineage collapsed** (◀ to expand) |
| **2 · Platform runtime** | Top `runtime_modules` (incl. trimable **per / tsync**); subpages: exec/FG · **EM launch map** · PHM · diag · **log** · OTA · **Event collector** · **Memory bounds** |

Shortcuts: Ctrl+1 / Ctrl+2. Verify / Generate returns to tab 1 Lineage.  
**Edit menu:** Undo / Redo (Ctrl+Z / Ctrl+Y) — jumps to the changed page (incl. platform subpages); status-bar tip is i18n’d.

**File menu:** Open · Save (Ctrl+S) · Save & Verify · Verify (Ctrl+R) · Generate (Ctrl+G) · Import hpp/fidl  

**View menu:** Fit (Ctrl+0) · Default zoom (Ctrl+H) · Reload (F5) · Lineage pane (Ctrl+L) · Delete edge (Delete)

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

- [x] Open `afc_with_uss` shows ported graph  
- [x] Add/remove nodes / drag edges / Save writes `wiring.yaml`  
- [x] Tab 1 thin SKU + tab 2 runtime_modules / platform round-trip  
- [x] Tab 2 **EM launch map** edits `platform/em_launch.yaml` (unlocked by `exec`)  
- [x] Verify shows Lineage pass/fail (incl. `platform_em_launch`)  
- [x] Log table: row-number select + duplicate context id fails Verify  
- [x] Undo/Redo navigates to the changed page (incl. platform subpages)  
- [x] CI does not require Qt  

## Tab 2 ↔ board modules (afc_with_uss)

| `runtime_modules` | Subpage / YAML | On board |
| `core` / `com` / `osal` | (greyed, required) | CMake always-on, not trimable |
|-------------------|----------------|----------|
| `exec` (+`sm`) | Exec/FG · `exec.yaml` | FG + dependency topo |
| `exec` | EM launch · `em_launch.yaml` | `gf_em_daemon` OSAL Spawn |
| `phm` | Health · `phm.yaml` | Alive; `restart` → EM |
| `collector` / phm / diag | Event collector · `collector.yaml` | ring / cp_dem stub |
| `diag` / `log` / `ucm` | respective pages | DoIP·UDS / log / OTA orchestrator (SIL; flash still stub) |
| `per` / `tsync` | (no subpage yet) | checkbox → compile into image (KV / time-sync skeleton) |
