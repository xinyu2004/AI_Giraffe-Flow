# Traceability — draft

SG → 机制 → 验证（可引用路径）。单元格随实现填实。

| SG | 设计 / 机制 | L1 case | L3 SIL | 备注 |
|----|-------------|---------|--------|------|
| SG-01 | `gf_em_daemon` + exit 75 relaunch；`gf_exec_em_smoke` | EM-* · EMD-* · OSAL-P* | SIL-EM-02 | [exec_cases](../cases/exec_cases.md) |
| SG-02 | PHM Alive/Deadline · `GF_PHM_FAULT_MS` | PHM-* | SIL-03 | [phm_cases](../cases/phm_cases.md) · [isolation](../metrics/isolation.md) |
| SG-03 | `StateClient` / FG 迁移 | SM-* | — | [sm_cases](../cases/sm_cases.md) |
| SG-04 | Collector local_store ring | COLL-* | — | [collector_cases](../cases/collector_cases.md) |
| SG-05 | production profile（待建） | — | — | ROADMAP T4 |

## 复现命令

```bash
# 矩阵成绩单 → fusa/runs/cases_*.log
bash fusa/scripts/run_cases.sh
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh

# SKU 产物包（可选附带最近 cases log）
bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
```

最近 SIL 绿结果见 [../cases/sil_verify_cases.md](../cases/sil_verify_cases.md)。
