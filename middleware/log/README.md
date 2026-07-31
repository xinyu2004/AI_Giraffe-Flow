# log — log lite (stdout/stderr)

| API | Role |
|-----|------|
| `Logger::Configure` / `ConfigureFromYaml` | `default_level` + per-context levels（对齐 `platform/log.yaml`） |
| `Logger::Info/Error/...` | 按级别过滤；ERROR+→stderr，其余→stdout |

Not DLT. Env: `GF_LOG_LEVEL` 覆盖默认级别。

Smoke: `gf_log_smoke`（LOG-01…03）.

FuSa: [log_cases.md](../../fusa/cases/log_cases.md).

Parent: [middleware/README.md](../README.md).
