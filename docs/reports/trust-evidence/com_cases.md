# com — trust cases

Smoke: `gf_com_loopback_smoke` · `middleware/com/testcases/smoke_loopback_event.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| COM-01 | LoopbackBus Clear | Publish EgoMotion | Publish true | `ctest -R gf_com_loopback_smoke` |
| COM-02 | COM-01 | Take | 载荷与 Publish 一致 | 同上 |
| COM-03 | COM-02 | 二次 Take | empty optional | 同上 |
