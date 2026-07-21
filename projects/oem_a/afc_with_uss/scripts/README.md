# Project scripts — oem_a / afc_with_uss

| Script | Purpose |
|--------|---------|
| [compile_sil.sh](compile_sil.sh) | Host：compose → generate → **compile** → ctest |
| [run_sil.sh](run_sil.sh) | Host：双进程回归 RouDi + uss_feed + demo_pipeline |
| [smoke_sil.sh](smoke_sil.sh) | Host 一键双进程：`compile_sil` → `run_sil` |
| [run_sil_multiproc.sh](run_sil_multiproc.sh) | Host：**四进程主链** gateway→fcm/uss→planning→Trajectory |
| [smoke_sil_multiproc.sh](smoke_sil_multiproc.sh) | Host 一键主链：`compile_sil` → `run_sil_multiproc` |
| [smoke_sil_observability.sh](smoke_sil_observability.sh) | O/F：multiproc → JSONL → Tag → MCAP |
| [run_sil_live_foxglove.sh](run_sil_live_foxglove.sh) | P2.5 Live：主链 + `gf_iox_obs_tap` → GMT `--ws --stdin` |
| [smoke_sil_phm_fault.sh](smoke_sil_phm_fault.sh) | X-3：gateway PHM 故障注入（miss→recover）+ 主链仍绿 |
| [compile_hil.sh](compile_hil.sh) | 交叉编译（默认 aarch64）→ `build-hil/` |
| [run_hil.sh](run_hil.sh) | 板端运行（P0 stub） |
| [deploy_hil.sh](deploy_hil.sh) | 部署到板（P0 stub） |
| [_common.sh](_common.sh) | 共享路径 / codegen / bootstrap 检查 |

兼容旧名：`compile_and_run.sh`、`run_bringup.sh` → `smoke_sil.sh`。

```bash
# SIL 主链（P2 多进程）
bash projects/oem_a/afc_with_uss/scripts/smoke_sil_multiproc.sh

# O/F：录 session → Tag → MCAP（演示见 docs/zh/operations/OBSERVABILITY_DEMO.md）
bash projects/oem_a/afc_with_uss/scripts/smoke_sil_observability.sh

# P2.5 Live：Studio 连 ws://127.0.0.1:8765 看 EgoMotion / Trajectory
bash projects/oem_a/afc_with_uss/scripts/run_sil_live_foxglove.sh

# X：PHM 故障注入（需已 compile；或先跑 smoke_sil_multiproc）
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/smoke_sil_phm_fault.sh

# SIL 双进程回归（uss_feed ↔ demo_pipeline）
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh

# 或分步
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/run_sil_multiproc.sh

# HIL（交叉；需 aarch64-linux-gnu-g++）
bash projects/oem_a/afc_with_uss/scripts/compile_hil.sh
bash projects/oem_a/afc_with_uss/scripts/run_hil.sh   # stub
```

Generated headers: `../generated/`（gitignored）。
Runtime staging: `middleware/.deps-prefix/`、`middleware/third_party/`（仓级 `scripts/bootstrap_deps.sh`）。
