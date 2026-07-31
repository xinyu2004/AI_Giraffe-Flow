# log — trust cases

Smoke: `gf_log_smoke` · `middleware/log/testcases/smoke_log.cpp` · **active**

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| LOG-01 | Configure INFO | Info | 允许 Info | `ctest -R gf_log_smoke` |
| LOG-02 | contexts phm=DEBUG | Debug(phm) | 允许 | 同上 |
| LOG-03 | ConfigureFromYaml | 读 default_level+contexts | WARN / exec=INFO | 同上 |

SIL：`platform_sil` 加载 `platform/log.yaml`；`on_failure: log` 时写 `log: [ERROR] phm …`。
