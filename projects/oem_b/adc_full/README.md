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

## MCU 桌面联调（P1 · 无真 MCU）

```bash
bash scripts/verify/oem_b_adc_full/smoke_mcu_desktop.sh
```

构建 `cp_ipc_peer`（模拟 CP）+ `mcu_cp_gateway`（AP），经 `cross_domain_ipc` Unix socket 互传 `IPC_CanInfo_*` / `TrajPlot` / `P_Parking`。

## 平台（不进 SOA 主图）

`iox-roudi`、exec_manager — 仅开发/部署可见。

```text
sensing.uss ─UssZones─► perception.parking ─ParkingWorld─► planning.parking
     ▲                        ▲
 EgoMotion（Adapter）   SurroundWorld / VehicleModeStatus
```

完整角色：[PROCESS_ROLES.md](../../PROCESS_ROLES.md)

## 命令（集成）

```bash
# 人工：开 GUI，保存即 compose；需要 C++ 头时点 Generate（或下面 CLI）
gf-config projects/oem_b/adc_full/project.yaml

# CI / 无 GUI
python -m gf_codegen.compose --project projects/oem_b/adc_full/project.yaml
gf-codegen lint projects/oem_b/adc_full/gf.sor.json
gf-codegen generate projects/oem_b/adc_full/gf.sor.json --out projects/oem_b/adc_full/generated/

# lineage：projects/oem_b/adc_full/reports/signal_lineage_report.yaml
```

iceoryx 双进程 SIL 演示仍以 [`afc_with_uss`](../oem_a/afc_with_uss/) 为准（拓扑更小）：

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_sil.sh
```
