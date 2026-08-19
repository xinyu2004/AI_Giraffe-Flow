# Giraffe Flow roadmap (P0–P3)

> **中文（权威）:** [ROADMAP.md](../../zh/operations/ROADMAP.md)  
> Design: [DESIGN.md](../architecture/DESIGN.md)  
> Config: [MIDDLEWARE_CONFIG_PLAN.md](../../zh/operations/MIDDLEWARE_CONFIG_PLAN.md)

**P0–P2.5 closed** (desktop MVP: gf-config · main-chain SIL · GMT/Foxglove).  
**Current: P3 deepen & expand** — config/middleware/cert-ready support/DoIP·OTA first; real board & real MCU are a late sprint gate.

## Summary

| Phase | Focus | Status | Exit criteria |
|-------|--------|--------|----------------|
| **P0** | Contract + minimal loop | ✅ | SOR 0.2, gf-codegen, iceoryx SIL, `adc_full` compose, CI |
| **P1** | Bindings, tools, stubs | ✅ skeleton | gf-config v1, FIDL import, MCU desktop peer, exec/phm/ucm/diag stubs |
| **P2** | Runnable + observability | ✅ | Multiproc SIL, platform YAML, CycloneDDS path, Tag/MCAP, Foxglove |
| **P2.5** | Host tools + architect UI | ✅ | SIL compiler switch, GMT GUI, VCD |
| **P3** | Deepen & expand | **In progress** | See Chinese ROADMAP §P3 |

## P3 priorities (aligned with zh)

| Track | Theme | Key deliverables |
|-------|--------|------------------|
| **P3-1 Config** | gf-config as middleware configurator | **Two tabs ✅**: (1) Signal & apps (default) · (2) Platform runtime (+ `runtime_modules`); Collector min editor |
| **P3-2 Middleware** | AP depth | sm state machine, PHM Logical + SM link, **Event Collector** runtime, log lite, per/tsync skeleton |
| **P3-3 FuSa** | Functional Safety toward a **full Safety Case** | `fusa/` cases + runs/packs, [isolation](../../../fusa/metrics/isolation.md) / [latency](../../../fusa/metrics/latency.md) (+ `measure_latency.sh`), Safety Case skeleton; later: HARA / FSC / `production` profile |
| **P3-4 DoIP / OTA / GMT** | Diag & update ops | ✅ DoIP TCP · GMT **OTA/UDS** (OTA · DEM-lite · Collector on one sheet) · UCM · default **0x38** ([DOIP_OTA](../../zh/operations/DOIP_OTA.md); real RAUC → P3z) |
| **P3-5 Sim spike** | Perception SIL → CARLA camera | ✅ A–C + `frame_ingest` freeze (`run_sil` via gf-config); AM62/S2 last; VP dropped |
| **P3z Board / MCU** | Sprint gate (lowest urgency) | Optional thin smoke mid-phase; full `run_hil` / soak / real CP after desktop tracks OK |

## Event Collector (replaces “no DEM”)

| Topology | Adaptive (Giraffe) | Who owns debounce / state |
|----------|--------------------|---------------------------|
| MCU with Classic AUTOSAR CP | **Collector min-set** → forward to CP DEM | CP |
| No CP / DoIP-only | Collector + store/query + DoIP-readable DTC subset | AP **DEM-lite** (not full Classic DEM) |

Error **collection** is required either way. DoIP replaces the bus, not event management.

## Safety posture

We provide **certification-ready support** (reproducible evidence, clear module boundaries, config traceability).  
We do **not** sell / perform ISO 26262 certification or hold ASIL certificates for the customer.

## Next

1. **Product demo:** CARLA + Foxglove (fake perception → FCM passthrough → planning lite).
2. **Board zero-Python:** onboard `runtime/` (including **entire `frame_ingest`**, not only ISP) and any GMT/EM board deps must not require Python — zh backlog `BL-BOARD-NO-PY`. Python stays host-SIL only (`carla_bridge` / scenarios / gf-config / GMT PC).
3. Cloud CI + release; P3z / wave E (AM62 / board / vsomeip / RAUC / soak).

### Upload milestone memo (2026-08)

**One-liner:** author yaml → compose → hpp → binaries; SIL camera path via CARLA/Foxglove; **board payload policy = zero Python + no mutable behavior yaml** (policy locked; implementation tracked in backlog).

| Closed (say this) | Deferred |
|-------------------|----------|
| Config freeze → hpp; camera_slot / driving·parking topics | Implement `BL-BOARD-NO-PY` on board |
| Foxglove camera path + hero reattach (SIL) | Stage py mtime (`BL-STAGE-PY-MTIME`); cloud CI |
| Client A/B roles + camera contract docs | Fake-perception → planning demo depth |

Source of truth (zh): [CONFIG_RUNTIME_POLICY.md](../../zh/operations/CONFIG_RUNTIME_POLICY.md) · [AP_LITE_BACKLOG.md](../../zh/operations/AP_LITE_BACKLOG.md) · [frame_ingest_roles.md](../sku/afc_no_uss/frame_ingest_roles.md).

P3-4 desktop DoIP/OTA is closed — see Chinese [DOIP_OTA.md](../../zh/operations/DOIP_OTA.md).
**2026-08-04:** gf-config log-table UX + duplicate-context Verify; GMT Collector/DEM merged into the OTA/UDS tab.
**2026-08-06:** P3-5 A–C + `frame_ingest` — accept via gf-config → compose → `compile_sil` → `run_sil` (other projects to follow same policy).
