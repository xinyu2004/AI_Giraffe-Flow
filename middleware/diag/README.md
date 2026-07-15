# middleware/diag

ARA-inspired **Diagnostics** (`gf_ara::diag`) — **DoIP-first** P1 stub（无真台架）。

| API | P1 行为 |
|-----|---------|
| `DoipStack::Initialize` / `Shutdown` | 进程内开关；可被诊断探针调用 |
| `RequestRoutingActivation` | 非 0 目标 → `kSuccess` |
| `SendDiagnosticMessage` | TesterPresent(`0x3E`) 回 `0x7E`；其它回 NRC |
| `ReceiveDiagnosticMessage` | 取上次发送的 stub 应答 |

真 ISO 13400 TCP/UDP 与 UDS 会话属后置；P1 验收为 **stub 可链 + Initialize/Shutdown 探针**。

```bash
bash scripts/smoke_eu_stub.sh
```

Parent: [middleware/README.md](../README.md)
