# collector — trust cases

Smoke:

- in-proc: `gf_collector_smoke` · `middleware/collector/testcases/smoke_collector.cpp`
- cross-proc store: `gf_collector_xproc_smoke` · `smoke_collector_xproc.cpp`

**active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| COLL-01 | Clear | Configure local_store max=4 | 配置生效 | `ctest -R gf_collector_smoke` |
| COLL-02 | COLL-01 | ReportEvent×5 | Size==4（环缓） | 同上 |
| COLL-03 | COLL-02 | Snapshot | 末条 LogicalFault | 同上 |
| COLL-X01 | `GF_COLLECTOR_STORE` | 两子进程各 ReportEvent | 共享 NDJSON ≥2 行 | `ctest -R gf_collector_xproc_smoke` |
| COLL-X02 | COLL-X01 | 读 store | 可见 AliveMissed 与 LogicalFault | 同上 |

跨进程：`EventCollector::ReportEvent` 在设置 `GF_COLLECTOR_STORE` 时追加 flock NDJSON（非 Classic DEM / 非 iceoryx）。  
SIL：`smoke_sil_sm_fg.sh` 写入 `runtime/collector/events.ndjson`。
