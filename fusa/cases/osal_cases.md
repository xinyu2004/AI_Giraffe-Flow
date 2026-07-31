# osal — trust cases

Smoke:

- clock/thread: `gf_osal_smoke` · `middleware/osal/testcases/smoke_osal.cpp`
- process: `gf_osal_process_smoke` · `middleware/osal/testcases/smoke_process.cpp`

**active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| OSAL-01 | — | MonotonicNowNs；SleepMs(20) | t1 > t0 | `ctest -R gf_osal_smoke` |
| OSAL-02 | OSAL-01 | 测 delta | delta ≥ 10ms | 同上 |
| OSAL-P01 | — | SpawnProcess(`/bin/true`) | 有效 ProcessId | `ctest -R gf_osal_process_smoke` |
| OSAL-P02 | OSAL-P01 | WaitProcess blocking | exited 0 | 同上 |
| OSAL-P03 | — | Spawn `/bin/sleep 30` + Wait nonblocking | still running | 同上 |
| OSAL-P04 | OSAL-P03 | TerminateProcess + reap | 非 still running | 同上 |
| OSAL-P05 | — | SpawnProcess 空 executable | kInvalidProcessId | 同上 |
