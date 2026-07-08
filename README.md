# AI Giraffe Flow

**Lightweight middleware + toolchain for cross-platform SOA systems** — desktop bring-up today, embedded vehicles tomorrow — without buying a full commercial AUTOSAR Adaptive stack.

**中文:** [README_zh.md](README_zh.md)

> Status: **architecture baseline** (docs first). Runtime and tools are not implemented yet.

---

## Why this exists

Teams building perception / planning / control / IVI need AP-like discipline (process lifecycle, health, SOA) and OEM intake (ARXML/DBC), but often cannot afford a heavy Adaptive Platform toolchain. They also need ROS 2 for algorithms, on-SoC zero-copy for sensors, and deep observability when pipelines misbehave.

**Giraffe Flow** is our answer: keep the useful AUTOSAR Adaptive *ideas*, ship a trim engineering platform, and own the model → codegen → review loop.

---

## What this repo is

One monorepo that will hold:

| Piece | Role |
|-------|------|
| **Runtime** | Exec / health / state + `gf_ara::com` (ARA-like API, own extensions under `gf::*`) |
| **Transports** | **iceoryx** (on-SoC), **SOME/IP** (vehicle SOA), **DDS** (ROS 2 / cross-SoC) |
| **SOR toolchain** | OEM ARXML/DBC → **`gf.sor.json`** (Statement of Requirements) → codegen |
| **Host tools** | DAG view, signal lineage review, GTKWave, record/replay |

**SOR (Statement of Requirements)** is the single contract for services, deployments, provide/require graphs, and OEM signal mappings. Codegen and architect tools all read the same SOR — diagrams and generated `::com` stay aligned.

---

## Who it helps

| You are… | You get… |
|----------|----------|
| **Platform / middleware eng** | Cross-OS/SoC portability via OSAL + HAL + binding plugins |
| **Architect / integrator** | DAG + signal review; OEM import without rewriting apps |
| **Perception / planning / control** | Stable service interfaces; OEM churn stays in adapter processes (e.g. radar) |
| **Algo / ROS users** | DDS path into the ROS ecosystem without dual stacks by hand |

Desktop-first debug, embedded-first ship: same SOR / manifests, profiles (`desktop` → `board` → `vehicle-debug` → `production`).

---

## Vision in one pass

```text
OEM ARXML/DBC ──► Importer ──► gf.sor.json ──► Codegen ──► gf_ara::com + manifests
                                   │
                    DAG / Signal Review (host)     apps: radar | perception | planning | control | IVI
                                   ▼
                    Runtime (EM/PHM) + iceoryx | SOME/IP | DDS
```

Key choices already aligned:

- Borrow AP concepts (**exec / phm / com / sm / log**); defer heavy safety/OTA clusters  
- **gf_ara::*** public API, **gf::*** internals  
- Services fine-grained; **processes by fault domain** (radar separate; IVI local or remote SoC)  
- Shared signals (e.g. vehicle speed) via one gateway, fan-out to subscribers  
- Monorepo for platform; customer vehicle projects stay out of this repo  

Details: [docs/en/architecture/DESIGN.md](docs/en/architecture/DESIGN.md) · flows: [docs/en/operations/WORKFLOW.md](docs/en/operations/WORKFLOW.md)

---

## Docs

| Link | Content |
|------|---------|
| [docs/en/README.md](docs/en/README.md) | English index |
| [docs/en/architecture/DESIGN.md](docs/en/architecture/DESIGN.md) | Design |
| [docs/en/operations/WORKFLOW.md](docs/en/operations/WORKFLOW.md) | Workflows |
| [README_zh.md](README_zh.md) / [docs/zh/](docs/zh/README.md) | Chinese |

---

## Roadmap (short)

0. Freeze SOR schema, SOA topology, deploy boundaries  
1. Triple-binding communication MVP  
2. Exec + health  
3. ROS + observability (DAG / GTKWave / record-replay)  
4. Embedded convergence + production profile  

## License

See [LICENSE](LICENSE).
