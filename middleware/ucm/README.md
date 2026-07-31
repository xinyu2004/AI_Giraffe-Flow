# middleware/ucm

ARA-inspired **Update and Configuration Management** (`gf_ara::ucm`).

| 组件 | 行为 |
|------|------|
| `PackageManager` | Idle→Transfer→Process→Activate / Rollback 状态机 |
| `OtaOrchestrator` | SM `Updating` + pause hook → PackageManager → Collector；失败可 Rollback |

失败注入：`GF_UCM_FORCE_FAIL=1` 或 `artifact_path` 含 `FORCE_FAIL` → Collector `ucm/ota_failed`。

**不做**真 RAUC 刷写（后端仍 stub；真板见 P3z）。

与 PHM：`SetPaused` 由编排 hook / 各进程在 Updating 窗调用（见 [PHM_OTA_PAUSE.md](../../docs/zh/operations/PHM_OTA_PAUSE.md)）。

```bash
ctest --test-dir build -R 'gf_ucm_' --output-on-failure
```

Parent: [middleware/README.md](../README.md) · FuSa: [ucm_cases.md](../../fusa/cases/ucm_cases.md).
