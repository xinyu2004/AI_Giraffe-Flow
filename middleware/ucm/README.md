# middleware/ucm

ARA-inspired **Update and Configuration Management** (`gf_ara::ucm`) — P1 PackageManager 状态机 stub。

| 状态 | 转移 |
|------|------|
| `kIdle` | `Initialize` |
| `kTransferring` | `StartTransfer` |
| `kProcessing` | `ProcessSwPackage` |
| `kActivated` | `Activate` |
| `kRolledBack` | `Rollback` |

## 与 SM / PHM 的钩子（文档约定，P1）

OTA 期间建议：

1. **SM**：切 degraded / 限制非必要进程（`middleware/sm` 仍可后置实现）  
2. **PHM**：对受影响实体调用 `SupervisedEntity::SetPaused(true)`，避免误报 Deadline  
3. Activate 成功后再 `SetPaused(false)` 并 `ReportAlive`

无真 OTA 后端（RAUC/OSTree 候选见依赖评估）；P1 只保证 **可链接 + 状态机可测**。

```bash
bash scripts/smoke_eu_stub.sh
```

Parent: [middleware/README.md](../README.md)
