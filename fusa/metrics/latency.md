# 参考延时表 — draft（ROADMAP T2）

用途：Safety Case / 架构评审的**可复现测量入口**，不是量产 ECU 合格判据。  
与 [isolation.md](isolation.md) 的关系：isolation 管「对不对」；本表管「多快」。说明见 [README.md](README.md)。

**预算口径：**「目标」列为 **SIL 主机参考预算**（engineering gate）。超出则查配置/回归；**不得**直接标为板级 ASIL 限值。板端 soak / ECU 限值 → **P3z**（假设 A-07）。

## 测量约定

| 项 | 约定 |
|----|------|
| 时钟 | OSAL monotonic（日志前缀 `t_ms=`）；Trajectory 用消息内 `timestamp_ns` |
| 环境 | SIL：`projects/oem_a/afc_with_uss` + iceoryx；主机 Linux |
| 样本 | 主链 verify：`GF_MP_TRAJ_COUNT=30`；PHM/EM 各跑对应 smoke 一次 |
| 产物 | `fusa/runs/measure_summary_*.json`（gitignore）；本表填汇总 |
| 脚本 | `bash fusa/scripts/measure_latency.sh`（**不**调用 `run_cases` / pack） |

## 最近快照

| 字段 | 值 |
|------|-----|
| 日期 (UTC) | 2026-07-31 |
| git | `60775b7` |
| 原始 JSON | `fusa/runs/measure_summary_20260731T065556Z.json`（本机） |

## 预算 / 实测表

| 路径 | 指标 | 目标（SIL 参考） | 测量方法 | 最近值 | 备注 |
|------|------|------------------|----------|--------|------|
| sensing→…→gateway | Trajectory **采样周期** p50 / p99 | p50 ∈ [90, 110] ms；p99 ≤ 120 ms（SKU period≈100 ms） | `run_sil_verify.sh` + `GF_MP_TRAJ_COUNT=30` | **100.6 / 100.8 ms**（n=30） | **不是** hop e2e |
| PHM Alive | 配置 period / timeout | = `phm.yaml`（100 ms / 300 ms） | `phm.yaml` + SIL-03 log | 与配置一致 | |
| PHM 故障检测 | FAULT begin → `DeadlineMissed` | ≤ timeout（**300 ms**） | `smoke_sil_phm_fault.sh` · `t_ms=` | **287 ms** | 必须 ≤ timeout |
| PHM 恢复（soft） | miss → `phm recovered` | ≤ **100 ms** | 同上（非 EM exit75） | **20 ms** | begin→recover **307 ms**（含检测窗） |
| EM relaunch | child exit → `relaunch` / spawn `relaunch=yes` | ≤ **50 ms**（daemon 时钟） | `smoke_sil_em_daemon.sh` · `t_ms=` | **0 ms / 1 ms** | 子进程 log 在 relaunch 后 `t_ms` 重置 |
| Collector ReportEvent | ring 首→末事件跨度（进程内） | ≤ **1 ms** | `gf_collector_smoke` · `t_us_span=` | **5 µs**（n=4） | 跨进程见 `GF_COLLECTOR_STORE` / COLL-X* |

## 如何更新

1. `bash fusa/scripts/measure_latency.sh`（需已 `compile_sil`）。  
2. 打开最新 `fusa/runs/measure_summary_*.json`，核对 PASS。  
3. 改本表「最近快照」与「最近值」；配置或 binding 变了注明 revision。  
4. 若实测持续越出「目标」列：先查回归，再评估是否放宽 SIL 参考预算（仍非 ECU 限）。
