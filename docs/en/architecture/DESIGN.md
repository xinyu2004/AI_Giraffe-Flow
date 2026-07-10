# Giraffe Flow Design Document

> Document version: 0.1 (architecture baseline)  
> Status: for review; large-scale implementation has not started  
> **中文:** [DESIGN.md](../../zh/architecture/DESIGN.md)  
> Companion workflow: [WORKFLOW.md](../operations/WORKFLOW.md)

---

## 1. Vision and positioning

Giraffe Flow is a **lightweight cross-platform platform stack** targeting:

- Embedded boards (primary deployment goal)
- Desktop Linux (early bring-up, simulation, host tooling)

It borrows ideas from the AUTOSAR Adaptive Platform (AP):

- Process / execution management
- Platform health management
- SOA communication (Proxy / Skeleton, service discovery)

…and deliberately strengthens areas that are expensive or weak in typical AP ecosystems:

- Affordable **model-driven codegen** (ARXML/DBC → SOR → generate)
- Architect-friendly **DAG + signal lineage review**
- **GTKWave**-class timing plus long-horizon **Record/Replay**
- **OpenVX** cross-core pipeline observability
- **ROS 2** interop (DDS)
- Trimmed, portable deployment (not a full AP 14+ daemon stack)

Phased delivery: **[ROADMAP.md](../operations/ROADMAP.md)** (P0–P3).

Embedded **ARM Linux** primary; **MIPS / RISC-V** via `platform/osal/arch/`. See [portability-hal.md](portability-hal.md).

More detail in the Chinese DESIGN (§6–§10) until full EN sync.

---

## 2. Relationship to AUTOSAR AP

We **borrow concepts; we do not clone the full stack**. API semantics stay close to ARA, but namespaces use `gf_ara::*` so we are not pretending to be a certified `ara::*` product.

### 2.1 AP functional clusters (baseline: R24-11 / R25-11)

| FC | Namespace | Role |
|----|-----------|------|
| Core Types | `ara::core` | Result / ErrorCode / Future |
| Communication | `ara::com` | SOA Method / Event / Field; bindings may include SOME/IP, DDS, IPC |
| Execution | `ara::exec` | Process lifecycle, function groups, resource groups |
| Health | `ara::phm` | Alive / Deadline / Logical supervision |
| State | `ara::sm` | Machine / function-group state, degradation |
| Log | `ara::log` | Logging and trace (DLT) |
| Persistency | `ara::per` | KV / file persistency |
| Diagnostics | `ara::diag` | UDS / DoIP / SOVD |
| Crypto | `ara::crypto` | Crypto and certificates |
| IAM | `ara::iam` | Access control |
| IDSM | `ara::idsm` | Intrusion detection |
| NM | `ara::nm` | Network management |
| Time Sync | `ara::tsync` | gPTP, etc. |
| UCM / V-UCM | `ara::ucm` / `vucm` | OTA / configuration |
| Raw Data Stream | `ara::rds` | Raw streams |
| Firewall / SHWA | `ara::fw` / `shwa` | Firewall / safe hardware accel |

### 2.2 Keep / simplify / defer / extend

**P0 (MVP must-have):** `core`, `com`, `log`; simplified `exec`, `phm`, `sm`

**P1:** `per`, `tsync`; **`ucm` (OTA)**, **`diag` (DoIP)** skeleton; full bindings

**P2 (safety / compliance):** `crypto`, `iam`, `idsm`, `fw`, `shwa`, full `nm`; OTA backends productionized

**Extensions (weak or missing in AP):**

| Capability | Approach |
|------------|----------|
| Pipeline observability | Unified trace + VCD/FST → GTKWave |
| OpenVX | Adapter + hooks; do not invade algorithm cores |
| ROS 2 | DDS binding + optional SOME/IP↔DDS bridge |
| Toolchain | Importer + `gf.sor.json` + codegen instead of heavy commercial tools |
| Long-horizon debug | Record/Replay |
| Architecture review | DAG Viewer + Signal Lineage |

---

## 3. Naming and dual-layer API

| Layer | Namespace | Purpose |
|-------|-----------|---------|
| Compatibility / public | `gf_ara::com`, `gf_ara::exec`, `gf_ara::phm`… | Clearly ARA-like semantics |
| Core / internal | `gf::com`, `gf::runtime`, `gf::trace`… | Extensions (recording, binding switching, …) |

Principle: **compatible semantics; stronger behavior allowed.** Public headers prefer `gf_ara::*` and forward to `gf::*`.

---

## 4. Communication architecture (three transports)

```text
Application (gf_ara::com)
        │
        ▼
  Binding Router  ←── manifest / COM_BINDING=iceoryx|someip|dds|auto
   ┌────┼────┐
   ▼    ▼    ▼
iceoryx  SOME/IP  DDS(CycloneDDS)
 on-SoC   vehicle  ROS2 / cross-SoC
```

| Transport | Role | Typical use |
|-----------|------|-------------|
| iceoryx | Local zero-copy | Radar detections, frames, fusion I/O |
| SOME/IP | Service-oriented, cross-ECU | Chassis, body, external SOA |
| DDS | Data-centric, ecosystem | ROS2 rviz/foxglove, cross-SoC IVI, prototypes |

Apps depend only on the unified API; runtime selects binding by profile. DDS vs SOME/IP semantic differences must live in SOR / mapping tables (Partition/Topic ↔ ServiceInstance, etc.), not only in plugin code.

---

## 5. Model-driven SOR and codegen

**SOR** = **Statement of Requirements** — the project’s single requirements/model contract (`gf.sor.json`). Early drafts called this IR; the standard name is SOR.

### 5.1 Format roles (confirmed)

| Format | Direct codegen input? |
|--------|------------------------|
| OEM `.arxml` / `.dbc` | No → Importer |
| `req.yaml` / optional `gf.idl` | No → normalize to SOR |
| **`gf.sor.json`** | **Yes (only)** |

Pipeline:

```text
OEM.arxml|dbc + req.yaml
        → Importer
        → gf.sor.json
        → lint
        → codegen
        → gf_ara Proxy/Skeleton + EM/PHM manifests + binding configs + adapter stubs
```

Architect tools (DAG / signal review) **read the same SOR**, so diagrams stay aligned with generated code.

Authoring and OEM import contract: [sor-authoring.md](sor-authoring.md) · examples: [projects/](../../../projects/)

### 5.2 Required SOR content

- `schema_version`
- `types[]`
- `services[]` (method / event / field + QoS)
- `deployments[]`: process, function group, resources; **each process `provides[]` / `requires[]`**
- `dataflows[]` (explicit or derived): producer → service/field → consumers; fan-out supported
- `bindings[]`
- `imports_meta`: OEM signal names ↔ stable service fields, source hashes

Without provide/require you **cannot draw a trustworthy DAG** or answer “who subscribes vehicle speed?”.

### 5.3 Shared signals (example: vehicle speed)

Wrong: perception, planning, and control each read CAN directly.  
Right:

1. Map DBC `VehicleSpeed` → `VehicleMotion.speed`
2. `vehicle.motion_gateway` is the **sole provider**
3. Perception / planning / control `require` the same service
4. Signal Review lists all consumers and QoS

When OEM signal tables change, prefer gateway + mapping edits and **avoid rewriting perception / planning / control**. Generated code goes under `generated/`; hand-written logic stays in `apps/*/src`.

---

## 6. SOA: service boundary vs process boundary

**SOA** = stable, discoverable, replaceable interfaces.  
**Process** = fault isolation and deployment granularity.

Do not force “one feature = one process”; that burns context switches, endpoints, and memory.

| Prefer separate processes | Prefer same process |
|---------------------------|---------------------|
| Crashy SDK / drivers; OEM churn | Pure operators; shared lifetime |
| Must not kill control path (IVI, radar) | Ultra-high rate under tight RAM |
| May move to another SoC | Forever pinned to this domain controller |

**Default process list:**

| Process | Notes |
|---------|-------|
| `gf.exec_manager` / `gf.phm` / `gf.sm` | Platform resident |
| `sensor.radar_*` | **Radar separate** (default recommendation) |
| `sensor.camera_ingest` | Camera input |
| `perception.pipeline` | Fusion / OpenVX |
| `planning.service` | Planning |
| `control.service` | Control (shortest path, highest priority) |
| `vehicle.actuator_gateway` | Actuators (optionally separate) |
| `ivi.service` | Local or remote SoC; never colocated with control |

Manifests may **colocate** light services into one OS process without changing service interfaces.

---

## 7. Deployment boundaries

| Class | Contents |
|-------|----------|
| **On-board always** | EM, PHM, SM, sensor adapters, perception/planning/control, IVI (local or peer), needed bindings, ring-buffer Trace Agent |
| **Host only (never ship)** | Importer, codegen, DAG / Signal Review, GTKWave, offline replay, ROS visualization |
| **Early (`desktop` profile)** | Simulated sensors, full recording, ROS bring-up |
| **Vehicle debug (`vehicle-debug`)** | Sampled Record, diag probes; off by default in production |

Phases: T0 desktop → T1 board+host → T2 HIL → T3 vehicle debug → T4 production trim.

---

## 8. Observability

| Layer | Means | Use |
|-------|-------|-----|
| Design-time | DAG Viewer, Signal Lineage | Architecture / signal-path review |
| Runtime (fine) | Trace → VCD/FST → GTKWave | Micro-timing, pipeline jitter |
| Runtime (long) | Record/Replay | Hour-scale reproduction, deterministic replay |

Principles: unify clocks first; read-only replay before injection replay; default to sampled recording on board so I/O does not kill realtime paths.

---

## 9. Portability: OSAL / HAL / Binding

```text
Apps (perception/planning/…)
    → gf_ara API
    → gf runtime
         ├→ Binding plugins (iceoryx / someip / dds)
         └→ OSAL → Linux (first) / QNX (later)
Apps / adapters
    → HAL → concrete SoC / radar SDK / CAN
```

When changing platforms: apps and most runtime stay put; touch OSAL (first port), HAL (per vehicle), bindings (library availability), and deployment profiles. **No `#ifdef SOC_X` in perception/planning/control.**

---

## 10. Repository and artifacts

**For now: one monorepo (single git, multiple packages).**  
Reason: `gf.sor.json` couples runtime, codegen, and architect tools; splitting too early causes contract drift and version hell.

Suggested layout:

```text
AI_Giraffe-Flow/
  schemas/                 # SOR contract, semver
  middleware/              # on-board runtime
  platform/osal|hal/
  bindings/
  tools/importer|codegen|architect|record_replay|lint/
  apps/                    # reference processes; customer prod apps in other repos
  deploy/profiles/
  deps/                    # third-party manifests + version lock
  third_party/             # upstream checkouts (after pins)
  docs/en/  docs/zh/
  ci/
```

Skeleton already in-tree: [STRUCTURE.md](../../../STRUCTURE.md) · [deps/README.md](../../../deps/README.md).

Artifact lines may split into `gf-runtime`, `gf-tools`, `gf-schemas`.  
Board CI **must not** build GUI tools.  
`schemas` changes must run golden codegen + at least one multi-process e2e.

**Customer vehicle projects** live in separate repos: pin schema/runtime/tools versions + own SOR/HAL/business code.  
Split later only when the schema is stable and independent release/licensing is needed; prefer `architect UI → tools → template apps`; keep middleware+schemas last.

---

## 11. Four delivery principles

1. Freeze the SOR/IDL subset before writing generators.  
2. Read-only replay before controllable injection.  
3. One clock abstraction across the stack.  
4. Encode DDS ↔ SOME/IP mappings in SOR — not tribal knowledge.

---

## 12. Milestones (summary)

| Milestone | Acceptance |
|-----------|------------|
| M0 | Module matrix, SOR schema (with graph info), import contract, SOA/deploy boundaries reviewed |
| M1 | Desktop multi-process + three bindings; OEM sample import; DAG / signal review usable |
| M2 | EM+PHM recovery; radar/IVI faults must not kill control |
| M3 | ROS↔DDS; GTKWave + Record/Replay |
| M4 | At least one embedded Linux SoC; production profile disables debug pieces |

---

## 13. Risks (short)

- Three-stack complexity → plugins + Event-first MVP  
- Over-splitting processes → decision table + colocatable deploys  
- OEM noise → human mapping review + lint  
- Diagram/code drift → tools read SOR only + CI checks  
- Premature multi-repo → monorepo first  

Operational detail: [WORKFLOW.md](../operations/WORKFLOW.md).
