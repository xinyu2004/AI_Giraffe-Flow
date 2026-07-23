# Verify — oem_a / afc_with_uss

非产品路径。产品：`projects/oem_a/afc_with_uss/scripts/{compile,run}_{sil,hil}.sh`。

| Script | Purpose |
|--------|---------|
| [smoke_sil.sh](smoke_sil.sh) | compile + 双进程 `run_iox_demo` |
| [run_sil_multiproc.sh](run_sil_multiproc.sh) | 有限帧主链 + exec/phm 断言 |
| [smoke_sil_multiproc.sh](smoke_sil_multiproc.sh) | compile → multiproc |
| [smoke_sil_observability.sh](smoke_sil_observability.sh) | multiproc → Tag → MCAP |
| [smoke_sil_phm_fault.sh](smoke_sil_phm_fault.sh) | PHM miss→recover |
| [run_sil_live_foxglove.sh](run_sil_live_foxglove.sh) | 别名 → 产品 `run_sil.sh` |
| [deploy_hil.sh](deploy_hil.sh) | 板端部署 stub |

旧名 `compile_and_run` / `run_bringup` → `smoke_sil.sh`。
