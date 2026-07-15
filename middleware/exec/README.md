# exec

ARA-inspired **Execution Management** client (`gf_ara::exec`) — P1 最小 Process State Reporting。

| API | 说明 |
|-----|------|
| `ExecutionClient::Offer` | 注册进程名 → `kStarting` |
| `ReportExecutionState` | `kRunning` / `kTerminating` … |
| `GetState` / `ProcessName` | 查询 |

与 `phm` 闭环：进程报 Running 后由 `SupervisedEntity` 做 Alive/Deadline。

```bash
bash scripts/smoke_eu_stub.sh
```

Parent: [middleware/README.md](../README.md)
