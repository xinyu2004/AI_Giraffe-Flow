# sm — trust cases

Smoke: `gf_sm_fg_smoke` · `middleware/sm/testcases/smoke_fg.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| SM-01 | — | EnsureGroup MachineFG Running | GetState Running | `ctest -R gf_sm_fg_smoke` |
| SM-02 | SM-01 | Running↔Updating | 双向成功 | 同上 |
| SM-03 | Running | →Off；Off→Updating | Off 成功；Updating **非法** | 同上 |
| SM-04 | Off | →Running | 成功 | 同上 |
| SM-05 | Running | NotifyHealthFault | FaultCount≥1 | 同上 |
