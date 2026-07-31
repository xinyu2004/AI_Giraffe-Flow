# tsync — trust cases

Smoke: `gf_tsync_smoke` · `middleware/tsync/testcases/smoke_tsync.cpp` · **active**（无 gPTP）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| TSYNC-01 | — | NowNs 间隔采样 | 单调递增 | `ctest -R gf_tsync_smoke` |
| TSYNC-02 | 默认配置 | GetStatus | Synchronized（stub） | 同上 |
| TSYNC-03 | pretend_synchronized=false | GetStatus | NotSynchronized | 同上 |
