# Giraffe Flow 路线图（P0–P3 具体化）

> **English:** [ROADMAP.md](../../en/operations/ROADMAP.md)  
> 设计背景：[DESIGN.md](../architecture/DESIGN.md)  
> 配置规格：[MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md)

本文将平台交付划分为 **P0–P3**。**P0–P2.5 已收口**（桌面 MVP：gf-config · 多进程 SIL · GMT/Foxglove）。  
**当前阶段：P3（深化与扩大）** — 主航道是配置器/中间件/经得起认证的支持/DoIP·OTA；真板与真 MCU 为冲刺门禁。

| 文档 | 用途 |
|------|------|
| [P2_PLAN.md](P2_PLAN.md) / [P2_5_PLAN.md](P2_5_PLAN.md) | 已交付阶段的实施记录 |
| [P2_REVIEW_CHECKLIST.md](P2_REVIEW_CHECKLIST.md) | P2 形式收口 |
| [MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md) | gf-config 两页目标 + Event Collector 口径 |
| [fusa/POLICY.md](../../../fusa/POLICY.md) | 功能安全：L1/L2/L3 证据 → **目标完整 Safety Case** |
| [OTA_SPIKE.md](OTA_SPIKE.md) | OTA 选型尖刺（非真刷写） |

---

## 总览

| 阶段 | 主题 | 状态 | 核心验收 |
|------|------|------|----------|
| **P0** | 契约 + 最小可运行闭环 | ✅ | SOR 子集、gf-codegen、iceoryx 双进程、adc_full compose、CI |
| **P1** | 车规通信 + 工具 + OTA/DoIP 骨架 | ✅ 骨架 | gf-config 初版、FIDL、MCU 桌面 peer、exec/phm/ucm/diag stub |
| **P2** | 真正可运行 + 可观测 + platform 骨架 | ✅ | 多进程 SIL、platform、CycloneDDS、Tag/MCAP、Foxglove |
| **P2.5** | 主机工具链 + 架构师可视化 | ✅ | SIL 编译器可换、GMT GUI、VCD |
| **P3** | 深化与扩大（见下） | **进行中** | 两页 gf-config、中间件加深、cert-ready、DoIP/OTA/GMT、仿真尖刺；真板后置 |

---

## P0 — 契约与最小闭环（✅ 2026-07-13）

**目标：** 证明「SOR → 生成 → 两进程 com」在 ARM Linux（含桌面仿真）可跑通。

### 交付物

| # | 交付物 | 路径 / 说明 | 状态 |
|---|--------|-------------|------|
| P0-1 | SOR schema **0.2** 字段级冻结（子集） | `schemas/gf.sor.schema.json` | ✅ |
| P0-2 | `gf-codegen`：compose / lint / generate | `tools/gf-codegen/` | ✅ |
| P0-3 | `gf_ara::core` Result/ErrorCode | `middleware/core/` | ✅ |
| P0-4 | `gf_ara::com` Event + iceoryx | `middleware/com/`, `middleware/bindings/iceoryx/` | ✅ |
| P0-5 | 两进程 demo | `apps/simulators/`, `apps/demo_pipeline/` + `smoke_sil.sh` | ✅ |
| P0-6 | OSAL POSIX | `middleware/osal/` | ✅ |
| P0-7 | CMake + `req.yaml` | `cmake/`，`projects/**/req.yaml` | ✅ |
| P0-8 | CI smoke | `devops/ci/scripts/smoke.sh` | ✅ |
| P0-9 | `adc_full` compose / generate | `projects/oem_b/adc_full/` | ✅ |

### 明确不在 P0

SOME/IP、DDS、GMT GUI、OTA/DoIP 实装、MCU 真机、MIPS/RISC-V 实板。`run_hil` 仍为 stub（见 P3z）。

---

## P1 — 通信扩展、工具链、OTA/DoIP 骨架（✅ 骨架）

细则：[P1_PLAN.md](P1_PLAN.md)

| # | 交付物 | 状态 |
|---|--------|------|
| P1-0 | `gf-config`：req + 信号链接画布 | ✅ |
| P1-2b | FIDL 导入（不导出 fidl/fdepl） | ✅ |
| P1-7 | `mcu.cp_gateway` + `cp_ipc_peer` 桌面联调 | ✅ |
| P1-8 | `exec` + `phm` Alive/Deadline 最小 | ✅ |
| P1-6 | `ucm` / `diag` stub 可链 | ✅ |
| P1-1 | CycloneDDS + vsomeip binding 可链 | ✅（vsomeip 仍 stub） |
| P1-5 | GMT CLI：`architect` · `measure export` | ✅ |

---

## P2 — 真正可运行 + 可观测 + platform 骨架（✅）

细则：[P2_PLAN.md](P2_PLAN.md) · [MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md)

| # | 交付物 | 状态 |
|---|--------|------|
| P2-Cfg | gf-config A/B/C 三页定型（历史形态；P3 收成两页） | ✅ |
| P2-P | compose 吃 platform；sm∈exec | ✅ |
| P2-R / X | 多进程 SIL；exec/phm 挂主链 + 故障注入 | ✅ |
| P2-O / F | Tag/MCAP；Foxglove bridge | ✅ |
| P2-B | CycloneDDS 真收发（主链仍 iceoryx） | ✅ |
| P2-U | OTA Spike 选型 | ✅ 文档 |

**P2 历史口径：** 未实现 Classic DEM / 事件收集最小集；诊断仅为 diag stub。**P3 起改为 Event Collector 策略**（见下、见 MIDDLEWARE_CONFIG）。

### P2.5（✅）

细则：[P2_5_PLAN.md](P2_5_PLAN.md) — SIL 编译器可换 · GMT GUI · VCD。DAG/GTKWave/GMT **不上车**。

### 明确已后置（P2 当时不做 → 现归 P3）

真 MCU / 真 DoIP 台架 / 量产 OTA；GMT 写配置（仍禁止）；双栈量产级；**代做** ISO 26262 认证。

---

## P3 — 深化与扩大（当前）

**产品定位：** 轻量类 AUTOSAR AP 中间件 + 工具链。桌面 MVP 已通；P3 加深配置与运行时，提供 **经得起认证的支持**（非代认证），并扩展 DoIP/OTA 操作面与仿真尖刺。  
**真板 / 真 MCU：** 冲刺门禁（P3z），非主航道。

```text
主航道：  P3-1 Config → P3-2 Middleware ∥ P3-5 Sim尖刺 → P3-3 Cert-ready → P3-4 DoIP/OTA/GMT
门禁：    P3z Board / MCU（everything OK 后冲刺；中段仅可选极薄 smoke）
```

### P3-1 Config — gf-config 成平台配置器（两页）

| # | 交付物 | 状态 |
|---|--------|------|
| C1 | **两页 UI**：① **信号与应用**（默认首页）· ② **平台运行时** | ✅ |
| C1b | **端口交互**：裸拖 Out/In=连线；**Ctrl+拖拽**=改端口边 | ✅ |
| C1c | 观测：`wiring_all` 天花板 + **codegen tap** + GMT 焦点过滤 | ✅ 合同+codegen；GMT 焦点既有 |
| C2 | 页 2 做实：exec / phm / sm / diag / log / ucm / Collector | ◐ 编辑器齐；运行时加深另见 P3-2 |
| C3 | Event Collector 配置表（`platform/collector.yaml`） | ✅ 最小编辑 |
| C4 | 对齐 [MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md) · [STRUCTURE.md](../../../STRUCTURE.md) | ✅ |

工作流：打开 project → **先画节点/信号** → 再勾模块并填平台表 → Verify / Generate。  
**GMT 仍不写配置。**

### P3-2 Middleware — AP 味加深

| # | 交付物 | 状态 |
|---|--------|------|
| M1 | **sm** 状态机可用（超出 exec.yaml 名单） | ✅ FG Off/Running/Updating + `NotifyHealthFault` |
| M2 | **phm** Logical + `notify_sm` / 与 Collector 联动 | ✅ `ReportLogical` + SIL `on_failure: notify_sm` |
| M3 | **Event Collector** 运行时：汇聚错误 → CP DEM 或本地事件库 | ✅ 环缓 + `cp_dem` stub 转发 |
| M3b | **EM** 最小集 + OS daemon（fork/exec + exit75 relaunch） | ✅ `ExecutionManager` + `gf_em_daemon` |
| M4 | **log** lite（超 skeleton） | ✅ `gf_ara::log` + `gf_log_smoke`；SIL 读 `log.yaml` |
| M5 | per / tsync 骨架落地（可裁剪） | ✅ `gf_ara::per` / `gf_ara::tsync` + smoke；`req` 可裁剪 |
| M6 | vsomeip **择一**加深 | **降至 P3z 前**（Z0b；不挡 DoIP/OTA） |

### P3-3 Cert-ready — 经得起认证的支持

| # | 交付物 | 状态 |
|---|--------|------|
| T1 | `fusa/` 入口：政策 + cases + 收集脚本 | ✅ [fusa/](../../../fusa/) · [POLICY.md](../../../fusa/POLICY.md) · [cases/](../../../fusa/cases/) |
| T2 | 可复现 PHM 隔离 / Collector 场景 + 参考延时表 | ✅ SIL 预算已填；文档标明主机 SIL ≠ ECU ASIL；板端 soak → P3z |
| T3 | 本机 runs / packs 流程（默认不进仓） | ✅ `fusa/scripts/run_cases.sh` → `fusa/runs/`；SKU `generate_fusa_artifacts.sh` → `fusa/packs/`（互不调用） |
| T3b | Safety Case 追溯（SG → SR → 验证） | ✅ [traceability.md](../../../fusa/safety-case/traceability.md)：SG-01…05 + OTA/DoIP/UDS；缺口 → P3z / assumptions |
| T4 | `production` profile：关 Record/ROS/调试路径 | ✅ [`smoke_production_profile.sh`](../../../scripts/verify/oem_a_afc_with_uss/smoke_production_profile.sh)；**发版必跑** `GF_FUSA_T4=1`（`devops/ci/README.md`） |

**目标：** 完整 Safety Case（骨架：[fusa/safety-case/](../../../fusa/safety-case/)）。**当前不声称**证书已取得；仓内持续积累可引用证据（不含把 GMT/stub 当板级 ASIL 证据）。

### P3-4 DoIP / OTA / GMT

| # | 交付物 | 状态 |
|---|--------|------|
| D1 | DoIP **会话级**互通（可先 SIL/假 board，不绑量产板） | ✅ TCP；**依赖** ISO 14229；`UdsDispatcher` + NRC |
| D2 | **GMT OTA sheet**：选包 / 进度 / 结果；经 **DoIP** 下发路径 | ✅ GMT「OTA」页：14229 父 / 13400 子；DoIP→UCM |
| D3 | UCM 编排（+ SM Pause）；后端可 stub→RAUC | ✅ `OtaOrchestrator`；0x27/0x29 插件 ABI（`.so/.dll`） |
| D4 | OTA/升级失败路径上 Collector 事件可观测 | ✅ `ucm/ota_failed` |

验收：`bash scripts/verify/oem_a_afc_with_uss/smoke_doip_ota.sh`

### P3-5 Sim spike — 场景演示（未开工；弃 VP）

| # | 交付物 | 状态 |
|---|--------|------|
| S1' | **YOLO → semantic** feed 尖刺（主推荐） | ⏳ 下一轮 |
| S1 | CARLA → 同一 semantic 出口（可选） | ⏳ |
| S2 | Vision Pilot | **放弃**（授权） |
| S3 | 与 GMT live/inject 联调说明 | ⏳ |

弱耦合；不替代主航道。

### P3z Board / MCU — 冲刺门禁（最不急）

| # | 交付物 | 说明 |
|---|--------|------|
| Z0 | （可选）极薄 smoke：交叉编译 + hello / 单 iceoryx ping | 中段穿插，不挡桌面交付 |
| Z0b | vsomeip **择一**加深（原 P3-2 M6） | 真板前完成即可；不挡 P3-4 DoIP/OTA |
| Z1 | `run_hil` / 部署自动化 | everything OK 后冲刺 |
| Z2 | ARM 24h soak + 板端证据包 | 同上 |
| Z3 | 真 **ap_mcu_cp** 台架 | Collector→CP 在桌面 peer 验证后再上真 CP |
| Z4 | OSAL mips / riscv 至少编译通过 | 可与 Z1 并行 |

---

## Event Collector / DEM 口径（P3 起）

| 场景 | Giraffe（AP） | 状态/防抖归属 |
|------|---------------|----------------|
| 有 MCU AUTOSAR CP | **Collector 最小集** → 转交 CP DEM | CP |
| 无 CP / 纯 DoIP | Collector + 持久化/查询 + DoIP 可读 DTC 子集 | AP 侧 **DEM-lite**（非完整 Classic DEM） |

**无论有无 CP，都必须有「收集错误」机制。** DoIP 替代的是总线形态，不是「可以没有事件管理」。完整 Classic DEM 编辑器 / 全量 UDS **不做**。

---

## 模块与阶段对照（更新）

| 模块 | P0–P2.5 | P3 |
|------|---------|-----|
| core, com, iceoryx | ● | |
| dds (Cyclone) | 真路径尖刺 ● | |
| vsomeip | stub | **P3z 前**择一加深（不挡 P3-4） |
| exec, phm | 挂主链 ● | Logical / 联动；**EM** 最小 + `restart` |
| sm | ∈exec 名单 | 状态机 ● |
| diag / ucm | stub / Spike | **DoIP 会话 · GMT OTA · UCM 编排 ●**（RAUC 真刷→P3z） |
| **Event Collector** | — | **最小集 ●** |
| log / per / tsync | skeleton / 缺 | **lite / 骨架 ●**（vsomeip→P3z） |
| gf-config | **两页 UI ✅** · wiring_all / codegen tap ✅ | 平台加深 |
| GMT | GUI + Foxglove | **OTA sheet ●** · measure 证据 |
| Sim (CARLA/VP) | — | adapter 尖刺 |
| 真板 / 真 CP | — | **P3z 冲刺** |
| 代认证 | — | **不做**（只做 cert-ready 支持） |

---

## 下一步

1. **P3-5** YOLO→semantic 演示尖刺（弃 VP；CARLA 可选）。  
2. **P3z**：真板 / vsomeip / RAUC 真刷写 / 板端 soak。  
3. 云 CI 启用 `devops/ci` + 发版跑 T4。
