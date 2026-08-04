# tsync — time sync lite（gPTP via linuxptp）

| API | Role |
|-----|------|
| `TimeSyncProvider::NowNs` | 同步域时间（已同步时含 offset）；否则 OSAL monotonic |
| `GetStatus` / `GetStatusDetail` | Synchronized + offset_ns |
| `ConfigureFromYaml` | `platform/tsync.yaml`：`backend: osal_monotonic \| linuxptp` |

**Board:** 运行 `ptp4l` / `phc2sys`；本模块用 `pmc` 读状态（不链 linuxptp 进镜像）。  
**SIL:** `backend: osal_monotonic` + `pretend_synchronized`.

Smoke: `gf_tsync_smoke`.

FuSa: [tsync_cases.md](../../fusa/cases/tsync_cases.md).
