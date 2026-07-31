# Safety Case 工作产品（骨架）

**目标：** 完整 ISO 26262 Safety Case。  
**现状：** 目录与追溯占位已立；可引用证据来自 [`../cases/`](../cases/) 与 `../runs/` / `../packs/`，证书与签字结论**不在仓内伪造**。

| 文档 | ISO 26262 相关 | 状态 |
|------|----------------|------|
| [item-definition.md](item-definition.md) | Item definition（项定义） | draft |
| [assumptions.md](assumptions.md) | Assumptions of use / 环境假设 | draft |
| [safety-goals.md](safety-goals.md) | Safety goals（安全目标） | draft |
| [traceability.md](traceability.md) | SG → 需求 → 设计 → 验证 追溯 | draft |
| [../metrics/latency.md](../metrics/latency.md) | 参考延时 / 预算（支撑 T2） | draft |
| [../metrics/isolation.md](../metrics/isolation.md) | PHM / 故障隔离场景索引（支撑 T2） | draft |

## 与证据层的关系

```text
Safety Case 论证（本目录）
    ↑ 引用
L1/L2/L3 cases + runs/packs（fusa/cases · run_cases · generate_fusa_artifacts）
    ↑ 实现
middleware/** · scripts/verify/**
```

政策边界见 [../POLICY.md](../POLICY.md)。
