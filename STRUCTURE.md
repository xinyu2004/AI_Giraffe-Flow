# Repository layout

```text
AI_Giraffe-Flow/
  projects/                  # OEM/产品：DBC + interfaces + wiring + req
  middleware/                # 板端 runtime
    core/ com/ bindings/ osal/
    hal/                     # board HAL
    third_party/             # iceoryx 等上游检出（gitignore）
  apps/                      # 业务与仿真进程
  tools/                     # codegen、config(gf-config GUI)、gmt、bridge
  schemas/                   # gf.sor.json contract + examples
  deps/                      # 依赖钉扎（策略，非检出树）
  cmake/ scripts/ ci/ docs/
```

## Toolchain flow（当前）

```text
bash scripts/bootstrap_deps.sh
# 产品主路径
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# HIL（交叉）
bash projects/oem_a/afc_with_uss/scripts/compile_hil.sh

# 验证
bash scripts/verify/oem_a_afc_with_uss/smoke_sil.sh

project → gf-config 保存 / compose → gf.sor.json → lint/lineage
         → generate → compile_sil / run_sil
```

上传前见：[projects/UPLOAD_CHECKLIST.md](projects/UPLOAD_CHECKLIST.md)

## Targets

- **Primary:** ARM Linux (aarch64 / armv7)
- **Reserved:** MIPS, RISC-V via `GF_OSAL_ARCH`

Links: [README.md](README.md) · [projects/](projects/) · [deps/README.md](deps/README.md) · [代码分层](docs/zh/architecture/code-layers.md) · [上传清单](projects/UPLOAD_CHECKLIST.md)
