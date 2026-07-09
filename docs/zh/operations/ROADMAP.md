# Giraffe Flow 路线图（P0–P3 具体化）

> **English:** [ROADMAP.md](../../en/operations/ROADMAP.md)  
> 设计背景：[DESIGN.md](../architecture/DESIGN.md)

本文将平台交付划分为 **P0–P3**，每阶段有明确交付物与验收标准。完成文档与目录骨架后，**下一步单独制定 P0 实施计划**。

---

## 总览

| 阶段 | 主题 | 典型周期（参考） | 核心验收 |
|------|------|------------------|----------|
| **P0** | 契约 + 最小可运行闭环 | 基础 | SOR 冻结子集、gf-codegen 管线、iceoryx 双进程、ARM Linux 桌面/板 |
| **P1** | 车规通信 + 工具 + OTA/DoIP 骨架 | 扩展 | 三 binding 可选、GMT、ucm/diag 可链、MCU gateway 模拟 |
| **P2** | 可观测 + 证据 + 异构量产 | 深化 | MCAP/Tag/bench、Foxglove 桥、ap_mcu_cp 台架 |
| **P3** | 嵌入式收敛 + 可信度交付 | 量产向 | 裁剪 profile、证据包、MIPS/RISC-V OSAL 验证 |

---

## P0 — 契约与最小闭环（下一步详细计划）

**目标：** 证明「SOR → 生成 → 两进程 com」在 **ARM Linux**（含桌面 aarch64/x86_64 仿真）可跑通。

### 交付物

| # | 交付物 | 路径 / 说明 |
|---|--------|-------------|
| P0-1 | SOR schema **0.2** 字段级冻结（子集） | `schemas/gf.sor.schema.json` + 评审记录 |
| P0-2 | `gf-codegen` 可执行：`import`（DBC 样例）、`lint`、`generate`（最小） | `tools/codegen/` |
| P0-3 | `gf_ara::core` Result/ErrorCode | `middleware/core/` |
| P0-4 | `gf_ara::com` Event 子集 + **iceoryx binding** | `middleware/com/`, `bindings/iceoryx/` |
| P0-5 | 两进程 demo：simulator publish + consumer subscribe | `apps/simulators/`, `apps/demo_pipeline/` |
| P0-6 | OSAL POSIX + **ARM** backend 最小（线程、单调时钟） | `platform/osal/` |
| P0-7 | CMake 构建 + desktop profile | `cmake/`, `deploy/profiles/desktop.yaml` |
| P0-8 | CI：lint + generate golden + 单测冒烟 | `ci/` |

### 验收标准

- [ ] `gf-codegen lint` 对 `schemas/examples/desktop_ap_only.sor.json` 通过
- [ ] 生成物可编译；两进程 iceoryx 收发 semantic 类型
- [ ] 无业务代码写 `#ifdef ARM`；架构由 CMake `GF_OSAL_ARCH` 选择
- [ ] 文档：P0 范围外功能标为 P1+

### 明确不在 P0

SOME/IP、DDS、GMT GUI、OTA 实装、DoIP 实装、MCU 真机、MIPS/RISC-V 实板。

---

## P1 — 通信扩展、工具链、OTA/DoIP 骨架

**目标：** SKU 可裁剪；主机工具链可用；诊断与 OTA **可链接占位模块**。

### 交付物

| # | 交付物 |
|---|--------|
| P1-1 | vsomeip、CycloneDDS binding（可选编译） |
| P1-2 | SOR `product_variants` + `runtime_modules` 驱动 CMake 裁剪 |
| P1-3 | `gf-codegen import` ARXML 子集 |
| P1-4 | SOR types → IDL → **cyclonedds idlc** 包装 |
| P1-5 | **GMT** CLI：`architect`（DAG 文本）、`measure export`（MCAP 雏形） |
| P1-6 | `middleware/ucm`、`middleware/diag` 链接进镜像（stub 实现） |
| P1-7 | `mcu.cp_gateway` + `cp_ipc_peer` 桌面联调 |
| P1-8 | `middleware/exec` + `phm` Alive/Deadline 最小 |

### 验收标准

- [ ] `ap_only` 与 `ap_mcu_cp` 两套 SOR 示例均可 lint + generate
- [ ] 低配 manifest 仅含 5/10 中间件库仍可运行 demo
- [ ] DoIP Initialize/Shutdown stub 可被诊断探针调用
- [ ] ucm PackageManager 状态机 stub 与 SM 钩子文档化

---

## P2 — 可观测、ROS 生态、工程证据

**目标：** 用户能 **度量、回放、出报告**；算法同事能用 Foxglove/PlotJuggler。

### 交付物

| # | 交付物 |
|---|--------|
| P2-1 | 板端 Record Agent + Session **Tag** |
| P2-2 | GMT `measure bench` + `qos_budgets` 对照 |
| P2-3 | GMT `bridge foxglove` / `measure plot` |
| P2-4 | trace → VCD → GTKWave 文档化工作流 |
| P2-5 | 故障注入场景 2–3 个（雷达丢失、IPC 超时） |
| P2-6 | `gf-codegen` + GMT 版本与 schema 锁定策略 |
| P2-7 | OTA：RAUC 或自研 ucm 后端 **Spike 选型落地** |

### 验收标准

- [ ] 10 分钟运行 + 第 6 分钟 tag + 导出 ±3 分钟 MCAP 可复现
- [ ] CI golden `bench_e2e_latency` 回归
- [ ] 证据包目录结构（HTML/JSON）有样例

---

## P3 — 嵌入式量产收敛与多架构

**目标：** 至少一块 **ARM** 车载 Linux SoC 量产 profile；预留 **MIPS/RISC-V**；可信度材料可给客户引用。

### 交付物

| # | 交付物 |
|---|--------|
| P3-1 | `production` profile：关闭 Record/ROS/调试 |
| P3-2 | DoIP 台架互通（基础会话 + 路由激活） |
| P3-3 | OTA 台架单次升级演练（A/B 或等效） |
| P3-4 | OSAL **mips** / **riscv** backend 各至少编译通过 |
| P3-5 | 发版附带 evidence_pack + 参考延时表 |
| P3-6 | 客户车型外仓集成指南 + 契约测试模板 |

### 验收标准

- [ ] ARM 板端 24h soak 无致命泄漏（指标入报告）
- [ ] PHM：雷达/IVI 故障不拖死控制链（或 gateway 降级可测）
- [ ] 文档声明：工程证据 ≠ ISO 26262 认证

---

## 模块与阶段对照

| 模块 | P0 | P1 | P2 | P3 |
|------|----|----|----|-----|
| core, com, iceoryx | ● | | | |
| exec, phm, sm | | ● | | |
| vsomeip, dds | | ● | | |
| ucm, diag (DoIP) | | skeleton ● | backend ● | production ● |
| gf-codegen | ● | ● | | |
| GMT | | ● | ● | ● |
| simulators / gateway | ● | ● | | |
| trust / bench | | | ● | ● |
| MIPS/RISC-V OSAL | | | | ● |

---

## 下一步

制定 **[P0 实施计划](P0_PLAN.md)**（待创建）：任务分解、人天粗估、依赖顺序、第一个可演示日期。
