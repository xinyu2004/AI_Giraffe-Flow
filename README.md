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
| **gf-codegen** | `import` → `lint` → `generate` |
| **GMT** | Giraffe Measure Tool — architect / measure / bridge |

Production perception/planning live in **external repos**; use `apps/simulators/` here.

---

## Vision

```text
OEM → gf-codegen import → gf.sor.json → lint → generate → build → onboard
Host: GMT measure / bridge / architect
```

---

## Onboard vs host PC

| | Onboard | Host PC |
|---|---------|---------|
| Runtime, bindings, adapters, sim | yes | |
| AUTOSAR CP on MCU (no gf) | optional | |
| gf-codegen, GMT, Foxglove | | yes |

Details: [DESIGN.md](docs/en/architecture/DESIGN.md)

---

## Roadmap

| Phase | Focus |
|-------|--------|
| **P0** | SOR, codegen, iceoryx demo, ARM OSAL — [ROADMAP](docs/en/operations/ROADMAP.md) |
| **P1** | Bindings, GMT, ucm/diag stubs |
| **P2** | MCAP, evidence, Foxglove |
| **P3** | Production profile, DoIP/OTA bench, multi-arch OSAL |

**Next:** [P0 plan](docs/zh/operations/P0_PLAN.md) (zh, to be expanded)

---

## Repo map

[STRUCTURE.md](STRUCTURE.md)

## Docs

| Link | Content |
|------|---------|
| [DESIGN.md](docs/en/architecture/DESIGN.md) | Design |
| [ROADMAP.md](docs/en/operations/ROADMAP.md) | Phases |
| [THIRD_PARTY_EVALUATION.md](docs/en/dependencies/THIRD_PARTY_EVALUATION.md) | Dependencies |

## License

[LICENSE](LICENSE)
