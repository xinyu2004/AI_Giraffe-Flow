# per — persistency lite（file-backed dual-slot KV）

| API | Role |
|-----|------|
| `KeyValueStorage::Open` | 打开实例；从 `GF_PER_DIR/<instance>.kv.{a,b}` 加载较新槽 |
| `SetValue` / `GetValue` | KV；写后原子落盘到另一槽 + 世代号 |
| `ClearValues` / `Close` | 清空并持久化 / 关闭 |

**Not SQLite.** 环境变量 `GF_PER_DIR`（默认 `.`）。SKU：`req.runtime_modules` 含 `per`。

Smoke: `gf_per_smoke`（PER-01…04，含跨 Open 持久化）.

FuSa: [per_cases.md](../../fusa/cases/per_cases.md).
