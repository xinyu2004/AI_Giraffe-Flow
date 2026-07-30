# Giraffe Flow roadmap (P0–P3)

> **中文（权威）:** [ROADMAP.md](../../zh/operations/ROADMAP.md)  
> Design: [DESIGN.md](../architecture/DESIGN.md)  
> Config: [MIDDLEWARE_CONFIG_PLAN.md](../../zh/operations/MIDDLEWARE_CONFIG_PLAN.md)

**P0–P2.5 closed** (desktop MVP: gf-config · multiproc SIL · GMT/Foxglove).  
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
| **P3-3 Cert-ready** | Certification-**ready support** (not certification) | trust-evidence docs, reproducible isolation scenarios, latency table, `production` profile |
| **P3-4 DoIP / OTA / GMT** | Diag & update ops | DoIP session, **GMT OTA sheet** via DoIP download path, UCM orchestration |
| **P3-5 Sim spike** | CARLA / Vision Pilot | CARLA→semantic adapter spike; VP feasibility; weak coupling to middleware |
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

1. **Two-tab gf-config ✅** · **wiring_all + codegen tap ✅**.  
2. Parallel: CARLA adapter spike · sm/phm/Collector **runtime**.  
3. Keep real board / real MCU off the critical path until P3z sprint.
