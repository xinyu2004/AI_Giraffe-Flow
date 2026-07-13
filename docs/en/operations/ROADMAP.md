# Giraffe Flow roadmap (P0–P3)

> **中文:** [ROADMAP.md](../../zh/operations/ROADMAP.md)  
> Design: [DESIGN.md](../architecture/DESIGN.md)

**P0 closed (2026-07-13).** Next: pick a **P1** thread (bindings / GMT CLI / MCU sim). Details: Chinese [ROADMAP](../../zh/operations/ROADMAP.md) · [P0_PLAN](../../zh/operations/P0_PLAN.md).

## Summary

| Phase | Focus | Key exit criteria |
|-------|--------|-------------------|
| **P0** ✅ | Contract + minimal loop | SOR 0.2, gf-codegen, iceoryx SIL demo, `adc_full` compose, CI smoke |
| **P1** | Bindings, tools, ucm/diag stubs | SKU trim, GMT CLI, MCU gateway sim, exec/phm minimal |
| **P2** | Observability + evidence | MCAP/Tag/bench, Foxglove bridge, fault injection |
| **P3** | Embedded production + multi-arch | production cut-down, DoIP/OTA bench, MIPS/RISC-V OSAL |

## Next step

Start **P1** after local verify: `bash ci/scripts/smoke.sh` (or compose + `smoke_sil.sh`).
