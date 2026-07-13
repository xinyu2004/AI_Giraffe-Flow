# OEM B / ADC（行泊一体）

域控制器项目：前视 + 环视 + USS + 泊车/行车规划 + MCU。

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

## Adapters（边界）

| process | 角色 |
|---------|------|
| `adapter.vehicle_can_gateway` | CAN → EgoMotion / VehicleModeStatus |
| `adapter.mcu_cp_gateway` | MCU IPC ↔ 轨迹/执行器 |

## 平台（不进 SOA 主图）

`iox-roudi`、exec_manager — 仅开发/部署可见。

```text
sensing.uss ─UssZones─► perception.parking ─ParkingWorld─► planning.parking
     ▲                        ▲
 EgoMotion（Adapter）   SurroundWorld / VehicleModeStatus
```

完整角色：[PROCESS_ROLES.md](../../PROCESS_ROLES.md)

## 命令（P0 已通）

```bash
# 务必在仓库根
gf-codegen compose --project projects/oem_b/adc_full/project.yaml
gf-codegen lint projects/oem_b/adc_full/gf.sor.json
gf-codegen generate projects/oem_b/adc_full/gf.sor.json --out projects/oem_b/adc_full/generated/

# lineage：projects/oem_b/adc_full/reports/signal_lineage_report.yaml
```

iceoryx 双进程 SIL 演示仍以 [`afc_with_uss`](../oem_a/afc_with_uss/) 为准（拓扑更小）：

```bash
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh
```
