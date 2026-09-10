# Verify — afc

本目录为 **本演示 SKU** 的验收 / smoke（非产品日常入口）。  
产品路径：`../{compile,run}_{sil,hil}.sh`（**不**含 `GF_PHM_FAULT_*`）。

平台 / host / GMT 日常质量门禁优先走 [`devops/ci/`](../../../../devops/ci/README.md)；本目录只保留 **绑死本 SKU** 的验收脚本。

**PHM 故障注入：** 仅本目录 smoke 自设 `GF_PHM_FAULT_*` 并自启进程（`run_mainchain_verify` / `smoke_sil_em_daemon`）；勿经产品 `run_sil`。

**CI 挂钩：**
- L0 → `smoke_sil.sh`（经 `devops/ci/scripts/smoke.sh`）
- L0b / L3 → `smoke_sil_observability` · `smoke_gmt_vcd`（经 `smoke_toolchain.sh`）
- L2/L3 → `smoke_doip_ota.sh`（仅通路，无刷写）

| Script | Purpose |
|--------|---------|
| [smoke_sil.sh](smoke_sil.sh) | compile + AFC 主链 `run_mainchain_verify` |
| [run_mainchain_verify.sh](run_mainchain_verify.sh) | 有限帧主链（verify 壳；可选 caller 注入 PHM） |
| [smoke_sil_observability.sh](smoke_sil_observability.sh) | main-chain → Tag → MCAP |
| [smoke_sil_phm_fault.sh](smoke_sil_phm_fault.sh) | PHM miss→recover（自设 fault） |
| [smoke_sil_sm_fg.sh](smoke_sil_sm_fg.sh) | SIL-SM-01：fcm `notify_sm` → `sm: health_fault` + Collector；Trajectory 仍在 |
| [smoke_sil_em_daemon.sh](smoke_sil_em_daemon.sh) | OS EM fork/exec + PHM restart relaunch |
| [smoke_doip_ota.sh](smoke_doip_ota.sh) | DoIP 通路冒烟（**不**冒烟刷写本身） |
| [smoke_gmt_vcd.sh](smoke_gmt_vcd.sh) | GMT VCD |
| [smoke_production_profile.sh](smoke_production_profile.sh) | production-release 关 debug-path |
| [deploy_hil.sh](deploy_hil.sh) | 板端部署 stub |
