# 进程角色：谁是 SOA App？

集成工程师连线时，先分清三类进程。**OEM 架构报告默认只画 SOA App**；Adapter / 平台 daemon 放「运行时依赖」附录。

## 三类进程

| 类别 | 是什么 | OEM 报告 | 例子 |
|------|--------|----------|------|
| **SOA App** | 提供/消费 **semantic 服务** 的业务进程 | **主图节点** | 前视感知、环视、USS、泊车感知、行车/泊车规划 |
| **Adapter** | 车外协议 ↔ semantic 的边界进程（CAN / MCU IPC） | 可画为边界框，或附录 | `adapter.vehicle_can_gateway`、`adapter.mcu_cp_gateway` |
| **平台 daemon** | 中间件基础设施 | **不画进 SOA 图** | `iox-roudi`、exec_manager、phm |

```text
        ┌──────────── Adapter ────────────┐     ┌──────── SOA Apps ────────┐
 CAN ─► │ vehicle_can_gateway             │─Ego─►│ sensing.uss              │─UssZones─►│
        │                                 │      │ perception.front/surround│            │
        │                                 │      │ perception.parking       │─Parking──►│ planning.*
 MCU ─► │ mcu_cp_gateway                  │◄─Traj│                          │            │
        └─────────────────────────────────┘      └──────────────────────────┘
                         ▲
              平台：iox-roudi / EM（开发人员可见，OEM 主图不画）
```

## 你关心的那条链（按 App 拆开）

```text
EgoMotion ──► sensing.uss ──► UssZones ──► perception.parking ──► ParkingWorld ──► planning.parking
```

| 边 | 生产者进程 | 类别 | 消费者进程 | 类别 |
|----|------------|------|------------|------|
| EgoMotion | `adapter.vehicle_can_gateway` | Adapter | `sensing.uss` | **SOA App** |
| UssZones | `sensing.uss` | **SOA App** | `perception.parking` | **SOA App** |
| ParkingWorld | `perception.parking` | **SOA App** | `planning.parking` | **SOA App** |

结论：这条链上 **USS / 泊车感知 / 泊车规划是 SOA App**；EgoMotion 的源头是 **Adapter**（不是业务 App）。

## 本仓模块示例 ↔ 进程

> **接口布局：** 各交付项目的 `interfaces/` 下维护 `io_types.hpp`（无顶层共享目录）。  
> `wiring.yaml` 的 `modules[].hpp` **只写路径引用**。详见 [MODULE_INTERFACE_LAYOUT.md](MODULE_INTERFACE_LAYOUT.md)。  
> `middleware/ucm`、`middleware/diag` 是平台 API，**不是**模块 `io_types.hpp`。

| 模块名 | process id | 类别 | 典型项目 |
|--------|------------|------|----------|
| `perception_front` | `perception.front` | SOA App | OEM A AFC、OEM B ADC |
| `perception_surround` | `perception.surround` | SOA App | OEM B ADC |
| `uss_sensing` | `sensing.uss` | SOA App | AFC+USS、ADC |
| `perception_parking` | `perception.parking` | SOA App | ADC（行泊） |
| `perception_driving` | `perception.driving.nullmax` | SOA App | 旧 demo / 可作行车备选 |
| `mcu_cp_gateway` | `adapter.mcu_cp_gateway` | Adapter | 有 MCU 的项目 |
| （无 hpp，平台 adapter） | `adapter.vehicle_can_gateway` | Adapter | 凡有车身 CAN |
| （外仓） | `planning.driving` / `planning.parking` | SOA App | 按 SKU |

规划模块本仓暂无 `io_types.hpp` 示例，在 wiring 里用 `package:` 指向外仓即可。

**走查（推荐先读）：** [oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md](oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md)

## 三个交付项目（集成工程师工作区）

| 路径 | 产品名 | 要点 |
|------|--------|------|
| [`oem_a/afc_no_uss`](oem_a/afc_no_uss/) | AFC 前视（无 USS） | 仅前视 + 行车规划；无 `sensing.uss` |
| [`oem_a/afc_with_uss`](oem_a/afc_with_uss/) | AFC 前视（有 USS） | 前视 + 独立 USS；泊车感知可选/简化 |
| [`oem_b/adc_full`](oem_b/adc_full/) | ADC 行泊一体 | 前视 + 环视 + USS + 泊车/行车规划 + MCU |

旧目录 [`oem_demo/vehicle_demo`](oem_demo/vehicle_demo/) 保留作对照，新工作以以上三项目为准。
