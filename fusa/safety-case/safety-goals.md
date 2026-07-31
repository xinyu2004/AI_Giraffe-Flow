# Safety goals — living draft

> **平台级候选安全目标**（middleware 可支撑的行为），非整车 HARA 结论。  
> ASIL 列保持 **TBD**，待项目 HARA；编号与 [traceability.md](traceability.md) 中 SR 对齐。

| SG | 意图 | 初步 ASIL | 分解 SR | 主证据入口 |
|----|------|-----------|---------|------------|
| SG-01 | 关键进程异常退出后，按策略可检测并可重启 / 降级，不静默丢失监督 | TBD | SR-01.1…01.4 | EM/EMD · SIL-EM-02 · ISO-EM-01 |
| SG-02 | Alive / Deadline 监督在配置窗口内可检出 miss，并在恢复后回到健康；故障隔离时旁路可继续 | TBD | SR-02.1…02.5 | PHM-* · SIL-03 · ISO-PHM-01 |
| SG-03 | 功能组状态机非法迁移被拒绝；健康故障可通知 SM | TBD | SR-03.1…03.4 | SM-* · ISO-SM-01 |
| SG-04 | 平台故障事件可被 Collector 记录（本地环），供事后分析 | TBD | SR-04.1…04.3 | COLL-* |
| SG-05 | 量产配置下调试通路可关闭，主链不依赖主机工具 | TBD | SR-05.1…05.2 | **open**（ROADMAP T4） |

## 覆盖状态（相对本仓证据）

| SG | L1 | L3 fusa | Isolation | 备注 |
|----|----|---------|-----------|------|
| SG-01 | ✅ | ✅ | ✅ | LAT relaunch 已测；SIL 预算 ≤50 ms |
| SG-02 | ✅ | ✅ | ✅ | LAT miss/recover 已测 |
| SG-03 | ✅ | ✅ SIL-SM-01 | ✅ | |
| SG-04 | ✅ COLL-X* | ✅（随 SIL-SM-01） | ✅ | 共享 NDJSON store |
| SG-05 | ✅ L2 | ✅ SIL-T4 | — | `GF_FUSA_T4=1` |

## 非目标（本阶段）

- 感知 / 规划功能正确性（OEM 算法）
- 整车横向 / 纵向控制 ASIL 分配
- 工具链 T2/T3 鉴定结论、证书签字
- 把 GMT / Inject / Tag→MCAP 当作板级 ASIL 证据
