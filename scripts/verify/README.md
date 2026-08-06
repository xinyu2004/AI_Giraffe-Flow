# scripts/verify/

**SKU 验收脚本已迁到各演示工程内**（平台与项目分离）：

| 演示工程 | 验收脚本 |
|----------|----------|
| oem_a / afc_with_uss | [`projects/oem_a/afc_with_uss/scripts/verify/`](../../projects/oem_a/afc_with_uss/scripts/verify/) |
| oem_b / adc_full | [`projects/oem_b/adc_full/scripts/verify/`](../../projects/oem_b/adc_full/scripts/verify/) |

产品主路径仍在各 project 的：`compile_sil` / `compile_hil` / `run_sil` / `run_hil`。

本目录下 `oem_a_afc_with_uss/`、`oem_b_adc_full/` 仅保留 **deprecated shim**（stderr 警告后转发到工程树）。新脚本与文档请直接写 project 路径。

```bash
bash projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_verify.sh
bash projects/oem_b/adc_full/scripts/verify/smoke_mcu_desktop.sh
bash fusa/scripts/run_cases.sh
```

FuSa 矩阵：[`fusa/scripts/run_cases.sh`](../../fusa/scripts/run_cases.sh) → `fusa/runs/`。
