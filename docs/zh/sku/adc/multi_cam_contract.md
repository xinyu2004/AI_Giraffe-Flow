# ADC 多摄合同（冻结）

> 通信层通用；paint/金源按 SKU（afc/adc）分叉。  
> **FS 与 `D_see` 同级要求（可见 + 进规划）** 的阶段方案见 [freespace_and_dsee_plan.md](./freespace_and_dsee_plan.md)。  
> **FOV / 距离唯一源 + BEV 画法** 见 [fs_fov_bev_scheme.md](./fs_fov_bev_scheme.md)。  
> **gf-config / 数据流（Near vs Freespace）** 见 [freespace_wiring_plan.md](./freespace_wiring_plan.md)。

## 尺子

| | 单摄 afc | 多摄 adc |
|--|----------|----------|
| 主合同 | 前向 `D_see`（规划内部） | 近场 FS + 前视 Out；**fuse 必须进入 `D_see`/tick`**（禁止空转） |
| FCM | `Perception_MESSAGE_Out_St` | **不变**（无 fcm_plus） |
| 环视/周视 | — | `SurroundWorld`（真目标/真车位）+ `FreespaceNear`（近场可行驶） |
| Trajectory | `D_see_m` 等 | **形状不变**；**完整 FS 网格不上 traj**（标量 `D_see_m` + 事件 Near 仍上总线） |

`Perception_FS_Out` = FailSafe，**≠** freespace。

## 包络（周视 / 环视，不发明）

| 方位 | 概念 | 默认 envelope |
|------|------|----------------|
| 后向 | 周视 | 纵深 **35 m**（与 Chase/BEV 互验）；**FOV cal 120°**（非整后半球） |
| 左/右 | 环视近场 | \|y\|≤5.25 m（~1.5×3.5 m 车道）且 x∈(0,10] |
| 前向远距 | FCM | FOV = **合同 front.fov（默认 100°）**；Near 前 cap ~15；空路融合前向跟 `D_see`（可到 120） |

**禁止** channel 空时 FillSilDemo / `SLOT_DEMO` 合成车位。无 valid pod → **不发** SurroundWorld / FreespaceNear。

## 数据流

```text
FCM → Out
surround → SurroundWorld + FreespaceNear   # 仅真 pod
planning.driving_plus → fuse → Freespace + Trajectory
parking → FreespaceNear + SurroundWorld（不算 120 m 融合）
```

相机选用、标定投影：仅 surround APP 内。  
金源：默认复用 AFC tick + C 侧 fuse；行为分叉再拆 plus `.m`。

## 观测

- Foxglove adc：BEV 米窗 x∈[**−35**,+120]（身后可读 ~35 m，与 ChaseCam=2 互验）；**验规划融合 FS**（前空→`D_see`）；有 Near 时**不画**单独青洗/`D` 走廊
- 仅 ingest 真样本；FS：后 **35 m @ FOV 120°** / 侧 5.25；**无轴 stub**；空前向 Near cap **不钳** `D_see`
- ChaseCam：1 风挡 · 2 chase（~35 m 后）· 3 俯视；旁观 ≠ 产品槽
- `GF_SYNTH_BEV`：二进制默认关；SIL 可开；**空 LiveBevState 不发 BEV 图**

## 风格

函数化、分层、单源；**宁可沉默，不发假数据**。假完成收口见 `.cursor/rules/engineering-principles.mdc`。
