# Verify — oem_a / afc_with_uss

本目录为 **本演示 SKU** 的验收 / smoke（非产品日常入口）。  
产品路径：`../{compile,run}_{sil,hil}.sh`。

Giraffe 平台更新不应依赖仓根 `scripts/verify/`；脚本与工程同树，便于各部门演示工程独立演进。

默认落盘（与 `run_sil` 一致，`GF_BUILD_DIR` 可改）：

| 用途 | 路径 |
|------|------|
| 二进制 | `projects/.../build-sil/` |
| session / MCAP | `${BUILD}/observability/` |
| logs / collector / per | `${BUILD}/runtime/{logs,collector,per}/` |
| 报告 | `../reports/`（lineage、`iox_shm_report.json` 等） |

| Script | Purpose |
|--------|---------|
| [smoke_sil.sh](smoke_sil.sh) | compile + 双进程 `run_iox_demo` |
| [run_sil_verify.sh](run_sil_verify.sh) | 有限帧主链 + exec/phm 断言 |
| [smoke_sil_verify.sh](smoke_sil_verify.sh) | compile → finite main-chain |
| [smoke_sil_observability.sh](smoke_sil_observability.sh) | main-chain → Tag → MCAP |
| [smoke_phm_dem_doip.sh](smoke_phm_dem_doip.sh) | PHM fault → PER + NDJSON → DoIP 0x19 |
| [smoke_sil_phm_fault.sh](smoke_sil_phm_fault.sh) | PHM miss→recover |
| [smoke_sil_em_daemon.sh](smoke_sil_em_daemon.sh) | OS EM fork/exec + PHM restart relaunch |
| [smoke_sil_inject.sh](smoke_sil_inject.sh) / [smoke_sil_inject_b2.sh](smoke_sil_inject_b2.sh) | continuous inject B1/B2 |
| [run_sil_live_foxglove.sh](run_sil_live_foxglove.sh) | **deprecated** → 产品 `../run_sil.sh` |
| [deploy_hil.sh](deploy_hil.sh) | 板端部署 stub |

Deprecated aliases（仍可跑，stderr 打 WARN）：`compile_and_run.sh` / `run_bringup.sh` → `smoke_sil.sh`；`smoke_obs_demo.sh` → `smoke_phm_dem_doip.sh`。
