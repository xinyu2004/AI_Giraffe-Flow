# Giraffe Flow 路线图（P0–P3 具体化）

> **English:** [ROADMAP.md](../../en/operations/ROADMAP.md)  
> 设计背景：[DESIGN.md](../architecture/DESIGN.md)

本文将平台交付划分为 **P0–P3**。**P0 已收口**；**P1 骨架已齐**（大量 stub），验收见 [P1_REVIEW_CHECKLIST.md](P1_REVIEW_CHECKLIST.md)。  
**当前阶段：P2 收口** — 细则 [P2_PLAN.md](P2_PLAN.md) · Review [P2_REVIEW_CHECKLIST.md](P2_REVIEW_CHECKLIST.md) · 配置规格 [MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md)。

---

## 总览

| 阶段 | 主题 | 典型周期（参考） | 核心验收 |
|------|------|------------------|----------|
| **P0** | 契约 + 最小可运行闭环 | ✅ 已完成 | SOR 子集、gf-codegen、iceoryx 双进程、adc_full compose、CI |
| **P1** | 车规通信 + 工具 + OTA/DoIP 骨架 | ✅ 骨架已齐 | Cfg✓ F✓ I✓ M✓ E/U✓ B/D✓ T/A✓（详见 P1_PLAN） |
| **P2** | **真正可运行** + 可观测 + platform 配置骨架 | ✅ 交付齐 / Review | 多进程 SIL、platform、CycloneDDS、Tag/MCAP、证据包 |
| **P3** | 嵌入式收敛 + 可信度交付 | 量产向 | 裁剪 profile、真板/DoIP/OTA 台架、MIPS/RISC-V OSAL 验证 |

---

## P0 — 契约与最小闭环（✅ 2026-07-13 收口）

**目标：** 证明「SOR → 生成 → 两进程 com」在 **ARM Linux**（含桌面仿真）可跑通；完整拓扑以 `adc_full` compose 验收。

### 交付物

| # | 交付物 | 路径 / 说明 | 状态 |
|---|--------|-------------|------|
| P0-1 | SOR schema **0.2** 字段级冻结（子集） | `schemas/gf.sor.schema.json` | ✅ |
| P0-2 | `gf-codegen`：compose / lint / generate | `tools/codegen/` | ✅ |
| P0-3 | `gf_ara::core` Result/ErrorCode | `middleware/core/` | ✅ |
| P0-4 | `gf_ara::com` Event + iceoryx | `middleware/com/`, `middleware/bindings/iceoryx/` | ✅ |
| P0-5 | 两进程 demo | `apps/simulators/`, `apps/demo_pipeline/` + `smoke_sil.sh` | ✅ |
| P0-6 | OSAL POSIX | `middleware/osal/` | ✅ |
| P0-7 | CMake + `req.yaml` | `cmake/`，`projects/**/req.yaml` | ✅ |
| P0-8 | CI smoke | `ci/scripts/smoke.sh`（含 afc + adc compose） | ✅ |
| P0-9 | `adc_full` compose / generate | `projects/oem_b/adc_full/` | ✅ |

### 验收标准

- [x] `gf-codegen lint` 对 `schemas/examples/desktop_ap_only.sor.json` 通过
- [x] 生成物可编译；两进程 iceoryx 收发（`smoke_sil.sh`）
- [x] 无业务代码写 `#ifdef ARM`；架构由 CMake `GF_OSAL_ARCH` 选择
- [x] `adc_full` compose + lineage `ok` + generate
- [x] 文档：P0 范围外功能标为 P1+

### 明确不在 P0

SOME/IP、DDS、GMT GUI、OTA 实装、DoIP 实装、MCU 真机、MIPS/RISC-V 实板。  
HIL：`compile_hil.sh` 依赖交叉工具链；无工具链时 `cross_link_smoke.sh` SKIP。`run_hil` 仍为 stub。

---

## P1 — 通信扩展、工具链、OTA/DoIP 骨架

**目标：** SKU 可裁剪；**信号链接 GUI**；**FIDL 轻量导入**；主机工具链可用；诊断与 OTA **可链接占位模块**。  
细则：[P1_PLAN.md](P1_PLAN.md)

### 交付物

| # | 交付物 |
|---|--------|
| P1-0 | **`gf-config`（PySide6）**：req 表单 + **信号链接画布**写回 wiring + lineage（**已交付**） |
| P1-2 | SOR / `req.yaml` `runtime_modules` / bindings 驱动 **CMake 裁剪**（**下一刀**） |
| P1-2b | **FIDL 导入已交付**（`parse_fidl` + B 页「导入 fidl…」）；**不导出** fidl/fdepl（后置）；`.fdepl` 读入挂 B/vsomeip；不做 IoNAS |
| P1-7 | **`mcu.cp_gateway` + `cp_ipc_peer` 桌面联调已交付**（`smoke_mcu_desktop.sh`） |
| P1-8 | **`middleware/exec` + `phm` Alive/Deadline 最小已交付** |
| P1-6 | **`middleware/ucm`、`middleware/diag` stub 可链已交付** |
| P1-1 | **CycloneDDS + vsomeip binding 可链**（DDS 默认 Cyclone；offline stub；真源码后置） |
| P1-4 | **SOR→IDL→idlc 包装已交付**（`emit-idl` + `run_idlc.sh` SKIP-ok） |
| P1-5 | **GMT CLI 已交付**：`architect`（CI）· `measure export`（MCAP 雏形） |
| P1-3 | **`gf-codegen import arxml` 子集已交付**（可接 FARACON 产出） |

### 验收标准

- [x] `gf-config` 打开 `afc_with_uss`：可见连线图；改边写回 wiring；compose/lineage 可用
- [ ] 低配 CMake 裁剪后 demo 仍可链（仅 core/com/log/iceoryx）
- [ ] 样例 `.fidl` 可经 gf-config 导入画布为端口候选（`.fdepl` 非本项；见 P1-2b / B）
- [x] DoIP Initialize/Shutdown stub 可被诊断探针调用
- [x] ucm PackageManager 状态机 stub 与 SM 钩子文档化
- [x] `adc_full` MCU 桌面联调脚本可跑（无真 MCU）

---

## P2 — 真正可运行 + 最小可观测 + 平台配置骨架

**目标：** **先定型 gf-config（A/B/C）** → 多进程 SIL → 可观测 → CycloneDDS；platform 五文件（**无 DEM**）。  
细则：[P2_PLAN.md](P2_PLAN.md) · 配置规格：[MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md)

### 交付物

| # | 交付物 | 子轨 |
|---|--------|------|
| P2-R0 | wiring/req 与粗端口对齐 | R0 |
| P2-Cfg | **gf-config 定型**：A 瘦身 · B 巩固 · **C·平台**（最先） | Cfg |
| P2-P | compose 吃 platform + 校验（五 yaml；sm∈exec；无 DEM） | P |
| P2-R | 多进程 iceoryx SIL（gateway/fcm/uss/planning）+ smoke | R |
| P2-X | exec/phm 读 platform 挂主链 + 1 例故障注入 | X |
| P2-O | Record + Tag + 真实 session→MCAP | O |
| P2-B | **CycloneDDS** 真收发（vsomeip 保持 stub） | B |
| P2-F | `GMT bridge foxglove` MVP | F |
| P2-G | 版本锁定 + bench golden + 证据包 + Review 清单 | G |
| P2-U | OTA Spike 选型（可选） | U |

### 验收标准

- [x] `smoke_sil_multiproc`：主链存活，端到端至少一跳有计数
- [x] platform 引用未知 process → compose/校验失败
- [x] Alive miss 可注入可观测
- [x] Tag + 导出 MCAP 可复现（演示）
- [x] CycloneDDS 真 event 收发 ≥ 1
- [x] CI bench golden；证据包有样例（`test_afc_bench_golden` · `evidence_pack/p2_afc_with_uss` · [P2_REVIEW_CHECKLIST.md](P2_REVIEW_CHECKLIST.md)）
- [x] **无 DEM** 配置/生成轨

**P2 收口入口：** [P2_REVIEW_CHECKLIST.md](P2_REVIEW_CHECKLIST.md)

### 明确不在 P2

DEM；真 MCU / 真 DoIP 台架 / 量产 OTA；GMT 可写配置；双栈量产级；ISO 26262。→ **P3 或另议**  
（注：gf-config **C·平台**已在 P2 完成，不再后置。）

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
| P3-7 | 真板 / ap_mcu_cp 台架（承接 P1 桌面 gateway） |

### 验收标准

- [ ] ARM 板端 24h soak 无致命泄漏（指标入报告）
- [ ] PHM：雷达/IVI 故障不拖死控制链（或 gateway 降级可测）
- [ ] 文档声明：工程证据 ≠ ISO 26262 认证

---

## 模块与阶段对照

| 模块 | P0 | P1 | P2 | P3 |
|------|----|----|----|-----|
| core, com, iceoryx | ● | | 四进程 ● | |
| exec, phm, sm | | stub ● | 挂主链 ● | |
| vsomeip, dds | | stub ● | **二选一真后端** ● | |
| ucm, diag (DoIP) | | skeleton ● | Spike 可选 | production ● |
| gf-codegen | ● | ● | 版本锁定 ● | |
| GMT | | CLI ● | Tag/MCAP/Foxglove ● | ● |
| 参考 App（afc 四节点） | 双进程 ● | | **四进程 SIL** ● | |
| trust / bench | | | ● | ● |
| MIPS/RISC-V OSAL | | | | ● |

---

## 下一步

按 **[P2 实施计划](P2_PLAN.md)** 开工：先 **R0 + R（四进程 SIL）**；W3 前确认 **B 轨选 CycloneDDS 还是 vsomeip**。
