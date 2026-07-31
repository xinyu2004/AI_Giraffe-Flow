# diag — trust cases

Smoke: `gf_diag_doip_smoke` · `middleware/diag/testcases/smoke_doip.cpp` · **skeleton**（DoIP stub，非量产 UDS 栈）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| DIAG-01 | 未 Init | Shutdown | 失败 | `ctest -R gf_diag_doip_smoke` |
| DIAG-02 | — | Initialize | 成功 | 同上 |
| DIAG-03 | Init | RoutingActivation | Success | 同上 |
| DIAG-04 | — | TesterPresent 收发 | 0x7E 响应 | 同上 |
| DIAG-05 | — | Shutdown | 成功 | 同上 |
