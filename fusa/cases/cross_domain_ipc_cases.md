# cross_domain_ipc — trust cases

Smoke: `gf_cross_domain_ipc_smoke` · `middleware/bindings/cross_domain_ipc/testcases/smoke_transport.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| XIPC-01 | — | FrameHeader | magic + size==12 | `ctest -R gf_cross_domain_ipc_smoke` |
| XIPC-02 | fork | Listen/Connect | 成功 | 同上 |
| XIPC-03 | XIPC-02 | SendPod/RecvPod | a==99 | 同上 |
| XIPC-04 | XIPC-03 | waitpid | child exit 0 | 同上 |
