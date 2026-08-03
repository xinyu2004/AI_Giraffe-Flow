# Safety Case 工作产品

**目标：** 完整 ISO 26262 Safety Case。  
**现状：** SG-01…05 已挂追溯与验证入口；T4 为**发版必跑**门禁。ASIL/HARA 仍 TBD。板端 soak 等见 assumptions A-07 → P3z。  
**不声称**证书或 ASIL 已认证；不把 GMT/stub 当板级 ASIL 证据。

| 文档 | ISO 26262 相关 | 状态 |
|------|----------------|------|
| [item-definition.md](item-definition.md) | Item definition（项定义） | living draft |
| [assumptions.md](assumptions.md) | Assumptions of use | living draft |
| [safety-goals.md](safety-goals.md) | Safety goals | living draft |
| [traceability.md](traceability.md) | SG → SR → 设计 → 验证 | **living**（主表） |
| [../metrics/latency.md](../metrics/latency.md) | 参考延时 / 预算（T2） | draft（有实测快照） |
| [../metrics/isolation.md](../metrics/isolation.md) | 故障隔离场景索引（T2） | draft（有 PASS 记录） |

## 论证结构

```text
Item definition + Assumptions
        ↓
   Safety goals (SG-01…05)
        ↓
   Safety requirements (SR-xx.y)  ← 写在 traceability.md
        ↓
   设计 / 机制（middleware · daemon · yaml）
        ↓
   验证：L1 cases · L3 SIL · isolation · latency
        ↑
   runs/ · packs/（本机；默认不进仓）
```

## 优先缺口（下一轮 / P3z）

1. 云 CI 默认跑 T4（样例已写 `devops/ci/workflows/ci.yml.example`；本地发版必跑）  
2. Collector 掉电持久化 / Classic DEM（若项内需要）→ P3z  
3. 板端 soak 复测 latency（主机 SIL ≠ ECU）→ P3z  

政策边界见 [../POLICY.md](../POLICY.md)。证据层入口 [../cases/README.md](../cases/README.md)。
