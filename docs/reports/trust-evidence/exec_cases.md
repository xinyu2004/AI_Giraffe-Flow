# exec — trust cases

Smoke: `gf_exec_smoke` · `middleware/exec/testcases/smoke_exec.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| EXEC-01 | 未 Offer | Report Running | 失败 | `ctest -R gf_exec_smoke` |
| EXEC-02 | — | Offer | state Starting | 同上 |
| EXEC-03 | EXEC-02 | Report Running | state Running | 同上 |
