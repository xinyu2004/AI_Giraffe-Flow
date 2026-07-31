# 故障隔离场景索引 — draft（ROADMAP T2）

把「可复现隔离」钉到脚本与 Safety Goal。  
与 [latency.md](latency.md) 的关系：本表管 **PASS/FAIL 行为**；毫秒数只作引用。说明见 [README.md](README.md)。

| 场景 ID | 故障 | 期望可观察结果 | 脚本 / case | SG | 最近状态 |
|---------|------|----------------|-------------|-----|----------|
| ISO-PHM-01 | planning Alive 注入窗口 miss | `planning.log`：FAULT → AliveMissed·DeadlineMissed → `phm recovered`；gateway 仍收 Trajectory | `smoke_sil_phm_fault.sh` · SIL-03 | SG-02 | **PASS** 2026-07-31 · git `60775b7` · begin→miss **287 ms** · miss→recover **20 ms** |
| ISO-EM-01 | planning exit 75（PHM restart） | daemon relaunch；子进程 `em os_restart_exit`；链路恢复 | `smoke_sil_em_daemon.sh` · SIL-EM-02 | SG-01 | **PASS** 2026-07-31 · exit→relaunch **0 ms** · exit→spawn2 **1 ms** |
| ISO-EM-02 | EM 软重启账本 | RequestRestart → soft relaunch | `gf_exec_em_smoke` EM-03/04 | SG-01 | L1 矩阵覆盖（`run_cases`）；本轮未单独计时 |
| ISO-SM-01 | 非法 FG 迁移 | 拒绝 Off→Updating 等 | `gf_sm_fg_smoke` SM-03 | SG-03 | L1 矩阵覆盖；本轮未单独计时 |

## 复现

```bash
# 行为：含 SIL-03 / SIL-EM-02
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh

# 单场景
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_phm_fault.sh
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_em_daemon.sh

# 延时数字（可选，独立脚本）
bash fusa/scripts/measure_latency.sh
```

追溯见 [../safety-case/traceability.md](../safety-case/traceability.md)。
