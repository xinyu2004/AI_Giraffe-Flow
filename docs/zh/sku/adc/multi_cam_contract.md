# ADC 多摄合同（冻结）

> 通信层通用；paint/金源按 SKU（afc/adc）分叉。  
> **FS 与 `D_see` 同级要求（可见 + 进规划）** 的阶段方案见 [freespace_and_dsee_plan.md](./freespace_and_dsee_plan.md)。  
> **FOV / 距离唯一源 + BEV 画法** 见 [fs_fov_bev_scheme.md](./fs_fov_bev_scheme.md)。  
> **变道降级** 见 [lane_change_degrade_plan.md](./lane_change_degrade_plan.md)。  
> **BEV mount 透视（先验 FS，LC 走廊后置）** 见 [bev_mount_perspective_plan.md](./bev_mount_perspective_plan.md)。  
> **ADC backlog** 见 [backlog.md](./backlog.md)。  
> **gf-config / 数据流（Near vs Freespace）** 见 [freespace_wiring_plan.md](./freespace_wiring_plan.md)。

## 尺子

| | 单摄 afc | 多摄 adc |
|--|----------|----------|
| 主合同 | 前向 `D_see`（规划内部） | 近场 FS + 前视 Out；**fuse 必须进入 `D_see`/tick`**（禁止空转） |
| FCM | `Perception_MESSAGE_Out_St` | **不变**（无 fcm_plus） |
| 后视感知（变道） | `perception/rcm` → **`Perception_Rear_Out_St`** ← CARLA `rcm_truth`；**订 EgoMotion**（过期沉默） | 故障时规划 **禁止变道**（见 [lane_change_degrade_plan.md](./lane_change_degrade_plan.md)） |
| 环视/周视 | — | `SurroundWorld`（真目标/真车位）+ `FreespaceNear`（近场可行驶） |
| Trajectory | 路径+执行 | **ADC `D_see_m` 恒 0（无旁路）**；完整 FS 网格不上 traj |

`Perception_FS_Out` = FailSafe，**≠** freespace。

## 包络（周视 / 环视，不发明）

数值单源（stage-A）：[`fs_envelope_cal.hpp`](../../../../projects/adc/interfaces/fs_envelope/fs_envelope_cal.hpp)。前/侧/后分域，见 [fs_fov_bev_scheme.md §1.1](./fs_fov_bev_scheme.md)。

| 方位 | 概念 | 默认 envelope（cal 名） |
|------|------|----------------|
| 后向 | 周视 | `kFsRearCapM` **35 m**（与 Chase/BEV 互验）；`kFsRearFovDeg` **120°**（非整后半球） |
| 左/右 | 环视近场 | `kFsSideCapM` \|y\|≤**7** m（~2×3.5 m）；**≠**前视半宽 |
| 前向远距 | FCM | `kFsFrontFovDeg`＝合同 front.fov（默认 100°）；`kFsNearFrontCapM` ~15；空路远深 `kFsFrontFarCapM` / `D_see`（可到 120） |

**禁止** channel 空时 FillSilDemo / `SLOT_DEMO` 合成车位。无 valid pod → **不发** SurroundWorld / FreespaceNear。

## 数据流

```text
FCM → Out
surround → SurroundWorld + FreespaceNear   # 仅真 pod
perception.rcm → Perception_Rear_Out_St    # CARLA rcm_truth；变道后向
planning.driving_plus → fuse → Freespace + Trajectory
parking → FreespaceNear + SurroundWorld（不算 120 m 融合）
```

相机选用、标定投影：仅 surround APP 内。  
金源：默认复用 AFC tick + C 侧 fuse；行为分叉再拆 plus `.m`。

## 观测

- Foxglove adc：BEV 米窗 x∈[**−35**,+120]；行车验 **`Freespace`+Trajectory**（+Out 叠画）；泊车验 **Near+ParkingTrajectory**；无 `Dxx`/`LC`
- 仅 ingest 真样本；FS：后 **35 m @ FOV 120°** / 侧 7；**无轴 stub**；空前向 Near cap **不钳** `D_see`
- ChaseCam：1 windshield · 2 bev_afc · 3 bev_adc · 4 overhead；旁观 ≠ 产品槽
  （文件：`carla_scenarios/config/spectator/*.mount.json`；paint：`iox_obs_foxglove/config/{afc,adc}/bev.mount.json`）
- `GF_SYNTH_BEV`：二进制默认关；SIL 可开；**空 LiveBevState 不发 BEV 图**

## 风格

函数化、分层、单源；**宁可沉默，不发假数据**。假完成收口见 `.cursor/rules/engineering-principles.mdc`。
