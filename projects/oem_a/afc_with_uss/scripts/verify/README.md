# Verify — oem_a / afc_with_uss

本目录为 **本演示 SKU** 的验收 / smoke（非产品日常入口）。  
产品路径：`../{compile,run}_{sil,hil}.sh`。

平台 / host / GMT 日常质量门禁优先走 [`devops/ci/`](../../../../devops/ci/README.md)（L0 / L0b toolchain / nightly / release）；本目录只保留 **绑死本 SKU** 的验收脚本（CI 编排调用此处真源）。

**CI 挂钩：**
- L0 → `smoke_sil.sh`（经 `devops/ci/scripts/smoke.sh`）
- L0b / L3 → `smoke_sil_observability` · `smoke_sil_inject` · `smoke_gmt_vcd`（经 `smoke_toolchain.sh`；发版另加 inject_b2）
- L2/L3 → `smoke_doip_ota.sh`（仅通路，无刷写）

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
| [smoke_doip_ota.sh](smoke_doip_ota.sh) | DoIP 通路冒烟（**不**冒烟刷写本身） |
| [smoke_sil_phm_fault.sh](smoke_sil_phm_fault.sh) | PHM miss→recover |
| [smoke_sil_em_daemon.sh](smoke_sil_em_daemon.sh) | OS EM fork/exec + PHM restart relaunch |
| [smoke_sil_inject.sh](smoke_sil_inject.sh) / [smoke_sil_inject_b2.sh](smoke_sil_inject_b2.sh) | continuous inject B1/B2 |
| [deploy_hil.sh](deploy_hil.sh) | 板端部署 stub |
