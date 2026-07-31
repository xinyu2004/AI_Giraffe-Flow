# scripts/verify/

模块 / 功能验证脚本（**非** SKU 产品主路径）。

产品主路径只在各 project 的四个脚本：`compile_sil` / `compile_hil` / `run_sil` / `run_hil`。

| Dir | Project |
|-----|---------|
| [oem_a_afc_with_uss/](oem_a_afc_with_uss/) | AFC + USS SIL smoke / multiproc / PHM / MCAP |
| [oem_b_adc_full/](oem_b_adc_full/) | MCU desktop IPC smoke |
| [trust_evidence_modules.sh](trust_evidence_modules.sh) | L1 库 `CASE` 汇总 → `evidence/sil/`（见 [trust-evidence](../../docs/reports/trust-evidence/)） |

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_multiproc.sh
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh
bash scripts/verify/trust_evidence_modules.sh
```
