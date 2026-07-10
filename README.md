# AI Giraffe Flow

**Lightweight SOA middleware + toolchain** — desktop first, **ARM Linux embedded** primary; MIPS / RISC-V reserved via OSAL.

**中文:** [README_zh.md](README_zh.md)

> Status: **architecture + directory skeleton** (incl. `ucm`/`diag` header stubs). **P0 code not started.**

[STRUCTURE.md](STRUCTURE.md) · [Roadmap P0–P3](docs/en/operations/ROADMAP.md) · [deps](deps/README.md)

---

## What this repo is

| Piece | Role |
|-------|------|
| **Runtime** | `gf_ara::*`, trimmable modules incl. **ucm** (OTA), **diag** (DoIP) |
| **Transports** | iceoryx, SOME/IP, DDS, cross_domain_ipc |
| **Contract** | **`gf.sor.json`** (SOR) |
| **gf-codegen** | `compose` → `lint` → `generate` |
| **GMT** | Giraffe Measure Tool — architect / measure / bridge |

Production perception/planning live in **external repos**; use `apps/simulators/` here.

---

## Ecosystem: roles → codegen → board → GMT

| Role | Owns | Does not own |
|------|------|--------------|
| Module engineer | `io_types.hpp` | DBC, wiring, SKU, JSON fragments |
| System integrator | `projects/<oem>/<vehicle>/` | Algorithm code |
| Platform / middleware | runtime, bindings, schemas | Per-vehicle deltas |
| DevOps | `req.yaml` acceptance, CI | Signal tables |

```text
four inputs + project.yaml → compose → gf.sor.json → lint/lineage → generate → build → onboard
Host loop: trace/MCAP → GMT / Foxglove → fix wiring → re-compose
```

Example: [projects/oem_demo/vehicle_demo/](projects/oem_demo/vehicle_demo/) · [WORKFLOW](docs/en/operations/WORKFLOW.md)

---

## Onboard vs host PC (full toolchain)

| Capability | Onboard | Host PC |
|------------|:-------:|:-------:|
| gf_ara runtime, bindings, adapters | ● | desktop profile for T0 |
| External app repos (perception/planning) | ● | cross-build |
| MCU (AUTOSAR CP, no gf) | ● optional | |
| gf-codegen (compose/lint/generate) | | ● (not in prod image) |
| GMT, Foxglove, MCAP replay | | ● |
| Cross-build, CI, SOR/wiring/DBC edit | | ● |
| lineage / golden diff gates | | ● |

Details: [DESIGN.md](docs/en/architecture/DESIGN.md) · expanded zh: [README_zh.md](README_zh.md)

---

## Roadmap

| Phase | Focus |
|-------|--------|
| **P0** | SOR, codegen, iceoryx demo, ARM OSAL — [ROADMAP](docs/en/operations/ROADMAP.md) |
| **P1** | Bindings, GMT, `compose --project`, ucm/diag stubs |
| **P2** | MCAP, evidence, Foxglove |
| **P3** | Production profile, DoIP/OTA bench, multi-arch OSAL |

**Next:** [P0 plan](docs/zh/operations/P0_PLAN.md) (zh, to be expanded)

---

## Repo map

[STRUCTURE.md](STRUCTURE.md) · [projects/](projects/)

## Docs

| Link | Content |
|------|---------|
| [DESIGN.md](docs/en/architecture/DESIGN.md) | Design |
| [sor-authoring.md](docs/en/architecture/sor-authoring.md) | SOR / four inputs |
| [ROADMAP.md](docs/en/operations/ROADMAP.md) | Phases |

## License

[LICENSE](LICENSE)
