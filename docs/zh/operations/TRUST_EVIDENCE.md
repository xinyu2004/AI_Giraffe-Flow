# Trust evidence（认证前期支持）

> **我们提供什么 / 不代做什么** — ROADMAP P3-3 · STRUCTURE trust 路径

## 提供

| 层 | 内容 | 落点 |
|----|------|------|
| **L1 板级库** | 可复现 C++ smoke + `CASE <ID> PASS\|FAIL` + 分模块矩阵 | `middleware/**/testcases/` · [`docs/reports/trust-evidence/*_cases.md`](../reports/trust-evidence/) |
| **L2 生成物** | gf-codegen 规则/golden（证明生成逻辑，非板端进程） | [`gf_codegen_cases.md`](../reports/trust-evidence/gf_codegen_cases.md) |
| **L3 SIL 场景** | **trust** 集成脚本（主链 / PHM 等）；不含 Observability/Inject | [`sil_verify_cases.md`](../reports/trust-evidence/sil_verify_cases.md) |
| 本地 pack | 汇总日志 | `evidence/sil/`（**默认不进仓**） |

一键（默认仅 L1）：

```bash
bash scripts/verify/trust_evidence_modules.sh
# 可选：GF_TRUST_EVIDENCE_CODEGEN=1 GF_TRUST_EVIDENCE_SIL=1 …
```

## 不提供 / 不代做

- ISO 26262 **证书**、完整 Safety Case、HARA 代办、工具鉴定代办
- 把 stub / 主机工具（如 GMT）伪装成板级 ASIL 证据
- 将 **Observability Tag→MCAP / Inject** 等调试通路当作认证支撑（它们属 **debug-path**：证实时性与稳定性即可；见 `sil_verify_cases.md`）
- 将 `evidence/sil/*.log` 默认提交进仓

## 与 app 的关系

量产算法多为 **外部 lib**；本仓证据打在 **middleware / bindings 库**。薄 `main` / SKU stub 靠 **L3 SIL** 证明拼装，不逐个做单元 smoke。

## 索引

完整模块表见 [`docs/reports/trust-evidence/README.md`](../reports/trust-evidence/README.md)。
