# Repository layout

> **Current** = as checked in today. **Target (P3)** = freeze before mass moves / two-tab UI.  
> Do not invent new top-level dirs ad hoc; extend this file first.

---

## Current (as of now)

```text
AI_Giraffe-Flow/
  projects/           # OEM / SKU: wiring, req, platform, interfaces, apps, scripts
  middleware/         # board runtime + third_party/ checkouts
  octave_planning/    # planning .m gold (workload, not the product)
  # SKU apps live under projects/<sku>/apps/（无根 apps/ 演示）
  tools/              # gf-config, gf-codegen, gf-octavecoder, gmt, gmt_board, …
  common/             # launch/deploy **templates** (copy into SKU; then fork)
  carla_scenarios/    # host CARLA Client A (place/IC; not under SKU)
  devops/             # bench CI → CD last mile (hardware)
  fusa/               # Functional Safety → Safety Case evidence
  dep-manifest/       # dependency pins + bootstrap.sh (checkouts → middleware/third_party/)
  cmake/ scripts/ docs/
  gallery/            # README media (GIF / screenshots / later video)
```

Flow today:

```text
bash scripts/bootstrap_deps.sh   # → dep-manifest/bootstrap.sh
→ bash common/bootstrap_sku_scripts.sh <sku>   # copy templates if missing
→ projects/<sku>/scripts/compile_sil.sh
→ projects/<sku>/scripts/run_sil.sh       # EM + optional GMT_depend
→ board: systemd/init → runtime/bin/gf_em_daemon   # board runtime
→ host debug: runtime/bin/giraffe_launch           # optional
```

---

## Target layout (P3) — freeze this

```text
AI_Giraffe-Flow/
│
├── dep-manifest/                 # WHAT to fetch/build (not the source tree)
│   ├── DEPENDENCIES.yaml
│   ├── versions.lock.md
│   ├── README.md
│   └── bootstrap.sh              # real installer
│
├── middleware/                   # board / SIL runtime (product core)
│   ├── bindings/ iceoryx, gf_channel, …
│   ├── exec/ phm/ sm/ collector/ diag/ ucm/ log/ per/ tsync/
│   ├── runtime/                  # process bring-up (SIL/HIL shared)
│   ├── trace/                    # timing → VCD / GMT (debug-path adjacent)
│   ├── hal/
│   ├── third_party/              # WHERE sources land (gitignore)
│   └── tests/                    # middleware unit + component tests
│       ├── unit/                 # per-module (core, com, phm, …)
│       └── component/            # multi-module in-process
│
├── octave_planning/              # planning .m gold (workload); C via gf-octavecoder
│
├── # SKU workload apps: projects/<sku>/apps/ only
│
├── projects/<sku>/         # one vehicle / trim
│   ├── giraffe.yaml              # 唯一入口索引（原 project.yaml）
│   ├── cfg/
│   │   ├── req.yaml              # SKU / SOR 交付分解
│   │   ├── wiring.yaml           # 集成连线 + canvas
│   │   └── gf_ara_cfg/           # 中间件运行时作者树（原 platform/）
│   │       # exec · em_launch · phm · diag · log · ucm · collector · tsync · bounds
│   ├── interfaces/               # SKU io_types
│   ├── oem/                      # DBC extract / import policy
│   ├── apps/                     # SKU workload (gateway, FCM, planning gold, …)
│   ├── scenarios/
│   ├── scripts/                  # compile_sil|hil, run_sil|hil
│   ├── build-sil/ · build-hil/   # default cmake trees (gitignore)
│   ├── generated/                # compose/generate (gitignore or local)
│   ├── golden/                   # optional SOR golden
│   └── tests/                    # this SKU’s integration / smoke fixtures
│
├── tools/
│   ├── gf-config/                # author GUI (was tools/config)
│   ├── gf-codegen/               # compose/lint/generate + schemas/ (SOR contract)
│   ├── gf-octavecoder/           # .m gold → C 1:1
│   ├── gmt/                      # observe / inject / OTA sheet (no config write)
│   ├── gmt_board/                # tap / inject / gf_foxglove_ws (SIL/board side of GMT)
│   └── tests/                    # tool unit tests (pytest per package also OK)
│
├── cmake/                        # profiles, toolchain
├── scripts/                      # repo-wide helpers（SKU smoke 在 project 内）
│   ├── bootstrap_deps.sh         # → dep-manifest/bootstrap.sh
│   ├── smoke_bd_cyclone.sh
│   └── cross_link_smoke.sh
├── devops/
│   ├── ci/                       # L0 smoke · L0b toolchain · nightly · release
│   └── cd/                       # 交付占位（package stub）
│
├── docs/
│   ├── zh/ en/
│   │   ├── architecture/
│   │   ├── operations/           # ROADMAP, WORKFLOW, MIDDLEWARE_CONFIG, …
│   │   └── dependencies/
│   └── reports/                  # long-form engineering reports (optional)
│
├── fusa/                         # Functional Safety (goal: full Safety Case)
│   ├── POLICY.md · cases/ · scripts/run_cases.sh
│   ├── safety-case/ · metrics/   # Safety Case skeleton + latency/isolation
│   ├── runs/                     # local CASE logs (gitignore)
│   └── packs/                    # SKU packs via projects/.../generate_fusa_artifacts.sh
│
├── gallery/                      # README: Giraffe_Flow/ + Giraffe_Modules/ + GIF / later video
└── STRUCTURE.md                  # this file
```

### Explicit non-homes (do not create casually)

| Avoid | Use instead |
|-------|-------------|
| New root `tests/` dumping everything | `middleware/tests/`, `tools/*/tests/`, `projects/.../tests/` |
| Root `third_party/` | `middleware/third_party/` |
| Mixing pins with checkouts | `dep-manifest/` vs `middleware/third_party/` |
| SKU stubs under shared `apps/` | `projects/<sku>/apps/` |
| Claiming ASIL certificate in-repo | `fusa/` = evidence toward Safety Case; certificate out of repo |
| Committing large `fusa/runs/` / `fusa/packs/` | local / release artifact; gitignore by default |

---

## Apps policy (shared vs project)

**Shared `apps/` only if:** same binary works across SKUs with **no** `#ifdef` and **no** SKU `io_types` — config/mapping only.

| Keep shared | Move under project |
|-------------|-------------------|
| `middleware/runtime/` (bring-up lib) | `vehicle_can_gateway`, `sensing.*`, `perception.*`, `planning.*` stubs |
| iceoryx / IPC smoke in `middleware/bindings/*/testcases/` | MCU mapping inside a future SKU gateway |
| `tools/gmt_board/` tap/inject/foxglove | Allowlists stay in `req` / GMT focus |

---

## Tests — where what lives

| Kind | Location | Examples |
|------|----------|----------|
| **Unit** | `middleware/<mod>/testcases/` next to code *or* `middleware/tests/unit/<mod>/` | Result, PHM timer math；FuSa `CASE` 行 |
| **Middleware component** | `middleware/tests/component/` | com+iceoryx in-proc |
| **Tool unit** | `tools/gf-codegen/tests/`、`tools/gf-config/…`（主机；codegen 见 FuSa L2） | compose, observability |
| **SKU integration / smoke** | `projects/<sku>/scripts/verify/` | main-chain SIL（FuSa L3） |
| **Bench / golden** | `projects/.../golden/` + codegen tests | SOR golden |
| **Manual / FuSa runs** | `fusa/runs/` (local) | CASE logs, soak |

Naming: prefer `test_*.py` / `*_test.cpp` already used; don’t invent a second parallel tree at repo root.

---

## FuSa / Functional Safety — where

| Artifact | Path |
|----------|------|
| Entry + policy（目标：完整 Safety Case） | [fusa/README.md](fusa/README.md) · [fusa/POLICY.md](fusa/POLICY.md) |
| Per-module / SIL / codegen matrices | [fusa/cases/](fusa/cases/) |
| Isolation · reference latency | [fusa/metrics/](fusa/metrics/) |
| Safety Case drafts | [fusa/safety-case/](fusa/safety-case/) |
| Run matrix | [fusa/scripts/run_cases.sh](fusa/scripts/run_cases.sh) |
| Latency snapshot | [fusa/scripts/measure_latency.sh](fusa/scripts/measure_latency.sh) |
| SKU artifacts | `projects/<sku>/scripts/generate_fusa_artifacts.sh` → `fusa/packs/` |
| Generated runs / packs | `fusa/runs/` · `fusa/packs/` (**not** committed by default) |
| ISO 26262 certificate | **out of repo**（仓内积累证据，不存放证书本身） |

---

## Observability contract vs GMT (related)

| Layer | Owner | Default debug behavior (target) |
|-------|--------|----------------------------------|
| Ceiling | gf-config / `req` | `live_tap.mode: wiring_all`（debug）|
| Tap binary | **codegen** → `generated/src/obs_tap_main.cpp` | 不手改 Proxy 列表 |
| Focus / layout / record subset | **GMT** | filter ⊆ ceiling；session prefs OK |
| Internal vars | debug stream + `replayable: false` | GMT show/record；**no** inject |

---

## Tool renames (done)

| Was | Now |
|-----|-----|
| `tools/config` | `tools/gf-config` |
| `tools/codegen` | `tools/gf-codegen` |
| `deps/` | `dep-manifest/` (+ `bootstrap.sh`) |
| `scripts/bootstrap_deps.sh` | thin wrapper → `dep-manifest/bootstrap.sh` |

---

## Migration order

1. STRUCTURE target (doc) — done.  
2. Layout: `dep-manifest` + tool renames + script wrapper — **done**.  
3. Apps split: stubs → `projects/.../apps/` (per SKU) — **done** for `afc` (gateway / fcm / uss / planning).  
4. gf-config **two-tab UI** + port UX + **wiring_all / codegen tap** — **done**.

---

## Toolchain flow (target)

```text
bash scripts/bootstrap_deps.sh          # → dep-manifest/bootstrap.sh
bash projects/<sku>/scripts/compile_sil.sh   # GF_CTEST=1 for smoke tests
bash projects/<sku>/scripts/run_sil.sh       # GF_GMT_DEPEND=0 → EM only
# after stage: ./build-sil/runtime/bin/giraffe_launch
bash projects/<sku>/scripts/verify/smoke_sil.sh

project → gf-config (tab1 graph → tab2 platform) → compose/generate
        → SIL / GMT_depend / Foxglove
```

Links: [README.md](README.md) · [ROADMAP](docs/zh/operations/ROADMAP.md) · [MIDDLEWARE_CONFIG_PLAN](docs/zh/operations/MIDDLEWARE_CONFIG_PLAN.md) · [UPLOAD_CHECKLIST](projects/UPLOAD_CHECKLIST.md)
