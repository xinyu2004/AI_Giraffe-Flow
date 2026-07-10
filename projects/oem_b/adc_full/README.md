# OEM B / ADC（行泊一体）

域控制器项目：前视 + 环视 + USS + 泊车/行车规划 + MCU。集成工程师主战场示例。

## SOA Apps（OEM 主图）

| process | 角色 | semantic |
|---------|------|----------|
| `sensing.uss` | 超声 | `UssZones` |
| `perception.front` | 前视 | `FrontObjectList` |
| `perception.surround` | 环视 | `SurroundWorld` |
| `perception.driving.nullmax` | 行车融合感知 | `DrivingObjectList` |
| `perception.parking` | 泊车感知 | `ParkingWorld` |
| `planning.driving` | 行车规划 | `Trajectory` |
| `planning.parking` | 泊车规划 | `Trajectory` / `ActuatorCommand` |

## Adapters（边界，附录可画）

| process | 角色 |
|---------|------|
| `adapter.vehicle_can_gateway` | CAN → EgoMotion / VehicleModeStatus |
| `adapter.mcu_cp_gateway` | MCU IPC ↔ 轨迹/执行器 |

## 平台（不进 SOA 主图）

`iox-roudi`、exec_manager — 仅开发/部署可见。

### 你关心的泊车链（SOA App 段）

```text
sensing.uss ─UssZones─► perception.parking ─ParkingWorld─► planning.parking
     ▲                        ▲
 EgoMotion（来自 Adapter）   SurroundWorld / VehicleModeStatus
```

完整角色说明：[PROCESS_ROLES.md](../../PROCESS_ROLES.md)

```bash
gf-codegen compose --project projects/oem_b/adc_full/project.yaml
```
