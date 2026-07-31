# Traceability — SG → SR → 设计 → 验证

> **状态：** living（SG-01…04 已接到现有 L1/L3；SG-05 / production profile 仍开）。  
> **范围：** 平台中间件可支撑的行为；非整车 HARA 结论，**不声称** ASIL 已认证。  
> **政策：** [../POLICY.md](../POLICY.md) · 目标 [safety-goals.md](safety-goals.md) · 假设 [assumptions.md](assumptions.md)

## 图例

| 符号 | 含义 |
|------|------|
| SG | 平台级安全目标（候选） |
| SR | 安全需求（由 SG 分解；本仓可验证的行为句） |
| L1 / L2 / L3 | 见 [../cases/README.md](../cases/README.md) |
| ISO-* | [../metrics/isolation.md](../metrics/isolation.md) 场景 |
| LAT | [../metrics/latency.md](../metrics/latency.md) 参考延时（支撑评审，非合格判据） |

**不进默认证据集：** GMT · Observability Tag→MCAP · Inject（debug-path，见 L3 SIL-DBG-*）。

---

## SG-01 — 进程异常可检测并可按策略重启 / 降级

| 字段 | 内容 |
|------|------|
| 意图 | 关键进程异常退出后不静默丢失监督；可 relaunch / soft restart |
| 假设 | A-01 · A-03 · A-04 |
| 设计 / 机制 | `middleware/exec` ExecutionManager；`gf_em_daemon` + `platform/em_launch.yaml`；OSAL `SpawnProcess`；PHM `on_failure: restart` → exit **75** |
| 源码锚点 | `middleware/exec/` · `middleware/osal/`（process）· `scripts/verify/.../smoke_sil_em_daemon.sh` |

### 安全需求

| SR | 需求句 | 验证 |
|----|--------|------|
| SR-01.1 | EM 账本可登记进程，并完成 Offer→Running 状态上报 | EM-01 · EM-02 |
| SR-01.2 | `RequestRestart` 后 soft relaunch 可清除 pending | EM-03 · EM-04 · SIL-EM-01 · ISO-EM-02 |
| SR-01.3 | OS daemon 按拓扑 Spawn；子进程 exit 75 触发 relaunch（launches≥2） | EMD-01…04 · OSAL-P01…P05 · SIL-EM-02 · ISO-EM-01 |
| SR-01.4 | relaunch 后主链仍可观察到 Trajectory（集成） | SIL-EM-02 |

### 证据索引

| 层 | ID / 路径 |
|----|-----------|
| L1 | [exec_cases.md](../cases/exec_cases.md) EXEC-* · EM-* · EMD-* · [osal_cases.md](../cases/osal_cases.md) OSAL-P* |
| L3 | [sil_verify_cases.md](../cases/sil_verify_cases.md) SIL-EM-01 · SIL-EM-02 |
| Isolation | ISO-EM-01 · ISO-EM-02 |
| Latency | EM relaunch：**0 ms / 1 ms**（daemon 时钟；见 latency.md） |

**缺口：** 板端 soak / 多故障叠加尚未纳入；LAT 目标预算仍 TBD。

---

## SG-02 — Alive / Deadline 监督可检出 miss 并可恢复健康

| 字段 | 内容 |
|------|------|
| 意图 | 配置窗口内检出 AliveMissed / DeadlineMissed；soft 恢复后回到健康；隔离故障进程时旁路仍可跑 |
| 假设 | A-01 · A-04 |
| 设计 / 机制 | `middleware/phm` SupervisedEntity；`phm.yaml` period/timeout；SIL 注入 `GF_PHM_FAULT_MS` |
| 源码锚点 | `middleware/phm/` · `smoke_sil_phm_fault.sh` |

### 安全需求

| SR | 需求句 | 验证 |
|----|--------|------|
| SR-02.1 | 无 Alive 时 Evaluate 报告 AliveMissed | PHM-01 |
| SR-02.2 | 窗口内 Alive → Ok；超时 → DeadlineMissed，再 Alive → Ok | PHM-02 · PHM-03 |
| SR-02.3 | LogicalFault 可置位与清除 | PHM-04 |
| SR-02.4 | Paused 时不因超时误报 | PHM-05 |
| SR-02.5 | SIL：planning 注入 miss 后 FAULT→recover；gateway 仍收 Trajectory | SIL-03 · ISO-PHM-01 |

### 证据索引

| 层 | ID / 路径 |
|----|-----------|
| L1 | [phm_cases.md](../cases/phm_cases.md) PHM-00…05 |
| L3 | SIL-03 |
| Isolation | ISO-PHM-01 |
| Latency | begin→DeadlineMissed **287 ms**（≤ timeout 300 ms）；miss→recover **20 ms** |

**缺口：** hop e2e 延时未打点；多 SE 并发监督矩阵未建。

---

## SG-03 — 功能组状态机合法迁移；健康故障可通知 SM

| 字段 | 内容 |
|------|------|
| 意图 | 非法 FG 迁移被拒绝；健康故障可 `NotifyHealthFault` |
| 假设 | A-04 |
| 设计 / 机制 | `middleware/sm` StateClient / FG；PHM→SM 通知路径（库级） |
| 源码锚点 | `middleware/sm/` · `gf_sm_fg_smoke` |

### 安全需求

| SR | 需求句 | 验证 |
|----|--------|------|
| SR-03.1 | EnsureGroup → Running 成功 | SM-01 |
| SR-03.2 | Running↔Updating 合法双向 | SM-02 |
| SR-03.3 | Off→Updating 等非法迁移失败 | SM-03 · ISO-SM-01 |
| SR-03.4 | Off→Running 成功；Running 下 NotifyHealthFault 计数增加 | SM-04 · SM-05 |
| SR-03.5 | SIL：uss（notify_sm）miss → `sm: health_fault`；gateway Trajectory 仍在 | SIL-SM-01 · ISO-SM-02 |

### 证据索引

| 层 | ID / 路径 |
|----|-----------|
| L1 | [sm_cases.md](../cases/sm_cases.md) SM-01…05 |
| L3 | [sil_verify_cases.md](../cases/sil_verify_cases.md) **SIL-SM-01** |
| Isolation | ISO-SM-01 · **ISO-SM-02** |

**缺口：** 多 FG / 跨进程 SM daemon 仍 out of scope（M1）。

---

## SG-04 — 平台故障事件可被 Collector 记录

| 字段 | 内容 |
|------|------|
| 意图 | 本地环可配置、可 Snapshot；供事后分析（非主机工具） |
| 假设 | A-01 · A-04 |
| 设计 / 机制 | `middleware/collector` local_store ring；可选 `cp_dem` stub 转发 |
| 源码锚点 | `middleware/collector/` · `gf_collector_smoke` |

### 安全需求

| SR | 需求句 | 验证 |
|----|--------|------|
| SR-04.1 | Configure local_store 容量生效 | COLL-01 |
| SR-04.2 | 超量 ReportEvent 保持环长（FIFO） | COLL-02 |
| SR-04.3 | Snapshot 可见末条事件类型 | COLL-03 |
| SR-04.4 | 两进程 ReportEvent 写入同一 `GF_COLLECTOR_STORE` 可见 | COLL-X01 · COLL-X02 · SIL-SM-01 |

### 证据索引

| 层 | ID / 路径 |
|----|-----------|
| L1 | [collector_cases.md](../cases/collector_cases.md) COLL-01…03 · COLL-X* |
| L3 | SIL-SM-01（附带共享 store） |
| Latency | ring 首→末跨度 **5 µs**（进程内）；SIL 参考预算 ≤ 1 ms |

**缺口：** 掉电持久化 / Classic DEM / iceoryx 事件总线未纳入默认证据集。

---

## SG-05 — 量产配置可关闭调试通路

| 字段 | 内容 |
|------|------|
| 意图 | production-release 下主链不依赖 GMT / Inject / Tag→MCAP |
| 假设 | A-05 |
| 设计 / 机制 | `req.yaml` `profile: production-release` → compose 关 live_tap/record、不编 tap/inject |
| 验证 | SIL-T4 · L2 `test_observability.py` |

| SR | 需求句 | 验证 |
|----|--------|------|
| SR-05.1 | production-release 下 live_tap 关闭、record=off、无 tap/inject 应用 | SIL-T4 compose 断言 · L2 |
| SR-05.2 | 同 profile 下 SIL-02（multiproc 主链）仍可通过 | SIL-T4（`build-prod`） |

门控：`GF_FUSA_T4=1 bash fusa/scripts/run_cases.sh`（另编 `build-prod`，退出恢复 vehicle-debug）。

---

## 支撑链（非独立 SG，但进入拼装证明）

| 主题 | 作用 | 证据 |
|------|------|------|
| 主链可跑 | 证明 middleware+SKU 拼装 | SIL-01 · SIL-02 |
| 通信 binding | 所选后端可链 | COM / IOX / SIP / DDS / XIPC cases · SIL-06 |
| 生成契约 | compose/codegen 规则 | L2 [gf_codegen_cases.md](../cases/gf_codegen_cases.md) |

---

## 总览矩阵（速查）

| SG | SR | 主机制 | L1 | L3 fusa | Isolation | LAT 摘要 |
|----|-----|--------|----|---------|-----------|----------|
| SG-01 | SR-01.1…01.4 | EM daemon · OSAL Spawn · exit75 | EM-* · EMD-* · OSAL-P* | SIL-EM-01/02 | ISO-EM-01/02 | relaunch ≤50 ms（测 0/1） |
| SG-02 | SR-02.1…02.5 | PHM Alive/Deadline | PHM-* | SIL-03 | ISO-PHM-01 | miss ≤300 ms · recover ≤100 ms |
| SG-03 | SR-03.1…03.5 | sm FG · notify_sm | SM-* | SIL-SM-01 | ISO-SM-01/02 | — |
| SG-04 | SR-04.1…04.4 | collector ring · shared store | COLL-* · COLL-X* | SIL-SM-01 | ISO-COLL-01 | ≤1 ms（测 5 µs） |
| SG-05 | SR-05.1…05.2 | production-release | L2 obs | SIL-T4 | — | — |

---

## 复现与刷新

```bash
# L1 + L3 fusa → fusa/runs/cases_*.log（默认不进仓）
bash fusa/scripts/run_cases.sh
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh

# Isolation / 延时数字（独立；不调用 run_cases）
bash fusa/scripts/measure_latency.sh

# SKU 产物包（独立）
bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
```

最近 L3 全绿记录：[../cases/sil_verify_cases.md](../cases/sil_verify_cases.md)「最近复现」。  
改机制或 case 时：先改 `cases/*` / metrics，再改本表对应行；假设变更同步 [assumptions.md](assumptions.md)。
