# iceoryx binding — trust cases

Smoke: `gf_iox_binding_smoke` · `middleware/bindings/iceoryx/testcases/smoke_binding.cpp` · **active**（需 `GF_WITH_ICEORYX=ON`）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| IOX-01 | iceoryx 已链 | BackendName() | `"iceoryx"` | `ctest -R gf_iox_binding_smoke` |
| IOX-02 | IOX-01 | BackendLinked() | true | 同上 |
