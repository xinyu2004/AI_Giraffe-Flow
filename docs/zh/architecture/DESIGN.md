# Giraffe Flow 设计文档

> 文档版本：0.1（架构基线）  
> 状态：供评审，尚未进入大规模实现  
> **English:** [DESIGN.md](../../en/architecture/DESIGN.md)  
> 配套流程：[操作流程 WORKFLOW.md](../operations/WORKFLOW.md)

---

## 1. 愿景与定位

Giraffe Flow 是一套**轻量跨平台平台软件**，目标用户同时覆盖：

- 嵌入式板端（优先落地）
- 普通桌面 Linux（前期调试、仿真、工具链）

它借鉴 AUTOSAR Adaptive Platform（AP）中的：

- 进程 / 执行管理
- 平台健康管理
- SOA 通信（Proxy / Skeleton、服务发现）

并主动补强 AP 生态中昂贵或薄弱的部分：

- 可负担的 **模型驱动代码生成**（ARXML/DBC → SOR → 生成）
- **架构师友好的 DAG + 信号扭转 review**
- **GTKWave** 级时序 + **长时间 Record/Replay**
- **OpenVX** 跨核 pipeline 可观测
- **ROS 2** 互操作（DDS）
- 可裁剪、可移植的部署（非完整 AP 14+ daemon）

产品策略：**工程平台优先**（先可用、可观测、可迁移），功能安全认证路径后置。

---

## 2. 与 AUTOSAR AP 的关系

我们**借鉴思想，不复制整栈**。API 语义贴近 ARA，命名空间使用 `gf_ara::*`，避免伪装成官方 `ara::*` 认证实现。

### 2.1 AP 功能簇全景（基线：R24-11 / R25-11）

| FC | 命名空间 | 核心职责 |
|----|----------|----------|
| Core Types | `ara::core` | Result / ErrorCode / Future |
| Communication | `ara::com` | SOA：Method / Event / Field；binding 可含 SOME/IP、DDS、IPC |
| Execution | `ara::exec` | 进程生命周期、功能组、资源组 |
| Health | `ara::phm` | Alive / Deadline / Logical 监督 |
| State | `ara::sm` | 机器 / 功能组状态、降级 |
| Log | `ara::log` | 日志与 trace（DLT） |
| Persistency | `ara::per` | KV / 文件持久化 |
| Diagnostics | `ara::diag` | UDS / DoIP / SOVD |
| Crypto | `ara::crypto` | 加解密、证书 |
| IAM | `ara::iam` | 访问控制 |
| IDSM | `ara::idsm` | 入侵检测 |
| NM | `ara::nm` | 网络管理 |
| Time Sync | `ara::tsync` | gPTP 等 |
| UCM / V-UCM | `ara::ucm` / `vucm` | OTA / 配置 |
| Raw Data Stream | `ara::rds` | 原始流 |
| Firewall / SHWA | `ara::fw` / `shwa` | 防火墙 / 安全加速器 |

### 2.2 保留 / 简化 / 延后 / 扩展

**P0（MVP 必须）：** `core`、`exec`（简化）、`phm`（简化）、`com`、`log`、`sm`（简化）

**P1（骨架 + 扩展）：** `per`、`tsync`；**`ucm`（OTA）**、**`diag`（DoIP）** 公共 API + stub 实现；完整 UDS 栈后置

**P2（安全 / 合规深化）：** `crypto`、`iam`、`idsm`、`fw`、`shwa`、完整 `nm`、OTA 后端量产化

**扩展（AP 弱或无）：**

| 能力 | 做法 |
|------|------|
| Pipeline 可观测 | 统一 trace + VCD/FST → GTKWave |
| OpenVX | adapter + hook，不侵入算法主体 |
| ROS 2 | DDS binding + 可选 SOME/IP↔DDS bridge |
| 工具链 | Importer + `gf.sor.json` + codegen，替代重型商业工具 |
| 长期定位 | Record/Replay |
| 架构评审 | DAG Viewer + Signal Lineage |

---

## 3. 命名与双层 API

| 层 | 命名空间 | 用途 |
|----|----------|------|
| 兼容 / 对外 | `gf_ara::com`、`gf_ara::exec`、`gf_ara::phm`… | 让人一眼知道对标 ARA 语义 |
| 核心 / 对内 | `gf::com`、`gf::runtime`、`gf::trace`… | 承载扩展（录制、binding 热切换等） |

原则：**语义兼容 ara；行为可以更强。** 对外头文件以 `gf_ara::*` 为主，内部转调 `gf::*`。

---

## 4. 通信架构（三协议栈）

```text
Application (gf_ara::com)
        │
        ▼
  Binding Router  ←── manifest / COM_BINDING=iceoryx|someip|dds|auto
   ┌────┼────┐
   ▼    ▼    ▼
iceoryx  SOME/IP  DDS(CycloneDDS)
 机内     车规/ECU  ROS2 / 跨 SoC
```

| 协议 | 角色 | 典型场景 |
|------|------|----------|
| iceoryx | 本机零拷贝 | 雷达检测、图像帧、融合输入输出 |
| SOME/IP | 服务导向、跨 ECU | 底盘、车身、对外 SOA |
| DDS | 数据中心、生态 | ROS2 rviz/foxglove、跨 SoC IVI、算法原型 |

应用只依赖统一 API；运行时按 profile 选择 binding。DDS 与 SOME/IP 的语义差异必须写进 SOR/映射表（Partition/Topic ↔ ServiceInstance 等），禁止散落在插件里。

---

## 5. 模型驱动：SOR 与代码生成

**SOR** = **Statement of Requirements**（需求说明 / 需求模型契约），对应唯一事实源文件 `gf.sor.json`。早期草案曾称 IR，现统一为 SOR。

### 5.1 格式职责（已确认）

| 格式 | 是否 codegen 直接输入 |
|------|------------------------|
| OEM `.arxml` / `.dbc` | 否 → Importer |
| `req.yaml` / 可选 `gf.idl` | 否 → 归一到 SOR |
| **`gf.sor.json`** | **是（唯一）** |

流水线：

```text
OEM.arxml|dbc + req.yaml
        → gf-codegen import
        → gf.sor.json
        → gf-codegen lint
        → gf-codegen generate
        → gf_ara Proxy/Skeleton + EM/PHM manifest + binding 配置
```

主机度量与分析：**GMT**（`architect` / `measure` / `bridge`）— 不参与 SOR 写入。

架构师工具（DAG / 信号 review）**只读同一份 SOR**，保证图与生成代码同源。

编写与 OEM 导入契约：[sor-authoring.md](sor-authoring.md) · 示例：[projects/](../../../projects/)

### 5.2 SOR 必备内容

- `schema_version`
- `types[]`
- `services[]`（method / event / field + QoS）
- `deployments[]`：进程、功能组、资源；**每个进程的 `provides[]` / `requires[]`**
- `dataflows[]`（显式或可推导）：生产者 → 服务/字段 → 消费者；支持一书多订
- `bindings[]`
- `imports_meta`：OEM 信号名 ↔ 稳定服务字段、源文件哈希

没有 provide/require，就**画不出可靠 DAG**，也无法做「车速被谁订阅」的 review。

### 5.3 共享信号（例：车速）

错误：感知、规划、控制各自读 CAN。  
正确：

1. DBC `VehicleSpeed` 映射为 `VehicleMotion.speed`
2. `vehicle.motion_gateway` **唯一 provide**
3. 感知 / 规划 / 控制在 `requires` 中订阅
4. Signal Review 列出全部消费者与 QoS

OEM 换信号表时，优先改 gateway + 映射，**尽量不改编感知 / 规控业务源码**。生成物放 `generated/`，手写逻辑放 `apps/*/src`。

---

## 6. 可组合组件、适配器与产品变体

感知 / 规划 / 控制 / IVI **不是固定全集**；由 `product_variants` 组合。

| 层 | 职责 | 仓库 |
|----|------|------|
| **适配器** | OEM、传感器 SDK、**mcu.cp_gateway** | 平台 monorepo `apps/adapters/` |
| **语义契约** | `semantic.*` 服务 | `schemas/` + SOR |
| **业务组件** | 感知、规划等 | **外部量产仓**；平台用 `apps/simulators/` |

**组件无感：** 业务只依赖 `gf_ara` semantic 服务；OEM 差异在 adapter/gateway。

**拓扑：**

- `ap_only` — 控制等在 AP；无 MCU gateway
- `ap_mcu_cp` — MCU 跑 **AUTOSAR CP（零 gf 代码）**；AP 上 `mcu.cp_gateway` + IPC

详见 [heterogeneous-compute.md](heterogeneous-compute.md)、[component-composition.md](component-composition.md)。

---

## 7. SOA：服务边界 vs 进程边界（参考示例，非全集）

**SOA** = 接口稳定。 **进程** = 故障域。清单随 `product_variants` 变化。

| 参考进程 | 说明 |
|----------|------|
| 平台常驻 | exec / phm / sm |
| 适配器 | radar、camera、vehicle_motion_gateway、**mcu.cp_gateway**（仅 ap_mcu_cp） |
| 业务 | 外部仓或 **simulators** |
| IVI | 可选，独立故障域 |

---

## 8. 部署边界：板端 vs 上位机

| 类别 | 板端 Onboard | 上位机 Host PC |
|------|----------------|----------------|
| 运行时 | EM、PHM、SM、`gf_ara::com`、裁剪 bindings | — |
| 适配 / sim / 外仓组件 | ● | — |
| MCU（ap_mcu_cp） | AUTOSAR CP（无 gf） | — |
| 录制 | Record Agent（vehicle-debug） | — |
| 契约 | 消费 `generated/` | **gf-codegen** |
| 度量 | — | **GMT** + Foxglove/PlotJuggler |
| OTA/DoIP | ucm/diag 模块（按 SKU） | 台架工具 |

阶段：T0 桌面 → T1 板+主机 → T2 台架 → T3 上车调试 → T4 量产裁剪。

**目标硬件：** 嵌入式 **ARM Linux** 为主；**MIPS、RISC-V** 经 OSAL arch 预留（见 §10）。

---

## 9. 可观测性与可信度（摘要）

设计态：GMT `architect` + SOR。运行态：trace、MCAP Session、Tag。发布态：`qos_budgets` + bench 证据包。

详见 [observability-toolchain.md](observability-toolchain.md)、[trust-evidence-metrics.md](trust-evidence-metrics.md)。

---

## 10. 移植性：解耦、OSAL、多架构

### 10.1 解耦五原则

1. **SOR 唯一契约** — 拓扑、QoS、模块裁剪、arch
2. **一能力一包** — middleware/bindings 可 `runtime_modules` 裁剪
3. **插件边界** — binding、HAL、GMT/codegen 插件独立演进
4. **gf_ara 稳定 / gf 与第三方可换**
5. **业务与 OEM 差异不进组件仓**

### 10.2 分层

```text
simulators / adapters / 外部组件
    → gf_ara API
    → middleware (可裁剪)
    → bindings (iceoryx | someip | dds | cross_domain_ipc)
    → OSAL (posix + arch: arm | mips | riscv)
    → HAL (boards/)
```

换 SoC：**只动 OSAL arch + HAL + profile**。禁止业务 `#ifdef SOC_X`。

### 10.3 OTA 与 DoIP

- **`gf_ara::ucm`** — [`middleware/ucm/`](../../../middleware/ucm/)：包传输、激活、回滚钩子（P1 骨架）
- **`gf_ara::diag`** — [`middleware/diag/`](../../../middleware/diag/)：DoIP 优先（P1 骨架）

OTA 后端候选：RAUC、OSTree；**不含 SWUpdate**。

---

## 11. 仓库与制品策略

**现阶段：一个 monorepo（单仓多包）。**  
原因：`gf.sor.json` 把 runtime、codegen、架构工具绑在一起，过早多仓会导致契约漂移与版本地狱。

推荐布局：

```text
AI_Giraffe-Flow/
  schemas/                 # SOR 契约，semver
  middleware/              # 板端 runtime：core/com/bindings/osal/hal/…
    third_party/           # 上游检出（钉扎后）
  tools/codegen/           # gf-codegen
  tools/bridge/            # 主机侧桥（如 ROS2）
  tools/gmt/               # GMT
  apps/adapters|simulators/
  projects/                # OEM 集成输入（req.yaml 含契约与部署裁剪）
  deps/                    # 第三方依赖清单与版本锁
  docs/en/  docs/zh/
  ci/
```

仓库内已落地的骨架说明见根目录 [STRUCTURE.md](../../../STRUCTURE.md) 与 [deps/README.md](../../../deps/README.md)。

制品线可分：`gf-runtime`、`gf-tools`、`gf-schemas`。  
板端 CI **不编** GUI 类 tools。  
`schemas` 变更必须跑 golden codegen + 至少一条多进程 e2e。

**客户车型工程**使用独立仓库：锁定 schema/runtime/tools 版本 + 自有 SOR/HAL/业务代码。  
待 schema 稳定且需要独立授权/发版时，再按「architect UI → tools → 模板 apps」顺序拆仓；middleware+schemas 尽量最晚拆。

---

## 12. 落地四原则

1. 先冻结 SOR 子集，再写生成器。  
2. 先只读回放，再可控注入。  
3. 全链路统一时间基准。  
4. 在 SOR 中显式固化 binding 与 QoS 映射。

---

## 13. 阶段路线图（P0–P3）

具体交付物与验收见 **[ROADMAP.md](../operations/ROADMAP.md)**。摘要：

| 阶段 | 焦点 |
|------|------|
| **P0** | SOR 0.2、gf-codegen、iceoryx 双进程、ARM OSAL |
| **P1** | 三 binding 可选、GMT、ucm/diag stub、MCU gateway 模拟 |
| **P2** | MCAP/Tag/bench、Foxglove、工程证据包 |
| **P3** | 量产 profile、DoIP/OTA 台架、MIPS/RISC-V OSAL 编译 |

---

## 14. 风险摘要

- 三栈复杂度 → 插件化 + 首版先 Event  
- 进程过细 → 决策表 + 允许合部署  
- OEM 噪声 → 映射人工 review + lint  
- 图码不一致 → 工具只读 SOR + CI 校验  
- 过早多仓 → monorepo 先行  

更细的操作步骤见 [WORKFLOW.md](../operations/WORKFLOW.md)。
