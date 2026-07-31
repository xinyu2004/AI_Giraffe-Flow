# phm — Platform Health Management

ARA-inspired **Platform Health Management** (`gf_ara::phm`) — Alive / Deadline / Logical.

| API | Role |
|-----|------|
| `ReportAlive` | 喂狗 |
| `ReportLogical` | Logical health (M2) |
| `Evaluate` | `kOk` / `kAliveMissed` / `kDeadlineMissed` / `kLogicalFault` |
| `SetPaused` | OTA / SM Updating |

`platform/phm.yaml` `on_failure`: `log` \| `notify_sm`（→ `gf_ara::sm::NotifyHealthFault` + Collector）。

Smoke: `gf_phm_alive_deadline_smoke`（`testcases/smoke_alive_deadline.cpp`）。Trust cases: [phm_cases.md](../../docs/reports/trust-evidence/phm_cases.md)。

Parent: [middleware/README.md](../README.md)
