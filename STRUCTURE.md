# Repository layout

Monorepo **skeleton** (headers + docs; runtime/tools implementation in P0+).

```text
AI_Giraffe-Flow/
  schemas/              # gf.sor.json contract + examples (desktop_ap_only, vehicle_ap_mcu_cp)
  middleware/           # Board runtime (trim via runtime_modules)
    core exec phm sm com log trace
    ucm/                # OTA (gf_ara::ucm) — P1 skeleton
    diag/               # DoIP (gf_ara::diag) — P1 skeleton
  platform/
    osal/               # POSIX + arch/{arm,mips,riscv}
    hal/                # Board packs
  bindings/             # iceoryx · someip · dds · cross_domain_ipc
  bridge/               # Optional ROS2 helpers
  tools/
    codegen/            # gf-codegen: import · lint · generate
    gmt/                # Giraffe Measure Tool: architect · measure · bridge
    importer lint …     # legacy paths → see codegen/gmt plugins
  apps/
    adapters/           # OEM/sensor/MCU gateway (mcu_cp_gateway)
    simulators/         # Semantic stubs (no production algo in repo)
    demo_pipeline/
    radar perception …  # legacy reference; production in external repos
  deploy/               # profiles + manifests
  deps/                 # DEPENDENCIES.yaml (no SWUpdate)
  docs/en|zh/           # DESIGN · ROADMAP (P0–P3) · …
```

## Toolchain flow

```text
OEM → gf-codegen (import → lint → generate) → build → board
Host analysis → GMT (architect / measure / bridge)
```

## Targets

- **Primary:** ARM Linux (aarch64 / armv7)
- **Reserved:** MIPS, RISC-V via `GF_OSAL_ARCH`

See [docs/zh/operations/ROADMAP.md](docs/zh/operations/ROADMAP.md) for P0–P3 deliverables.

Links: [README.md](README.md) · [deps/README.md](deps/README.md)
