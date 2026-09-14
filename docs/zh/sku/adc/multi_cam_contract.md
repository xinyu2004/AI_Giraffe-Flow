# ADC 多摄合同（冻结）

> 通信层通用；paint/金源按 SKU（afc/adc）分叉。  
> **FS 与 `D_see` 同级要求（可见 + 进规划）** 的阶段方案见 [freespace_and_dsee_plan.md](./freespace_and_dsee_plan.md)。

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
| 后向 | 周视 | x∈[−40,0] m，\|y\|≤12 |
| 左/右 | 环视近场 | \|y\|≤10 m 且 x∈(0,10]（AVM 近障文献常 ~5–6 m；先取 10） |
| 前向远距 | FCM | surround **不**合成前向远目标；Near 前向 cap 仅 ~15 m |

**禁止** channel 空时 FillSilDemo / `SLOT_DEMO` 合成车位。无 valid pod → **不发** SurroundWorld / FreespaceNear。

## 数据流

```text
FCM → Out
surround → SurroundWorld + FreespaceNear   # 仅真 pod
planning.driving_plus → fuse → 钳 D_see → tick → Trajectory
parking → FreespaceNear + SurroundWorld（不算 120 m 融合）
```

相机选用、标定投影：仅 surround APP 内。  
金源：默认复用 AFC tick + C 侧 fuse；行为分叉再拆 plus `.m`。

## 观测

- Foxglove adc：BEV **同一米窗** x∈[−40,+120]；灰=`VR_End`；青洗/`D` 只在 +x
- 仅 ingest 真样本；FS 扇区按方位 cap（后 40 / 侧 10）；**无轴 stub**
- ChaseCam：1 风挡 · 2 chase（抽检 BEV 前向）· 3 俯视（验侧后）；旁观 ≠ 产品槽
- `GF_SYNTH_BEV`：二进制默认关；SIL 可开；**空 LiveBevState 不发 BEV 图**

## 风格

函数化、分层、单源；**宁可沉默，不发假数据**。假完成收口见 `.cursor/rules/engineering-principles.mdc`。
