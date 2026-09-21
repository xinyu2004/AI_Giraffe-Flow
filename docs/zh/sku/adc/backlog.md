# ADC backlog（规控 / 感知 / 平台）

> 工作项登记；细则见链接。原则：假完成收口、禁止半套变道、控件→内存→校验→写盘。

## 进行中 / 待动手

| ID | 项 | 说明 |
|----|-----|------|
| **BL-LC-P1** | 变道健康门 | **已落** |
| **BL-LC-P2** | error → PER | **已落**：`LcInhibitEgo/Surround/Rcm` 上升沿 `ReportEvent(process,…)` → collector `dtc_map` `0xC01C01..03`；走廊-only 不报 DTC（P3 前预期）。需 **recompose** 刷新 `collector_config.hpp` |
| **BL-LC-P3** | 走廊 + 真变道 | **后置**：等 FS BEV 目视验收通过（见 [bev_mount_perspective_plan.md](./bev_mount_perspective_plan.md)） |
| **BL-BEV-ORTHO** | 垂直俯视 mount 验钥匙孔 | **已落**：nadir 验收后已恢复斜视 |
| **BL-BEV-MOUNT** | 斜视 mount 变换 | **已落**：`adc/bev.mount.json` = 斜视旁观（x=-45 z=48 look_x=40） |
| **BL-FG-SIL** | DrivePark 抽检 | FCM+RCM 已挂 `DrivingActive`；Parking：FCM/RCM 停、surround+parking 吃 Near |
| **BL-RCM-OBS** | RCM 可观测 | 现仅启动一行 stdout；无周期心跳。需 FrameWatch / 稀疏 diag（与主链 log 对齐），便于确认 truth/Ego/Send |
| **BL-FAKE-PARK** | 泊车 invent 车位 | 无真源沉默；禁 `SLOT_DEMO` |
| **BL-FAKE-DET** | FCM Detect 空转 | 勿宣称视觉已通 |
| **BL-LOG-NOISE** | stdout 节流口径 | gateway `Trajectory#` / `[fs][diag]` 靠 `GF_APP_LOG_EVERY` + on-change；默认 40；SIL 验主链依赖这些串 |

## 已落（勿回退）

- EgoMotion → FCM / surround / RCM；surround/RCM stale 沉默  
- RCM ← `rcm_truth`；exec：FCM+RCM ∈ DriveParkFG/`DrivingActive`，surround ∈ MachineFG  
- gf-config：平台控件 Save/Verify 前 `flush_to_session`；`active_in` 先对齐再 harvest  
- **LC P1**：`MakeLcGate` + `ApplyLcInhibit`；缺 Near 默认不自由；无走廊恒 inhibit  
- **LC P2**：健康故障上升沿 `ReportEvent` → DTC `0xC01C01..03`（走廊-only 不报）  

## 不做（本表）

- 半套变道（有旗无走廊乱打方向）  
- 观测另算最终行车 FS；FailSafe ≠ freespace  
- occupy/光学写进 FCM `VR_End`  
