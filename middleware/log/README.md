# log — log lite + DLT sink

| API / 工具 | Role |
|------------|------|
| `Logger::Configure` / `ConfigureFromYaml` | `default_level` · `sinks` · `contexts` · `dlt.app_id` |
| `Logger::Info/...` | console / file / **dlt** |
| `DltSink` | COVESA libdlt；**≤64 contexts**；无 `/tmp/dlt` 不 `register`（不阻塞） |
| `gf_dlt_log` | Host/脚本打一条 Info（`run_sil` `host_info`） |

**Sinks（gf-config）：** `console` · `file` · `dlt`  
**Env：** `GF_LOG_LEVEL` · `GF_LOG_FILE`/`GF_LOG_DIR` · `GF_DLT_APP_ID`（per-process 4 字符）

**启动顺序（SIL）：** `dlt-daemon` → Host (`gf_dlt_log`) → RouDi → apps  
**APP ID 例：** `HOST` · `GATE` · `FCM_` · `USS_` · `PLAN`

**有界内存（log 子集）：**
- DltSink context 表硬上限 64（溢出复用 `OVFL`）
- 无 daemon 时不进入 libdlt 重试等待
- GMT DLT 客户端 pending 队列有上限

计划：[docs/zh/operations/DLT_PLAN.md](../../docs/zh/operations/DLT_PLAN.md)

Smoke: `gf_log_smoke`（LOG-01…04）。

FuSa: [log_cases.md](../../fusa/cases/log_cases.md).

Parent: [middleware/README.md](../README.md).
