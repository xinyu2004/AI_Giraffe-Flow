# 第三方库初步评估

> **English:** [THIRD_PARTY_EVALUATION.md](../../en/dependencies/THIRD_PARTY_EVALUATION.md)  
> 清单：[deps/DEPENDENCIES.yaml](../../../deps/DEPENDENCIES.yaml)

**原则：** `gf.sor.json` 为唯一契约；三方库为传输/序列化/工具引擎。OTA **不包含 SWUpdate**。

## 评估维度

许可、部署类别（板端/主机）、成熟度、复用策略（链接 / idlc / 外调）、风险、建议（P0–P3）。

## 传输（板端）

| 库 | 建议 | 复用 | 风险 |
|----|------|------|------|
| **iceoryx** | P0 | 直接链接 posh | 类型须可 relocatable |
| **vsomeip** | P1 | SOR→JSON 配置 | Boost 体积 |
| **CycloneDDS + idlc** | P1 | SOR→IDL→idlc | profile 可关 |

## Codegen

| 组件 | 建议 | 说明 |
|------|------|------|
| **自研 gf-codegen 模板** | P0 | Proxy/Skeleton、manifest |
| **cyclonedds idlc** | P1 | 仅类型/序列化层 |
| **cantools** | P1 | DBC import（主机） |
| **rosidl** | Defer | 仅 GMT ROS 桥 |

## ROS 生态（主机）

Foxglove、MCAP、PlotJuggler — P1–P2 外调；rclcpp 不上板。

## OTA（ucm）

| 候选 | 建议 | 备注 |
|------|------|------|
| **自研 ucm 核心** | P1 skeleton | 包描述 + 状态机 |
| **RAUC** | P1 评估 | A/B 槽位 |
| **OSTree** | P2 | 原子树 |
| **SWUpdate** | **排除** | 用户明确不用 |

## DoIP（diag）

| 候选 | 建议 |
|------|------|
| **doip-cpp 等** | P1 Spike |
| **最小自研 DoIP** | P1 备选 |

## Spike 列表

S1 iceoryx 双进程 · S2 SOR→idlc · S3 DBC import · S4 MCAP · S5 vsomeip 体积
