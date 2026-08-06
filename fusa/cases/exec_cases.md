# exec — trust cases

Smokes:
- Client: `gf_exec_smoke`
- In-process EM: `gf_exec_em_smoke`
- OS EM daemon: `gf_em_daemon_smoke`

状态: **active**

## ExecutionClient

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| EXEC-01 | 未 Offer | Report Running | 失败 | `ctest -R gf_exec_smoke` |
| EXEC-02 | — | Offer | state Starting | 同上 |
| EXEC-03 | EXEC-02 | Report Running | state Running | 同上 |

## ExecutionManager（进程内账本）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| EM-01 | Reset | StartProcess | IsRegistered | `ctest -R gf_exec_em_smoke` |
| EM-02 | EM-01 | Client Offer→Running | EM ReportedState Running | 同上 |
| EM-03 | EM-02 | RequestRestart | count=1 + pending | 同上 |
| EM-04 | EM-03 | soft Offer/Running + Consume | pending clear | 同上 |

## EmDaemon（OS fork/exec）

| Case ID | 前置 | 步骤 | 期望 | 复现 |
|---------|------|------|------|------|
| EMD-01 | — | 写 fixture platform/launch | 文件就绪 | `ctest -R gf_em_daemon_smoke` |
| EMD-02 | EMD-01 | Load | topo：depends 前驱在前；phm restart 标志 | 同上 |
| EMD-03 | EMD-02 | StartAll | 子进程 spawn | 同上 |
| EMD-04 | EMD-03 | child exit 75 | relaunch；launches≥2 | 同上 |

SIL：`projects/oem_a/afc_with_uss/scripts/verify/smoke_sil_em_daemon.sh`（RouDi + `gf_em_daemon` + PHM fault→exit 75→relaunch）。
