# phm — trust cases

Smoke: `gf_phm_alive_deadline_smoke` · `middleware/phm/testcases/smoke_alive_deadline.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| PHM-00 | — | exec Offer→Running | 成功 | `ctest -R gf_phm_alive_deadline_smoke` |
| PHM-01 | Configure 50/80 | Evaluate 无 Alive | AliveMissed | 同上 |
| PHM-02 | ReportAlive | Evaluate + 窗口内 | Ok；IsWithinDeadline | 同上 |
| PHM-03 | sleep>deadline | Evaluate；再 Alive | DeadlineMissed→Ok | 同上 |
| PHM-04 | — | ReportLogical false/true | LogicalFault→Ok | 同上 |
| PHM-05 | SetPaused | sleep>deadline | 仍 Ok | 同上 |
