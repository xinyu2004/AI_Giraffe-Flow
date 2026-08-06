# middleware/ucm

ARA-inspired **Update and Configuration Management** (`gf_ara::ucm`).

| 组件 | 行为 |
|------|------|
| `PackageManager` | Idle→Transfer→Process→Activate / Rollback 状态机；SIL 校验产物 magic（`GFSW` / `PK` / `RAUC`） |
| `OtaOrchestrator` | SM `Updating` + pause hook → PackageManager → Collector；失败可 Rollback |

**入口：** GMT OTA（DoIP/UDS）或进程内 smoke。配置：`platform/ucm.yaml`（编排策略）+ `diag.yaml`（传输 SID / 时序）。见 [DOIP_OTA.md](../../docs/zh/operations/DOIP_OTA.md)。

失败注入：`GF_UCM_FORCE_FAIL=1` 或 `artifact_path` 含 `FORCE_FAIL` → Collector `ucm/ota_failed`。

**不做**真 RAUC 刷写（后端仍 stub；真板见 P3z）。选型史：[OTA_SPIKE.md](../../docs/zh/operations/OTA_SPIKE.md)。

与 PHM：`SetPaused` 由编排 hook / 各进程在 Updating 窗调用（见 [PHM_OTA_PAUSE.md](../../docs/zh/operations/PHM_OTA_PAUSE.md)）。

```bash
ctest --test-dir build -R 'gf_ucm_' --output-on-failure
bash projects/oem_a/afc_with_uss/scripts/verify/smoke_doip_ota.sh
```

Parent: [middleware/README.md](../README.md) · FuSa: [ucm_cases.md](../../fusa/cases/ucm_cases.md).
