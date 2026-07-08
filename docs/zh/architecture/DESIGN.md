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

**P0（MVP 必须）：** `core`、`exec`、`phm`、`com`、`log`、`sm`（均为简化实现）

**P1：** `per`、`tsync`；诊断类可先用健康查询 API 代替完整 `diag`

**P2（安全 / 合规）：** `crypto`、`iam`、`idsm`、`ucm`/`vucm`、`fw`、`shwa`、完整 `nm`/`diag`

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
        → Importer
        → gf.sor.json
        → lint
        → codegen
        → gf_ara Proxy/Skeleton + EM/PHM manifest + binding 配置 + 适配骨架
```

架构师工具（DAG / 信号 review）**只读同一份 SOR**，保证图与生成代码同源。

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

## 6. SOA：服务边界 vs 进程边界

**SOA** = 接口稳定、可发现、可替换。  
**进程** = 故障隔离与资源部署粒度。  

不必「一个功能一个进程」，否则会白白增加上下文切换、端点与内存。

| 倾向拆进程 | 倾向同进程 |
|------------|------------|
| SDK / 驱动易崩、OEM 易变 | 纯算子、同生命周期 |
| 不应拖死控制链（IVI、雷达） | 超高频且资源紧 |
| 可能部署到另一 SoC | 永远钉在本域控制器 |

**默认进程清单：**

| 进程 | 说明 |
|------|------|
| `gf.exec_manager` / `gf.phm` / `gf.sm` | 平台常驻 |
| `sensor.radar_*` | **雷达独立**（建议默认） |
| `sensor.camera_ingest` | 相机输入 |
| `perception.pipeline` | 融合 / OpenVX |
| `planning.service` | 规划 |
| `control.service` | 控制（最短路径、最高优先级） |
| `vehicle.actuator_gateway` | 执行器（可选独立） |
| `ivi.service` | 本机或跨 SoC；永不与控制共进程 |

Manifest 允许把轻量服务**合部署**到同一 OS 进程，而不改服务接口。

---

## 7. 部署边界

| 类别 | 内容 |
|------|------|
| **板端常驻** | EM、PHM、SM、传感器适配、感知/规控、IVI（本机或对端）、必要 binding、环形缓冲 Trace Agent |
| **上位机（永不装车）** | Importer、codegen、DAG / Signal Review、GTKWave、离线回放、ROS 可视化 |
| **前期（desktop profile）** | 模拟传感器、全量录制、ROS 联调 |
| **上车调试（vehicle-debug）** | 采样 Record、诊断探针；量产默认关闭 |

阶段：T0 桌面 → T1 板+主机 → T2 台架 → T3 上车调试 → T4 量产裁剪。

---

## 8. 可观测性

| 层级 | 手段 | 用途 |
|------|------|------|
| 设计态 | DAG Viewer、Signal Lineage | 架构 / 信号扭转评审 |
| 运行态（细） | Trace → VCD/FST → GTKWave | 微小时序、pipeline 抖动 |
| 运行态（长） | Record/Replay | 小时级复现、确定性回放 |

原则：先统一时钟；先只读回放，再做注入式回放；板端录制默认采样，避免拖垮实时路径。

---

## 9. 移植性：OSAL / HAL / Binding

```text
Apps (perception/planning/…)
    → gf_ara API
    → gf runtime
         ├→ Binding plugins (iceoryx / someip / dds)
         └→ OSAL → Linux（先行） / QNX（预留）
Apps / adapters
    → HAL → 具体 SoC / 雷达 SDK / CAN
```

换平台时：业务与 runtime 核心通常不变；改 OSAL（首次移植）、HAL（每车型）、binding（库可用性）、部署 profile。**禁止在感知/规控里写 `#ifdef SOC_X`。**

---

## 10. 仓库与制品策略

**现阶段：一个 monorepo（单仓多包）。**  
原因：`gf.sor.json` 把 runtime、codegen、架构工具绑在一起，过早多仓会导致契约漂移与版本地狱。

推荐布局：

```text
AI_Giraffe-Flow/
  schemas/                 # 契约心脏，semver
  middleware/              # 板端 runtime
  platform/osal|hal/
  bindings/
  tools/importer|codegen|architect|record_replay/
  apps/                    # 参考进程；客户量产工程另仓
  deploy/profiles/
  docs/en/  docs/zh/
  ci/
```

制品线可分：`gf-runtime`、`gf-tools`、`gf-schemas`。  
板端 CI **不编** GUI 类 tools。  
`schemas` 变更必须跑 golden codegen + 至少一条多进程 e2e。

**客户车型工程**使用独立仓库：锁定 schema/runtime/tools 版本 + 自有 SOR/HAL/业务代码。  
待 schema 稳定且需要独立授权/发版时，再按「architect UI → tools → 模板 apps」顺序拆仓；middleware+schemas 尽量最晚拆。

---

## 11. 落地四原则

1. 先冻结 SOR/IDL 子集，再写生成器。  
2. 先只读回放，再可控注入。  
3. 全链路统一时间基准。  
4. 在 SOR 中显式固化 DDS ↔ SOME/IP 映射，不靠口头约定。

---

## 12. 里程碑（摘要）

| 里程碑 | 验收要点 |
|--------|----------|
| M0 | 模块矩阵、SOR schema（含图信息）、导入契约、SOA/部署边界评审通过 |
| M1 | 桌面多进程 + 三 binding；OEM 样例可导入；DAG / 信号 review 可用 |
| M2 | EM+PHM 恢复闭环；雷达/IVI 故障不拖死控制 |
| M3 | ROS↔DDS；GTKWave + Record/Replay |
| M4 | 至少一块嵌入式 Linux SoC；量产 profile 关闭调试件 |

---

## 13. 风险摘要

- 三栈复杂度 → 插件化 + 首版先 Event  
- 进程过细 → 决策表 + 允许合部署  
- OEM 噪声 → 映射人工 review + lint  
- 图码不一致 → 工具只读 SOR + CI 校验  
- 过早多仓 → monorepo 先行  

更细的操作步骤见 [WORKFLOW.md](../operations/WORKFLOW.md)。
