# Repository layout

Monorepo **skeleton** (headers + docs; runtime/tools implementation in P0+).

```text
AI_Giraffe-Flow/
  projects/             # 按 <oem>/<product>/：DBC + interfaces(hpp) + wiring + req + golden
  schemas/              # gf.sor.json contract + examples
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
    codegen/            # gf-codegen: compose · import · lint · generate
    gmt/                # Giraffe Measure Tool: architect · measure · bridge
  apps/
    adapters/           # OEM/sensor/MCU gateway
    simulators/         # Semantic stubs
    demo_pipeline/
  deploy/               # profiles + manifests
  deps/                 # DEPENDENCIES.yaml
  docs/en|zh/
```

## Toolchain flow

```text
project(oem+interfaces+wiring+req) → compose → gf.sor.json → lint/lineage → generate → build → board
Host: GMT / CI
```

## Targets

- **Primary:** ARM Linux (aarch64 / armv7)
- **Reserved:** MIPS, RISC-V via `GF_OSAL_ARCH`

Links: [README.md](README.md) · [projects/](projects/) · [deps/README.md](deps/README.md)
