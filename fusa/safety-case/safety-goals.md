# Safety goals — draft

> 下列为 **平台级候选安全目标**（middleware 可支撑的行为），非整车 HARA 结论。  
> 编号稳定后进入 [traceability.md](traceability.md)。

| SG | 意图（候选） | 初步 ASIL（待 HARA） | 相关机制 |
|----|--------------|----------------------|----------|
| SG-01 | 关键进程异常退出后，按策略可检测并可重启 / 降级，不静默丢失监督 | TBD | EM relaunch · PHM · OSAL process |
| SG-02 | Alive / Deadline 监督在配置窗口内可检出 miss，并在恢复后回到健康 | TBD | PHM SupervisedEntity · SIL-03 |
| SG-03 | 功能组状态机非法迁移被拒绝；健康故障可通知 SM | TBD | sm · PHM notify |
| SG-04 | 平台故障事件可被 Collector 记录（本地环），供事后分析 | TBD | collector |
| SG-05 | 量产配置下调试通路可关闭，主链不依赖主机工具 | TBD | production profile（ROADMAP T4） |

## 非目标（本阶段）

- 感知/规划功能正确性（OEM 算法）
- 整车横向/纵向控制 ASIL 分配
- 工具链 T2/T3 鉴定结论
