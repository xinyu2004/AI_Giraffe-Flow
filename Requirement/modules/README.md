# modules/ — 模块 IO 示例（只交 hpp）

| 谁 | 交什么 | 不交什么 |
|----|--------|----------|
| **模块工程师** | `io_types.hpp` | JSON、YAML、连线、SKU |
| **系统工程师** | `projects/.../integration/wiring.yaml` | — |

## 示例目录 ↔ SOA App

| 目录 | process id | 类别 | 用于 |
|------|------------|------|------|
| [perception_front/](perception_front/) | `perception.front` | SOA App | AFC / ADC |
| [perception_surround/](perception_surround/) | `perception.surround` | SOA App | ADC |
| [uss_sensing/](uss_sensing/) | `sensing.uss` | SOA App | AFC+USS / ADC |
| [perception_parking/](perception_parking/) | `perception.parking` | SOA App | ADC |
| [perception_driving/](perception_driving/) | `perception.driving.nullmax` | SOA App | ADC 行车融合 |
| [mcu_cp_gateway/](mcu_cp_gateway/) | `adapter.mcu_cp_gateway` | **Adapter** | ADC |

规划进程在 wiring 里用外仓 `package:`，本仓暂无 hpp。

进程分类总表：[projects/PROCESS_ROLES.md](../../projects/PROCESS_ROLES.md)
