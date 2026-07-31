# Safety Case 工作产品

**目标：** 完整 ISO 26262 Safety Case。  
**现状：** SG-01…04 已建立 **SG → SR → 设计 → L1/L3 / isolation / latency** 追溯；SG-05（production profile）与 ASIL/HARA 仍开。  
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

## 优先缺口（下一轮）

1. SIL-T4 全量纳入默认 CI（目前 `GF_FUSA_T4=1` 可选，因另编 `build-prod`）  
2. Collector 掉电持久化 / Classic DEM（若项内需要）  
3. 板端 soak 复测 latency 预算（主机 SIL ≠ ECU）  

政策边界见 [../POLICY.md](../POLICY.md)。证据层入口 [../cases/README.md](../cases/README.md)。
