# PHM Alive 与 OTA Pause 的关系（P2 X-4）

> 配套：`middleware/phm` · `platform/phm.yaml` · `platform/ucm.yaml`

## 结论（先读）

| 模式 | PHM 行为 | 谁触发 |
|------|----------|--------|
| 正常运行 | 周期 `ReportAlive`；超时 → `AliveMissed` / `DeadlineMissed` | 各进程本地 `SupervisedEntity` |
| **OTA / 更新窗口** | `SetPaused(true)` → Evaluate 恒为 `kOk`（不判超时） | UCM 激活前 / SM 进入更新 FG |
| 更新结束 | `SetPaused(false)` → 恢复监督；建议立刻再 `ReportAlive` | UCM 完成或回滚 |

P2 **不做**真台架 OTA；`ucm.yaml` 仍是空壳。Pause API 已在 `SupervisedEntity`，smoke `gf_phm_alive_deadline_smoke` 覆盖「暂停期间不报 DeadlineMissed」。

## 与主链 SIL

- 多进程脚本设 `GF_PLATFORM_DIR=…/platform`，gateway / planning 读 `exec.yaml` + `phm.yaml`。
- `GF_PHM_FAULT_INJECT_MS`：planning 故意停 Alive 一段时间，验证 miss → recover（**不是** OTA Pause）。
- OTA Pause 与 fault inject 正交：Pause 是策略豁免；fault inject 是测试缺狗。

## 后续（P3）

UCM 真后端激活包时：SM 切状态 → 各 supervised entity Pause → 更新 → Unpause + Alive。
