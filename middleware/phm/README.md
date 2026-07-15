# phm

ARA-inspired **Platform Health Management** (`gf_ara::phm`) — P1 Alive / Deadline 本地监督。

| API | 说明 |
|-----|------|
| `SupervisedEntity::Configure` | alive_cycle_ms / deadline_ms |
| `ReportAlive` | 喂狗 |
| `Evaluate` | `kOk` / `kAliveMissed` / `kDeadlineMissed` |
| `SetPaused` | OTA/降级时暂停监督（UCM/SM 钩子） |

闭环 smoke：`gf_phm_alive_deadline_smoke`（先 `exec` Offer/Running，再 Alive→超时→恢复→Pause）。

```bash
bash scripts/smoke_eu_stub.sh
```

Parent: [middleware/README.md](../README.md)
