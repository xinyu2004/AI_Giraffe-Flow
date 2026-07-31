# per — trust cases

Smoke: `gf_per_smoke` · `middleware/per/testcases/smoke_per.cpp` · **active**（进程内 KV stub）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| PER-01 | — | Open(instance) | Ok | `ctest -R gf_per_smoke` |
| PER-02 | PER-01 | SetValue / GetValue | 往返一致 | 同上 |
| PER-03 | PER-01 | GetValue(missing) | Err NotAvailable | 同上 |
