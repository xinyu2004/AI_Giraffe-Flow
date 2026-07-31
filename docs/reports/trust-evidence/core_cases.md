# core — trust cases

Smoke: `gf_core_smoke` · 源码: `middleware/core/testcases/smoke_result.cpp` · 状态: **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| CORE-01 | — | `Result<int>::Ok(42)` | HasValue && Value==42 | `ctest -R gf_core_smoke` |
| CORE-02 | — | `Result<int>::Err(kNotAvailable)` | !HasValue && Error | 同上 |
| CORE-03 | — | `Result<void>` Ok/Err | Ok 有值、Err Busy | 同上 |
| CORE-04 | — | `ToString(kTimeout)` | `"Timeout"` | 同上 |
