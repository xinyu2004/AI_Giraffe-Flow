# collector — Event Collector + DEM-lite

Not Classic DEM. PHM/UCM/process events → debounce → FDC-lite → confirmed DTC → `gf_ara::per` (instance `dtc`).

| API | Role |
|-----|------|
| `ReportEvent` | 环缓 + DEM 路径（需 `dtc_map`） |
| `NotifyOperationCycle` | 老化 tick |
| `ListDtcs` / `ClearDtc` / `SetDtcControlEnabled` | 供 UDS 0x19 / 0x14 / 0x85 |
| `GetFreezeFrame` | 冻结帧（confirmed 时采样） |

Config: `platform/collector.yaml`. Persist: `GF_PER_DIR` + module `per`.

Smoke: `gf_collector_smoke` · `gf_dem_lite_smoke`.
