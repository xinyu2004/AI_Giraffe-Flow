# per — persistency skeleton (in-memory KV)

| API | Role |
|-----|------|
| `KeyValueStorage::Open` | 打开实例（进程内 stub） |
| `SetValue` / `GetValue` | KV；未 Open / 缺 key → `NotAvailable` |

Not SQLite. SKU 可裁剪：`req.runtime_modules` 含 `per` 时编入。

Smoke: `gf_per_smoke`（PER-01…03）.

FuSa: [per_cases.md](../../fusa/cases/per_cases.md).
