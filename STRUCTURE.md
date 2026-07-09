# Repository layout

Monorepo **skeleton** (headers + docs; runtime/tools implementation in P0+).

```text
AI_Giraffe-Flow/
  projects/             # 按 <oem>/<vehicle>/ 组织的集成工程（四类输入 + project 入口）
  Requirement/            # 平台归档：模块 hpp 示例 + golden SOR + 原始 DBC archive
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
四类输入 + project → compose → gf.sor.json → lint/lineage → generate → build → board
Host: GMT measure / bridge / architect / CI
```

## Targets

- **Primary:** ARM Linux (aarch64 / armv7)
- **Reserved:** MIPS, RISC-V via `GF_OSAL_ARCH`

See [docs/zh/operations/ROADMAP.md](docs/zh/operations/ROADMAP.md) for P0–P3 deliverables.

Links: [README.md](README.md) · [projects/](projects/) · [deps/README.md](deps/README.md)
