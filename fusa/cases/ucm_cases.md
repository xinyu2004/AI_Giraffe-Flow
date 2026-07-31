# ucm — trust cases

Smoke: `gf_ucm_package_manager_smoke` · `gf_ucm_ota_smoke` · `smoke_doip_ota.sh`

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| UCM-01…06 | — | PackageManager 状态机 | PASS | `ctest -R gf_ucm_package_manager_smoke` |
| UCM-OTA-01 | — | OtaOrchestrator success | unpause + SM Running | `ctest -R gf_ucm_ota_smoke` |
| UCM-OTA-02 | FORCE_FAIL | RunPackage fail | Collector `ota_failed` | 同上 |
| UCM-OTA-03 | — | PHM SetPaused API | available | 同上 |
