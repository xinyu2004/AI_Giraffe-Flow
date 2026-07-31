# someip binding — trust cases

Smoke: `gf_someip_binding_smoke` · `middleware/bindings/someip/testcases/smoke_binding.cpp` · **active**（当前 stub 后端）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| SIP-01 | — | IsInitialized | false | `ctest -R gf_someip_binding_smoke` |
| SIP-02 | — | InitRuntime | initialized + BackendName | 同上 |
| SIP-03 | SIP-02 | Shutdown | !initialized | 同上 |
