# tsync — time sync skeleton

| API | Role |
|-----|------|
| `TimeSyncProvider::NowNs` | 委托 OSAL monotonic |
| `GetStatus` | stub：默认同步；可 `pretend_synchronized=false` |

Not gPTP. SKU 可裁剪：`req.runtime_modules` 含 `tsync` 时编入。

Smoke: `gf_tsync_smoke`（TSYNC-01…03）.

FuSa: [tsync_cases.md](../../fusa/cases/tsync_cases.md).
