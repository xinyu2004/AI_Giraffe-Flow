# middleware/diag

ARA-inspired **Diagnostics** (`gf_ara::diag`) — **DoIP session**（SIL / 假 board；非量产 UDS 全栈）。

| API | 行为 |
|-----|------|
| `DoipStack::*` | 进程内 stub（TesterPresent 回声）— 保留 DIAG-01…05 |
| `DoipTcpServer` / `DoipTcpClient` | ISO 13400-2 子集：RoutingActivation + DiagnosticMessage over TCP |
| `gf_doip_ota_server` | 监听 `GF_DOIP_PORT`（默认 13400）；UDS `0x31` 例程 `0xF100` → UCM OTA |

RoutineControl（SIL）：

| UDS | 含义 |
|-----|------|
| `31 01 F1 00` + `id\|path` | start OTA → `OtaOrchestrator::RunPackage` |
| `31 03 F1 01` | 进度 percent |

```bash
ctest --test-dir build -R 'gf_diag_doip_smoke|gf_doip_session_smoke' --output-on-failure
bash scripts/verify/oem_a_afc_with_uss/smoke_doip_ota.sh
```

Parent: [middleware/README.md](../README.md) · FuSa: [diag_cases.md](../../fusa/cases/diag_cases.md).
