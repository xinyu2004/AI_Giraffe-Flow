# collector — Event Collector min-set (M3)

| API | Role |
|-----|------|
| `EventCollector::Configure` | `forward` / local ring (`max_entries`) |
| `ReportEvent` | phm / process / com → ring + log; `cp_dem` stub |
| `Snapshot` / `Clear` | Query / reset |

Not Classic DEM. Config: `platform/collector.yaml`.

Smoke: `gf_collector_smoke`.

Parent: [middleware/README.md](../README.md)

Trust cases: [collector_cases.md](../../docs/reports/trust-evidence/collector_cases.md).
