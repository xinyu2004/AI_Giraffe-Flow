# Assumptions of use — living draft

未满足下列假设时，本仓 FuSa 证据**不能**直接外推为整车 ASIL 结论。  
更新时同步检查 [traceability.md](traceability.md) 与 [item-definition.md](item-definition.md)。

| ID | 假设 | 影响 SG | 状态 | 备注 |
|----|------|---------|------|------|
| A-01 | 目标 ECU 提供满足 OSAL 契约的时钟、进程、存储原语 | SG-01 · SG-02 · SG-04 | open | SIL 用主机 POSIX 近似；板端需复测 |
| A-02 | 通信后端（iceoryx/SOME/IP/DDS）按所选 binding 正确部署与配额 | 支撑链 | open | L1 binding smoke + SIL-01/02/06 部分覆盖 |
| A-03 | OEM 算法以独立进程/库接入，仅通过服务名 pub/sub，不绕过 EM 拓扑 | SG-01 | open | 项外软件约束 |
| A-04 | SIL 证据在「同配置 compose 产物」下复现；配置漂移需重新跑 `run_cases` / pack | 全部 | **演示中** | 见 `sil_verify_cases`「最近复现」与 `measure_latency` revision |
| A-05 | debug-path（GMT / Inject / Tag→MCAP）在 production-release 可关闭且不参与默认证据集 | SG-05 | **演示中** | SIL-T4 / `smoke_production_profile.sh`；SIL-DBG-* 仅证「开得了」 |
| A-06 | 证书、工具鉴定、HARA 由项目安全流程另册完成；本仓只提供可引用技术证据 | 全部 | open | 政策硬边界 |

## 操作含义

- 换 SKU / binding / `phm.yaml` period：重跑 `GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh`，并视需要 `measure_latency.sh`。  
- 引用本仓证据时写明 **git revision** 与 case 日志 / pack MANIFEST。  
- 不得将 SIL 主机数字直接标为量产 ECU 合格限。
