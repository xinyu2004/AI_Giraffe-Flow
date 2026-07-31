# Repository layout

> **Current** = as checked in today. **Target (P3)** = freeze before mass moves / two-tab UI.  
> Do not invent new top-level dirs ad hoc; extend this file first.

---

## Current (as of now)

```text
AI_Giraffe-Flow/
  projects/           # OEM / SKU: wiring, req, platform, interfaces, scripts
  middleware/         # board runtime + third_party/ checkouts
  apps/               # reference processes (mixed shared + SKU-ish stubs)
  tools/              # gf-config, gf-codegen, gmt, bridge, …
  schemas/
  dep-manifest/       # dependency pins + bootstrap.sh (checkouts → middleware/third_party/)
  cmake/ scripts/ ci/ docs/
  result_pic/         # README assets
```

Flow today:

```text
bash scripts/bootstrap_deps.sh   # → dep-manifest/bootstrap.sh
→ projects/<oem>/<sku>/scripts/compile_sil.sh | run_sil.sh
→ scripts/verify/…/smoke_*.sh
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
│   ├── core/ com/ bindings/ osal/
│   ├── exec/ phm/ sm/ diag/ ucm/ log/ …
│   ├── hal/
│   ├── third_party/              # WHERE sources land (gitignore)
│   └── tests/                    # middleware unit + component tests
│       ├── unit/                 # per-module (core, com, phm, …)
│       └── component/            # multi-module in-process
│
├── apps/                         # ONLY true platform-common
│   ├── common/                   # SIL helpers (platform_sil, …)
│   └── README.md                 # what may live here (see §Apps policy)
│
├── projects/<oem>/<sku>/         # one vehicle / trim
│   ├── project.yaml
│   ├── req.yaml
│   ├── integration/wiring.yaml
│   ├── platform/                 # exec phm diag log ucm collector…
│   ├── interfaces/               # SKU io_types
│   ├── oem/                      # DBC extract / import policy
│   ├── apps/                     # SKU stubs (gateway, uss, fcm, planning.*)
│   ├── scenarios/
│   ├── scripts/                  # compile_sil|hil, run_sil|hil
│   ├── generated/                # compose/generate (gitignore or local)
│   ├── golden/                   # optional SOR golden
│   └── tests/                    # this SKU’s integration / smoke fixtures
│
├── tools/
│   ├── gf-config/                # author GUI (was tools/config)
│   ├── gf-codegen/               # compose/lint/generate (was tools/codegen)
│   ├── gmt/                      # observe / inject / OTA sheet (no config write)
│   ├── bridge/                   # Foxglove etc.
│   └── tests/                    # tool unit tests (pytest per package also OK)
│
├── schemas/                      # gf.sor contract + examples
├── cmake/                        # profiles, toolchain
├── scripts/                      # thin wrappers + verify orchestration
│   ├── bootstrap_deps.sh         # → dep-manifest/bootstrap.sh
│   └── verify/<oem>/<sku>/       # CI/smoke entrypoints
├── ci/
│
├── docs/
│   ├── zh/ en/
│   │   ├── architecture/
│   │   ├── operations/           # ROADMAP, WORKFLOW, MIDDLEWARE_CONFIG, …
│   │   └── dependencies/
│   └── reports/                  # long-form engineering reports (optional)
│       └── trust-evidence/       # cert-ready materials (not certificates)
│
├── evidence/                     # generated / local packs (default gitignore)
│   ├── sil/                      # session clips, MCAP, latency tables
│   └── board/                    # P3z soak packs
│
├── result_pic/                   # README screenshots / architecture GIFs
└── STRUCTURE.md                  # this file
```

### Explicit non-homes (do not create casually)

| Avoid | Use instead |
|-------|-------------|
| New root `tests/` dumping everything | `middleware/tests/`, `tools/*/tests/`, `projects/.../tests/` |
| Root `third_party/` | `middleware/third_party/` |
| Mixing pins with checkouts | `dep-manifest/` vs `middleware/third_party/` |
| SKU stubs under shared `apps/` | `projects/<oem>/<sku>/apps/` |
| Safety certificates in-repo | `docs/**/trust-evidence/` = **support materials only** |
| Committing large `evidence/` | local / release artifact; gitignore by default |

---

## Apps policy (shared vs project)

**Shared `apps/` only if:** same binary works across SKUs with **no** `#ifdef` and **no** SKU `io_types` — config/mapping only.

| Keep shared | Move under project |
|-------------|-------------------|
| `apps/common/` | `vehicle_can_gateway`, `sensing.*`, `perception.*`, `planning.*` stubs |
| Optional: ultra-thin demo_pipeline / feeds | MCU payload↔semantic **mapping** (if today inside gateway) |
| Generic obs **binary** (after codegen tap) | Allowlists stay in `req` / GMT focus |

---

## Tests — where what lives

| Kind | Location | Examples |
|------|----------|----------|
| **Unit** | `middleware/<mod>/testcases/` next to code *or* `middleware/tests/unit/<mod>/` | Result, PHM timer math；trust `CASE` 行 |
| **Middleware component** | `middleware/tests/component/` | com+iceoryx in-proc |
| **Tool unit** | `tools/gf-codegen/tests/`、`tools/gf-config/…`（主机；codegen 见 trust L2） | compose, observability |
| **SKU integration / smoke** | `projects/.../tests/` + `scripts/verify/...` | multiproc SIL（trust L3） |
| **Bench / golden** | `projects/.../golden/` + codegen tests | SOR golden |
| **Manual / evidence** | `evidence/` (local) | MCAP, soak logs |

Naming: prefer `test_*.py` / `*_test.cpp` already used; don’t invent a second parallel tree at repo root.

---

## Trust / safety reports — where

| Artifact | Path |
|----------|------|
| Policy + how to produce evidence | [docs/zh/operations/TRUST_EVIDENCE.md](docs/zh/operations/TRUST_EVIDENCE.md) + ROADMAP P3-3 |
| Per-module / SIL / codegen matrices | [docs/reports/trust-evidence/](docs/reports/trust-evidence/) |
| Generated packs (CASE logs, latency, soak) | `evidence/sil/` or `evidence/board/` (**not** committed by default) |
| ISO 26262 certificate | **out of repo** (we only provide cert-ready support) |

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
3. Apps split: stubs → `projects/.../apps/` (per SKU) — **done** for `oem_a/afc_with_uss` (gateway / fcm / uss / planning).  
4. gf-config **two-tab UI** + port UX + **wiring_all / codegen tap** — **done**.

---

## Toolchain flow (target)

```text
bash scripts/bootstrap_deps.sh          # → dep-manifest/bootstrap.sh
bash projects/<oem>/<sku>/scripts/compile_sil.sh
bash projects/<oem>/<sku>/scripts/run_sil.sh
bash scripts/verify/<oem>/<sku>/smoke_sil.sh

project → gf-config (tab1 graph → tab2 platform) → compose/generate
        → SIL / GMT (focus filter) / Foxglove
```

Links: [README.md](README.md) · [ROADMAP](docs/zh/operations/ROADMAP.md) · [MIDDLEWARE_CONFIG_PLAN](docs/zh/operations/MIDDLEWARE_CONFIG_PLAN.md) · [UPLOAD_CHECKLIST](projects/UPLOAD_CHECKLIST.md)
