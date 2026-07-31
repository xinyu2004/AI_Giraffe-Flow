# diag — trust cases

Smoke: `gf_diag_doip_smoke` · `gf_doip_session_smoke` · `smoke_doip_ota.sh`

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| DIAG-01…05 | — | 进程内 DoipStack | PASS | `ctest -R gf_diag_doip_smoke` |
| DOIP-S01 | — | TCP listen (ephemeral) | PASS | `ctest -R gf_doip_session_smoke` |
| DOIP-S02 | server | RoutingActivation | PASS | 同上 |
| DOIP-S03 | activated | TesterPresent | 0x7E | 同上 |
| DOIP-S04 | — | RoutineControl OTA success | SM Running | 同上 |
| DOIP-S05 | FORCE_FAIL | OTA fail | Collector `ota_failed` | 同上 |
| DOIP-LIVE | `gf_doip_ota_server` | Python DoipClient | Activate OK | `smoke_doip_ota.sh` |
