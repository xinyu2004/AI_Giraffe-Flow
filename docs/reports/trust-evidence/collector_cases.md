# collector — trust cases

Smoke: `gf_collector_smoke` · `middleware/collector/testcases/smoke_collector.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| COLL-01 | Clear | Configure local_store max=4 | 配置生效 | `ctest -R gf_collector_smoke` |
| COLL-02 | COLL-01 | ReportEvent×5 | Size==4（环缓） | 同上 |
| COLL-03 | COLL-02 | Snapshot | 末条 LogicalFault | 同上 |
