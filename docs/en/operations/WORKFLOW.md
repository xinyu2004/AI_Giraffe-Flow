# Giraffe Flow Operational Workflow

> Document version: 0.1  
> **中文:** [WORKFLOW.md](../../zh/operations/WORKFLOW.md)  
> Companion design: [DESIGN.md](../architecture/DESIGN.md)  
> Note: this describes the **target** workflow. Executable CLIs will be filled in after implementation. Steps marked “planned” have no binaries yet.

---

## 0. Roles and environments

| Role | Primary environment | Typical artifacts |
|------|---------------------|-------------------|
| Architect | Host PC | SOR, DAG, signal-review reports |
| Middleware / tools developer | Host + optional board cross-build | runtime, tools, schemas |
| App developer (perception / planning-control) | Host → board | Hand-written logic + generated com |
| Integration / test | Desktop → HIL → vehicle | profiles, bags, traces |

**Do not** ship Importer / Codegen / DAG / GTKWave in production images.

---

## 1. Repo checkout and layout (once implemented)

```text
AI_Giraffe-Flow/
  schemas/
  middleware/
  tools/
  apps/
  deploy/profiles/
  docs/en/   docs/zh/
```

Suggested reading order:

1. [README.md](../../../README.md)  
2. [DESIGN.md](../architecture/DESIGN.md)  
3. This document  

Start Phase 0 skeleton work only after documentation review.

---

## 2. Day-to-day feature work (stable SOR already exists)

Use when changing perception / planning / control logic on existing service contracts.

```text
Pull platform repo (pin schema/runtime versions)
  → Edit apps/<domain>/src (never edit generated/)
  → Build & integrate with desktop profile
  → Need a new signal? Follow §3 OEM/SOR change — do not read DBC from business code
  → Commit; CI: unit + multi-process smoke
```

Rules:

- Apps depend only on **stable service names** (`ObjectList`, `Trajectory`, `VehicleMotion`, …)
- Generated `gf_ara::com` Proxy/Skeleton is owned by codegen; hand edits vanish on regen

---

## 3. Vehicle integration (four inputs + compose)

Module engineers deliver **`io_types.hpp` only** (no JSON).  
System integrator maintains `projects/<oem>/<vehicle>/` and runs:

```bash
gf-codegen compose --project projects/oem_demo/vehicle_demo/project.yaml
```

Contract: [sor-authoring.md](../architecture/sor-authoring.md) · [projects/oem_demo/vehicle_demo/](../../../projects/oem_demo/vehicle_demo/)

### 3.1 DevOps acceptance and Golden (`req.yaml`)

`acceptance` block: `sor_golden` (path to this project's known-good `gf.sor.json` snapshot), lineage gate, required services. CI runs compose + lint + golden diff before merge — codegen stays off production images.

**Golden** = regression/CI reference SOR, not a board runtime file and not the OEM architecture report. Update it only on intentional contract/wiring changes. Details (zh): [INTEGRATOR_WALKTHROUGH §3](../../../projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md#3-golden对照用的正确答案sor) · example: [adc_full/golden/](../../../projects/oem_b/adc_full/golden/)

### 3.2 Breaking service changes

If a stable field shape must change:

1. Bump `gf.sor` schema / service version  
2. Update all `requires` (prefer compile errors from codegen)  
3. CI blocks until every consumer aligns  

---

## 4. New service / application flow

1. Define `types` + `services` in `req.yaml` or SOR  
2. Declare process + `provides` / `requires` under `deployments`  
3. lint → DAG review → codegen  
4. Implement Skeleton callbacks in `apps/<name>/src`  
5. Attach function group + PHM supervision  
6. Desktop integrate, then add `board` profile  

---

## 5. Multi-process integration (desktop T0)

### 5.1 Suggested start order

1. Platform: `exec_manager`, `phm` (and routing pieces as needed)  
2. Shared signals: `vehicle.motion_gateway`  
3. Sensors: `radar`, `camera_ingest`  
4. `perception` → `planning` → `control`  
5. `ivi` (optional)  

EM can later auto-order this from manifest dependencies.

### 5.2 Binding selection

| Scenario | Prefer |
|----------|--------|
| Same-machine high-rate | iceoryx |
| ROS visualization / prototype | DDS |
| Real ECU | SOME/IP |
| Auto prefer local | `auto` (planned) |

Change only manifests / env vars — not application logic.

### 5.3 Observability

- Design-time: DAG / signal review vs expected topology  
- Runtime: enable ring-buffer trace; export GTKWave when needed  
- Hard bugs: enable Record (full capture OK on desktop first)  

---

## 6. Board + host integration (T1)

```text
Board: runtime + apps + lightweight Trace Agent (sampled)
Host:  codegen (if needed), DAG, GTKWave, offline replay, ROS tools
Link:  pull sampled bags / VCD over Ethernet; do not run full architect GUI on board
```

Notes:

- Disable full payload recording on board  
- Same SOR as desktop; only switch profile to `board`  

---

## 7. HIL (T2)

- Enable real SOME/IP / sensor HAL  
- PHM: Alive / Deadline + restart budget  
- Prove: kill radar process → perception degrades, control goes conservative, IVI may die without killing control  

---

## 8. Vehicle debug (T3)

Use `vehicle-debug` profile:

| On | Off |
|----|-----|
| Sampled Record Agent | Host GUIs, codegen |
| Remote log dump | Full iceoryx dump to disk |
| SOME/IP diag probes (if needed) | Desktop-only simulators |

Field issues:

1. Capture sampled bag + metadata (time window, vehicle, SOR version)  
2. Offline Replay + Signal / Trace correlation in the lab  
3. If root cause is mapping / contract → return to §3; do not hotfix random CAN reads in apps  

---

## 9. Production trim (T4)

`production` profile:

- Keep: EM, PHM, SM, required apps and bindings  
- Disable: Record, ROS deps, diag probes, chatty logging  
- Artifacts: `gf-runtime` family only; no `gf-tools`  

Release checklist:

- [ ] SOR schema version pinned  
- [ ] No mandatory unmapped signals  
- [ ] Control path free of GUI / Python tool deps  
- [ ] PHM restart/degrade paths reviewed  
- [ ] IVI peer-SoC failure isolation tested  

---

## 10. Architect workflow (DAG + signals)

Use as a design gate after OEM import or before a release.

1. Load current `gf.sor.json`  
2. **DAG Viewer**  
   - Collapse by function group  
   - Inspect edge binding + QoS  
3. **Signal Lineage**  
   - Query `VehicleMotion.speed` and key perception outputs  
   - Export subscriber tables for the review packet  
4. Diff against previous SOR: new edges, removed providers, fan-out changes  
5. Only then codegen / merge to main  

**Hard rule:** PowerPoint is not the source of truth; SOR is.

---

## 11. Porting to a new SoC / OS (sketch)

1. Implement or port `platform/osal` (threads, clocks, shm, processes)  
2. Implement board `platform/hal` (radar SDK, camera, CAN)  
3. Confirm binding library availability; disable or swap if missing  
4. Add `deploy/profiles/<soc>.yaml` (affinity, memory pools)  
5. Smoke reference apps, then wire the customer project  

Document the platform↔customer version matrix in the customer README.

---

## 12. Suggested review gates (before coding)

Complete at least one written review covering:

| Topic | Document |
|-------|----------|
| AP module keep/defer | DESIGN §2 |
| Transports + API naming | DESIGN §3–4 |
| SOR as sole contract | DESIGN §5 |
| Process granularity (radar / IVI) | DESIGN §6–7 |
| Monorepo strategy | DESIGN §10 |
| OEM intake operability | This doc §3 |

Optional notes file: `docs/en/architecture/REVIEW_NOTES.md` (create when reviewing).

---

## 13. What exists today / what does not

| Present | Not yet |
|---------|---------|
| README / README_zh | schemas, middleware, tools source |
| docs/en + docs/zh (DESIGN / WORKFLOW) | Executable importer/codegen |
| LICENSE | Board build scripts and concrete profiles |

Next usual step after doc review: monorepo skeleton + draft `gf.sor.schema.json`.
