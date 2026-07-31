# dds binding — trust cases

Smoke: `gf_dds_binding_smoke` · `middleware/bindings/dds/testcases/smoke_binding.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| DDS-01 | — | InitRuntime | 打印 backend | `ctest -R gf_dds_binding_smoke` |
| DDS-02 | Cyclone 构建时 | BackendName | cyclonedds（条件） | 同上 |
| DDS-03 | — | Publish Sample | true | 同上 |
| DDS-04 | DDS-03 | Take 轮询 | seq==7 | 同上 |
