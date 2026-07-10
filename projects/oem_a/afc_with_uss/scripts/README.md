# Project scripts — oem_a / afc_with_uss

| Script | Purpose |
|--------|---------|
| [compile_sil.sh](compile_sil.sh) | Host：compose → generate → **compile** → ctest |
| [run_sil.sh](run_sil.sh) | Host：RouDi + uss_feed + demo_pipeline |
| [smoke_sil.sh](smoke_sil.sh) | Host 一键：`compile_sil` → `run_sil` |
| [compile_hil.sh](compile_hil.sh) | 交叉编译（默认 aarch64）→ `build-hil/` |
| [run_hil.sh](run_hil.sh) | 板端运行（P0 stub） |
| [deploy_hil.sh](deploy_hil.sh) | 部署到板（P0 stub） |
| [_common.sh](_common.sh) | 共享路径 / codegen / bootstrap 检查 |

兼容旧名：`compile_and_run.sh`、`run_bringup.sh` → `smoke_sil.sh`。

```bash
# SIL（桌面）
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh
# 或分步
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# HIL（交叉；需 aarch64-linux-gnu-g++）
bash projects/oem_a/afc_with_uss/scripts/compile_hil.sh
bash projects/oem_a/afc_with_uss/scripts/run_hil.sh   # stub
```

Generated headers: `../generated/`（gitignored）。
Runtime staging: `middleware/.deps-prefix/`、`middleware/third_party/`（仓级 `scripts/bootstrap_deps.sh`）。
