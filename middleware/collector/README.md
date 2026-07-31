# collector — Event Collector min-set (M3)

| API | Role |
|-----|------|
| `EventCollector::Configure` | `forward` / local ring (`max_entries`) |
| `ReportEvent` | phm / process / com → ring + log；可选 `GF_COLLECTOR_STORE` 跨进程 NDJSON；`cp_dem` stub |
| `Snapshot` / `Clear` | Query / reset |

Not Classic DEM. Config: `platform/collector.yaml`.

Env:

| 变量 | 含义 |
|------|------|
| `GF_COLLECTOR_STORE` | 若设置路径，每次 `ReportEvent` flock 追加一行 NDJSON（跨进程证据） |

Smokes: `gf_collector_smoke` · `gf_collector_xproc_smoke`.

Parent: [middleware/README.md](../README.md)

FuSa cases: [collector_cases.md](../../fusa/cases/collector_cases.md).
