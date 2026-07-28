# gf-config (host configuration GUI)

**中文:** [README_zh.md](README_zh.md)

PySide6 tool: edit **SKU** via `req.yaml`, edit the **Simulink-like signal graph** via `wiring.yaml`, then one-shot `compose` + lineage.

> **Flow:** edit tabs A/B → **Ctrl+S Save** (disk only) → **Verify (Ctrl+R)** builds SOR + lineage → optional **Generate (Ctrl+G)** for Proxy/Skeleton.  
> Headless / CI: `python -m gf_codegen.compose --project …`; codegen remains `gf-codegen generate`.  
> Boundaries: `gf-config` = authoring GUI · `gf-codegen` = lint / generate / import · GMT = read-only CI + measure

## `req.yaml` vs `wiring.yaml`

| | **req.yaml** | **wiring.yaml** |
|--|--------------|-----------------|
| **In one line** | What this vehicle / SKU **needs, trims, and accepts** | How processes **connect** (who provides / requires) |
| **Who edits** | Tab A (product / integrator SKU) | Tab B (integrator signal graph) |
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
pip install -e "tools/codegen[dev]"
pip install -e tools/config
```

## Launch

```bash
gf-config projects/oem_a/afc_with_uss/project.yaml
```

## Tabs

| Tab | Role |
|-----|------|
| A · SKU / middleware | Full `req.yaml` (capabilities / observability / apps / acceptance) |
| B · Signal graph | Simulink-like canvas → `wiring.yaml`; **right pane Lineage** |

No separate C tab: Lineage lives on the right of B. Verify / Generate switches focus to Lineage.

**File menu:** Open · Save (Ctrl+S) · Save & Verify · Verify (Ctrl+R) · Generate (Ctrl+G) · Import hpp/fidl  

**View menu:** Fit (Ctrl+0) · Default zoom (Ctrl+H) · Reload (F5) · Lineage pane (Ctrl+L) · Delete edge (Delete)

Daily loop: edit A/B → **Save** → **Verify** → **Generate** when apps need rebuild.

## Tab B — four steps

| # | Action | Effect |
|---|--------|--------|
| 1 | **Right-click empty → Add module** | New process (`deployments[]`) |
| 2 | **Right-click module → Delete** | Drop deployment + related dataflows |
| 3 | **Double-click module** | Edit In/Out ports, direction, service names |
| 4 | **Drag Out → In** | Creates `dataflows`; Out name wins (In renamed if needed) |

Also: click edges (incl. missing dashed) to select; search box; import hpp / **fidl**; Ctrl+wheel zoom.

**FIDL import:** File → Import fidl… → pick struct / broadcast / method / interface ports → writes `wiring.modules[].fidl` and provides/requires (`gf_codegen.compose.parse_fidl`).  
**Export:** wiring/SOR → `.fidl` / `.fdepl` **not supported** yet (import first; full `.fdepl` needs SOME/IP ID model).

## Acceptance

- [x] Open `afc_with_uss` shows ported graph  
- [x] Add/remove nodes / drag edges / Save writes `wiring.yaml`  
- [x] Tab A req (incl. acceptance) round-trips  
- [x] Verify shows Lineage pass/fail  
- [x] CI does not require Qt  
