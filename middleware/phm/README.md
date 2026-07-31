# phm — Platform Health Management

ARA-inspired **Platform Health Management** (`gf_ara::phm`) — Alive / Deadline / Logical.

| API | Role |
|-----|------|
| `ReportAlive` | 喂狗 |
| `ReportLogical` | Logical health (M2) |
| `Evaluate` | `kOk` / `kAliveMissed` / `kDeadlineMissed` / `kLogicalFault` |
| `SetPaused` | OTA / SM Updating |

`platform/phm.yaml` `on_failure`:

| 值 | 行为 |
|----|------|
| `log` | 仅日志 + Collector |
| `notify_sm` | Collector + `sm::NotifyHealthFault`（可选进 Updating） |
| `restart` | Collector + EM：`GF_EM_MANAGED` 时 exit 75 由 `gf_em_daemon` relaunch；否则 soft relaunch |

Smoke: `gf_phm_alive_deadline_smoke`（`testcases/smoke_alive_deadline.cpp`）。FuSa cases: [phm_cases.md](../../fusa/cases/phm_cases.md)。

Parent: [middleware/README.md](../README.md)
