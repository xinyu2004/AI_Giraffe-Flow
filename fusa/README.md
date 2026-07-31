# FuSa — Functional Safety

**目标：完整 Safety Case（ISO 26262 / ASIL 路径）。**

本目录是功能安全材料与证据的**唯一入口**。当前交付可复现的 L1/L2/L3 证据与拼装证明；Safety Case 工作产品在此基础上补齐。  
**不把 stub / 主机工具（如 GMT）伪装成板级 ASIL 证据；仓内不存放 / 不声称证书。**

| 路径 | 含义 | 进仓 |
|------|------|------|
| [POLICY.md](POLICY.md) | 边界、分层、怎么跑 | 是 |
| [safety-case/](safety-case/) | Safety Case：项定义 / SG / **追溯主表** | 是 |
| [metrics/](metrics/) | **isolation**（行为）· **latency**（参考延时） | 是 |
| [cases/](cases/) | L1/L2/L3 案例矩阵 | 是 |
| [scripts/run_cases.sh](scripts/run_cases.sh) | 跑矩阵 → `runs/cases_*.log` | 是 |
| [scripts/measure_latency.sh](scripts/measure_latency.sh) | 延时快照 → `runs/measure_summary_*.json` | 是 |
| `runs/` | 本机日志 / JSON | **否** |
| `packs/` | SKU 产物包（由 **project** 脚本生成） | **否** |

## 快速复现

```bash
# 默认 L1；可选 L2 / L3 / T4
bash fusa/scripts/run_cases.sh
GF_FUSA_CODEGEN=1 bash fusa/scripts/run_cases.sh
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh
# production-release 关 debug-path（另耗编译；可 GF_FUSA_T4_SKIP_COMPILE=1 只验 compose）
GF_FUSA_T4=1 bash fusa/scripts/run_cases.sh

# 参考延时（独立；不调用 run_cases）
bash fusa/scripts/measure_latency.sh

# 本 SKU 产物包（独立；不调用 run_cases）
bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
```

CI 分层见 [ci/README.md](../ci/README.md)。SIL 场景脚本仍在 `scripts/verify/`。
