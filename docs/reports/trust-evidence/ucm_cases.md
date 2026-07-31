# ucm — trust cases

Smoke: `gf_ucm_package_manager_smoke` · `middleware/ucm/testcases/smoke_package_manager.cpp` · **skeleton**（状态机 stub，非量产 OTA）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| UCM-01 | 未 Init | StartTransfer | 失败 | `ctest -R gf_ucm_package_manager_smoke` |
| UCM-02 | — | Initialize | 成功 | 同上 |
| UCM-03 | Init | StartTransfer | Transferring | 同上 |
| UCM-04 | — | ProcessSwPackage | Processing | 同上 |
| UCM-05 | — | Activate | Activated | 同上 |
| UCM-06 | — | Rollback | RolledBack | 同上 |
