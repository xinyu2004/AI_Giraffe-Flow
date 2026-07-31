# osal — trust cases

Smoke: `gf_osal_smoke` · `middleware/osal/testcases/smoke_osal.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| OSAL-01 | — | MonotonicNowNs；SleepMs(20) | t1 > t0 | `ctest -R gf_osal_smoke` |
| OSAL-02 | OSAL-01 | 测 delta | delta ≥ 10ms | 同上 |
