# FuSa 政策（Functional Safety）

> **目标：完整 Safety Case** — ROADMAP P3-3 · 仓库入口 [`fusa/`](README.md)

## 分层证据（通向 Safety Case）

| 层 | 内容 | 落点 |
|----|------|------|
| **L1 板级库** | 可复现 C++ smoke + `CASE <ID> PASS\|FAIL` + 分模块矩阵 | `middleware/**/testcases/` · [`cases/*_cases.md`](cases/) |
| **L2 生成物** | gf-codegen 规则/golden（证明生成逻辑，非板端进程） | [`cases/gf_codegen_cases.md`](cases/gf_codegen_cases.md) |
| **L3 SIL 场景** | 主链 / PHM / EM 等集成脚本；不含 Observability/Inject（debug-path） | [`cases/sil_verify_cases.md`](cases/sil_verify_cases.md) |
| **本机 runs** | 汇总日志 | `fusa/runs/`（**默认不进仓**） |
| **packs** | 发版/样例证据包 | `fusa/packs/`（**默认不进仓**） |

一键（默认仅 L1）：

```bash
bash fusa/scripts/run_cases.sh
# 可选：GF_FUSA_CODEGEN=1
# L3 FuSa SIL 全套：GF_FUSA_SIL=1 …

# SKU 产物包（独立，不调用本脚本）：
# bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
```

## 边界

- **目标**是完整 Safety Case（含 HARA、安全需求追溯、工具信心等后续工作产品），本仓持续积累可引用证据。
- **当前不声称**已取得 ISO 26262 证书或 ASIL 等级已认证通过。
- 不把 stub / 主机工具（如 GMT）伪装成板级 ASIL 证据。
- **Observability Tag→MCAP / Inject** 属 **debug-path**：证实时性与稳定性即可，不进 Safety Case 默认证据集（见 `cases/sil_verify_cases.md`）。
- `fusa/runs/*.log`、`fusa/packs/**` 默认不提交进仓。

## 与 app 的关系

量产算法多为 **外部 lib**；本仓证据打在 **middleware / bindings 库**。薄 `main` / SKU stub 靠 **L3 SIL** 证明拼装，不逐个做单元 smoke。

板端启动：com 底座 → **EM（`gf_em_daemon`）** → OSAL Spawn Apps；见 [DESIGN §8.1](../docs/zh/architecture/DESIGN.md#81-板端启动顺序em)。EM / OSAL process 用例见 `cases/exec_cases.md`、`cases/osal_cases.md`。

## Safety Case

论证骨架见 [`safety-case/`](safety-case/)；**行为** isolation / **延时** latency 见 [`metrics/`](metrics/)（`measure_latency` 不并入默认 `run_cases`）。  
证据层仍是 `cases` + `run_cases` / SKU `generate_fusa_artifacts`。

## 索引

完整模块表见 [`cases/README.md`](cases/README.md)。
