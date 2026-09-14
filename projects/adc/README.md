# ADC — 行泊一体 SKU（阶段 A 骨架）

从 AFC 模板分叉；**绝对独立**。无 USS、无 MCU。

| 阶段 | 状态 |
|------|------|
| **M** Modules 根基 | 共用 `middleware/`（EM 首启） |
| **A** 本 SKU 骨架 | Front+Surround 形态、Mode/VehicleMode、gateway 选 traj | 已完成 |
| **P** 算法/场景 | Surround + `FreespaceNear`；`planning.driving_plus`；DriveParkFG | 进行中 |

多摄合同：[docs/zh/sku/adc/multi_cam_contract.md](../../docs/zh/sku/adc/multi_cam_contract.md)

```bash
# compose / generate（或 gf-config Verify+Generate）后：
bash projects/adc/scripts/compile_sil.sh
# 调试帧：GF_FRAME_SOURCE=carla（ego 已 freeze carla）
# ChaseCam=2 后高空 / =3 俯视泊车；Foxglove GF_BEV_SKU=adc（run_sil 默认）
GF_FRAME_SOURCE=carla bash projects/adc/scripts/run_sil.sh
# DrivePark：GF_SLOT_CONFIRMED=1 + 停稳，或 ModeHint cosim
```

行泊：**DriveParkFG** 差集起停 `planning.driving_plus` / `planning.parking`  
（见 [drive_park_fg.md](../../docs/zh/architecture/drive_park_fg.md)）。  
Mode Manager → `RequestTransitionNamed`；gateway 只转发存活 traj。  
感知 MachineFG 常驻。验收：`smoke_sil_drive_park_fg.sh`。
