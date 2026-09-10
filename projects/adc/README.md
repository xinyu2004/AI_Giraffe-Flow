# ADC — 行泊一体 SKU（阶段 A 骨架）

从 AFC 模板分叉；**绝对独立**。无 USS、无 MCU。

| 阶段 | 状态 |
|------|------|
| **M** Modules 根基 | 共用 `middleware/`（EM 首启） |
| **A** 本 SKU 骨架 | Front+Surround 形态、Mode/VehicleMode、gateway 选 traj | 已完成 |
| **P** 算法/场景 | Surround cosim + `m_park_tick`；**DriveParkFG 差集** | 进行中 |

```bash
# …
bash projects/adc/scripts/compile_sil.sh
# DriveParkFG: Mode→SM→EM set-diff (DrivingActive|ParkingActive)
# Confirm park: GF_SLOT_CONFIRMED=1 + stop, or ModeHint cosim
bash projects/adc/scripts/run_sil.sh
```

行泊：**DriveParkFG**（`kind: mode` + 进程 `active_in`）差集起停 `planning.driving` /
`planning.parking`（见 [drive_park_fg.md](../../docs/zh/architecture/drive_park_fg.md)）。  
Mode Manager 调通用 `RequestTransitionNamed`；`VehicleMode` 仍发；**gateway 只转发**存活 traj。  
感知在 MachineFG 常驻。验收：`smoke_sil_drive_park_fg.sh`（勿把 `smoke_sil_sm_fg` 当差集证明）。
