# Assumptions of use — draft

未满足下列假设时，本仓 FuSa 证据**不能**直接外推为整车 ASIL 结论。

| ID | 假设 | 状态 |
|----|------|------|
| A-01 | 目标 ECU 提供满足 OSAL 契约的时钟、进程、存储原语 | open |
| A-02 | 通信后端（iceoryx/SOME/IP/DDS）按所选 binding 正确部署与配额 | open |
| A-03 | OEM 算法以独立进程/库接入，仅通过服务名 pub/sub，不绕过 EM 拓扑 | open |
| A-04 | SIL 证据在「同配置 compose 产物」下复现；配置漂移需重新跑 `run_cases` / pack | open |
| A-05 | debug-path（GMT / Inject / Tag→MCAP）在 production profile 可关闭且不参与 Safety Case 默认证据集 | open |
| A-06 | 证书、工具鉴定、HARA 由项目安全流程另册完成；本仓只提供可引用技术证据 | open |

更新假设时同步检查 [traceability.md](traceability.md)。
