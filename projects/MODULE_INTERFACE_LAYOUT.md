# 模块接口布局（project-only）

**已取消**顶层共享 + project 定制双轨。DBC 与 hpp **一律跟交付项目走**。

```text
projects/<oem>/<product>/
  oem/                 # DBC / manifest（车型相关，必不同）
  interfaces/          # 本项目实际使用的 io_types.hpp（外仓常只交这个）
  integration/         # wiring.yaml
  req.yaml
  project.yaml
  golden/              # 可选：本项目 compose 对照（主示范在 adc）
  reports/
```

| 规则 | 说明 |
|------|------|
| DBC | 只在 `oem/`；各 SKU 各自一份 |
| hpp | 只在本项目 `interfaces/`；外仓不可见源码时在此落盘 |
| 两项目 hpp 碰巧相同 | 复制即可；不必抽公共目录 |
| 平台 API | `middleware/`（ucm/diag/core）— 不是模块 IO |
| **Golden** | 本项目 `golden/gf.sor.json`：compose 的**正确答案快照**（回归 / CI）；主示范 [`adc/golden/`](adc/golden/)；说明见 [afc/README.md](afc/README.md#golden) |

集成入口：[afc/README.md](afc/README.md)
