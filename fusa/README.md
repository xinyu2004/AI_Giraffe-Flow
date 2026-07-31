# FuSa — Functional Safety

**目标：完整 Safety Case（ISO 26262 / ASIL 路径）。**

本目录是 Giraffe Flow 功能安全相关材料与证据的**唯一入口**：案例矩阵、本机复现日志、发版证据包。  
当前交付的是可复现的 L1/L2/L3 证据与拼装证明；Safety Case 工作产品在此基础上持续补齐，**不把 stub / 主机工具（如 GMT）伪装成板级 ASIL 证据**。

| 路径 | 含义 | 进仓 |
|------|------|------|
| [POLICY.md](POLICY.md) | 边界、分层、怎么跑 | 是 |
| [cases/](cases/) | L1/L2/L3 案例矩阵 | 是 |
| [scripts/run_cases.sh](scripts/run_cases.sh) | 跑矩阵 → `runs/` | 是 |
| `runs/` | 本机 `cases_*.log` | **否** |
| `packs/` | 各 SKU 产物包（由 **project** 脚本生成） | **否** |

## 快速复现

```bash
# FuSa 矩阵（跨模块）→ fusa/runs/
bash fusa/scripts/run_cases.sh
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh

# 本 SKU 产物包（不调用 run_cases；可另跑）→ fusa/packs/oem_a_afc_with_uss/
bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
```

CI 分层见 [ci/README.md](../ci/README.md)。SIL 场景脚本仍在 `scripts/verify/`。
