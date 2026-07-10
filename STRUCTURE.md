# Repository layout

```text
AI_Giraffe-Flow/
  projects/                  # OEM/产品：DBC + interfaces + wiring + req
  middleware/                # 板端 runtime
    core/ com/ bindings/ osal/
    hal/                     # board HAL
    third_party/             # iceoryx 等上游检出（gitignore）
  apps/                      # 业务与仿真进程
  tools/                     # codegen、gmt（P1）、bridge/ros2（主机侧）
  schemas/                   # gf.sor.json contract + examples
  deps/                      # 依赖钉扎（策略，非检出树）
  cmake/ scripts/ ci/ docs/
```

## Toolchain flow（当前）

```text
bash scripts/bootstrap_deps.sh
cmake -B build && cmake --build build
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh   # SIL: compose → generate → compile → RouDi

# HIL（交叉）
bash projects/oem_a/afc_with_uss/scripts/compile_hil.sh

project → gf-codegen compose → gf.sor.json → lint/lineage
         → generate（types + Proxy/Skeleton）→ iceoryx demo
```

上传前见：[projects/UPLOAD_CHECKLIST.md](projects/UPLOAD_CHECKLIST.md)

## Targets

- **Primary:** ARM Linux (aarch64 / armv7)
- **Reserved:** MIPS, RISC-V via `GF_OSAL_ARCH`

Links: [README.md](README.md) · [projects/](projects/) · [deps/README.md](deps/README.md) · [代码分层](docs/zh/architecture/code-layers.md) · [上传清单](projects/UPLOAD_CHECKLIST.md)
