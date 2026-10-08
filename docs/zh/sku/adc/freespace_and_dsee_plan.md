# ADC：Freespace 与 D_see（可见 + 进规划）方案

> 配套 [multi_cam_contract.md](./multi_cam_contract.md)、[两把尺子](../../../.cursor/rules/two-rulers-vr-and-dsee.mdc)、[做事原则](../../../.cursor/rules/engineering-principles.mdc)。  
> 目标一句话：**可行驶边界要像 `D_see` 一样——规控吃、BEV 看得到；完整网格不上 Trajectory。**

---

## 1. 概念对齐（三样东西，勿混）

| 名 | 是什么 | 谁写 | 谁吃 | BEV |
|----|--------|------|------|-----|
| **标线** `VR_End` | 线质量还在多远 | FCM / 地图 | 规划只当 `D_vr` | **灰线** |
| **驾驶尺** `D_see` | 本拍敢当前向畅通多远（内部） | `driving_plus`：`slew(min(D_vr,D_occ,D_fov,D_wx,D_fs_fwd,cap))` | 路径长、`T_plan`、`v_cap_vis`、HUD `D` | **青洗 + 青横杠**（仅 +x） |
| **近场 FS** `FreespaceNear` | 周向 Empty180（`d_r_m[180]`+`type`） | surround | 行车 compose 基线输入；**泊车：走廊/碰撞主输入** | **同米窗 180 轮廓** |
| FailSafe `Perception_FS_Out` | 功能安全失效 | FCM | 诊断/降级 | 不画成可行驶 |

```text
行车最终「敢开」的前向尺 = D_see（内部）
  ← 仍含 D_vr / D_occ / D_fov / D_wx
  ← 加上 fuse 后的前向 FS 分量 D_fs_fwd（**仅真实前向近障**；空 Near 前向 cap≠砍 D_see）

周向/泊车敢开的包络 = FreespaceNear（+ SurroundWorld 槽/障碍）
  ← 不上 Trajectory 整网；泊车进程内直接订
```

**与旧口头「完整 FS 不上总线」不矛盾：**  
不上的是 **稠密网格 / 最终融合副本**；上的是既有 **`Trajectory.D_see_m`（标量）** + 既有 **`FreespaceNear` 事件**。观测与规控 **禁止各算一套最终 FS**。

---

## 2. 目标行为（验收语言）

### 2.1 行车（driving_plus）

1. surround 发 `FreespaceNear`；FCM 发 `Out`；二者在 **planning 进程内** fuse（无新融合 APP）。
2. fuse 结果 **进入** `D_see` / tick（禁止算完 `(void)`）。
3. 路径只画在青区（≤ `D_see`）；变道门控可先读 `rear_*_free`，**转向后挂**（禁止半套变道）。
4. BEV：米窗 x∈[−40,+120]；灰=`VR_End`；青=`D_see`；FS=近场扇区轮廓。

### 2.2 泊车（后阶段）

1. `parking` **订** `FreespaceNear` + `SurroundWorld`，**不算** 120 m 前视融合。
2. 走廊 / 碰撞 / 库位几何吃 FS 包络 + slots。
3. BEV 同窗可画槽位与 FS；ChaseCam=3/4（bev_adc / overhead）仅旁观。

### 2.3 观测

| 可见物 | 数据源 | 禁止 |
|--------|--------|------|
| 灰线 | Out LH `VR_End` | 把 occupy/FS 写进 VR |
| 青洗 / `D` | **AFC**；ADC **删除**（无 `D_see_m` 旁路） | Foxglove 重算「最终行车 FS」 |
| FS 环 | 行车：`Freespace`；泊车：`FreespaceNear` | 行车再订 Near 当主轮廓 |

---

## 3. 架构方案

```text
                    ┌─ Perception_MESSAGE_Out_St (FCM, 不变)
surround ──► FreespaceNear ──┐
         └─ SurroundWorld ───┤
                             ▼
              planning.driving_plus
              ┌──────────────────────────┐
              │ FuseDrivingFs (前处理)    │
              │  → D_fs_fwd / 侧后净空   │
              │ m_plan_tick / 内部 D_see │
              │  → Freespace + Trajectory（ADC 无 D_see_m）│
              └──────────────────────────┘
                             │
              parking ───────┴── Near+World → ParkingTrajectory

Foxglove 行车: Out + Ego + Freespace + Trajectory
Foxglove 泊车: Near + World + ParkingTrajectory
          同一 BevWindow；ingest 不融
```

### 3.1 fuse 进 `D_see`（P0 假完成收口）

```text
forward_clear ← lead / 本车道 DYN（既有 D_occ 路径）
d_fs_fwd      ← min(forward_clear, FreespaceNear.d_front_m, 相关扇区)
D_see         ← slew(min(D_vr, D_occ, D_fov, D_wx, d_fs_fwd, cap))
```

- 邻道扇区 **不砍** 前向 `D_see`（与两把尺子一致）。
- `lane_change_candidate`：可打日志 / HUD；**不改 steer** 直到变道走廊里程碑。

### 3.2 金源策略（现阶段）

- **默认：** 继续复用 AFC `m_plan_tick`；**FS 钳位在 C 前处理**（单一真相写进合同）。
- **仅当** plus 横向/变道与 AFC 行为分叉到 cal 放不下时，再拆 `m_plan_tick_plus.m`。

### 3.3 Paint / 双 bin

- 保持 `gf_foxglove_ws` + `gf_host_bev_ws` + **共用 paint** + `GF_BEV_SKU`。
- 真 compose 分叉：**后置**（开关塞不下图层语义时再拆）。

---

## 4. 分阶段计划

| 阶段 | 交付 | 验收 | 明确不做 |
|------|------|------|----------|
| **P0 收口假完成** | fuse→`D_see`；BEV 订并画 `FreespaceNear`；合同/原则文档 | 有近障：HUD `D` 与青杠缩短；BEV 有扇区轮廓；日志可见 fuse | 变道转向；真多摄投影；compose 分叉 |
| **P1 看见对齐** | 青洗走廊（+x 至 `D_see`）；FS 轮廓与轴净空可读；ChaseCam 文档旁观≠产品槽 | 空直道青区跟 `D`；身后无青洗；重启 SIL 米窗连续 | 泊车搜索 |
| **P2 变道门控（薄）** | ~~HUD LC~~ **ADC 已撤**；变道转向后挂 | — | 半套打方向 |
| **P3 泊车吃 FS** | parking 订 Near；`m_park_tick` 按扇区裁剪路径 | 库位路径不穿扇区硬边 | 120 m 融合进泊车 |
| **P4 surround 产品化** | 标定投影→稠密近场（合同：扇区可加密，**不改名**） | 多摄 SIL 与扇区一致 | 发明 `fcm_plus` |
| **P5 plus 金源（可选）** | 仅行为分叉时拆 `.m` | Host/C 1:1 | 为改名而拆包 |

### 落地状态（实现跟踪）

| 阶段 | 状态 |
|------|------|
| P0 fuse→`D_see`（`x_end` 钳） | **已落地** |
| P1 青洗 + HUD `D` + FS 环加粗 | **已落地** |
| P2 LC 意图位 + HUD `LC` | **已落地（转向在金源；remap≠reg；FS 进门+hold）** |
| P3 parking clip by Near | **已落地（几何 stub+裁剪）** |
| P4 真多摄投影 | **未做**（SIL demo 加强前后障便于看效果） |
| P5 plus 金源分叉 | **未做**（仍复用 AFC tick） |

---

## 5. 与「六条半截」对照

| 条目 | 本方案处置 |
|------|------------|
| FreespaceNear fuse 空转 / BEV 不画 | **P0–P1 必做**；完整 FS 仍不上 traj |
| driving_plus 名薄壳 | 名保留；**能力 = fuse 进尺 + 钩子**；真变道 P2+ |
| ChaseCam 2/3/4 | **文档/验收对齐**，不与产品槽强绑几何 |
| 周视 stub | **P4**；此前标 stage-A |
| 金源挂 AFC | **默认合法**；P5 条件触发 |
| 双 bin + SKU 开关 | **默认合法**；分叉后置 |

---

## 6. 实现触点（代码地图）

| 层 | 路径 |
|----|------|
| Near 类型 | `projects/adc/generated/include/perception_surround/io_types.hpp` |
| surround 算/发 | `apps/perception/surround/` |
| fuse | `apps/planning/driving_plus/src/fuse_driving_fs.hpp` + `main.cpp` → tick |
| 金源/ops | AFC pack → `driving_plus/oct_gen`（直至 P5） |
| BEV | `tools/gmt_board/iox_obs_foxglove/`：`bev_window`、`apply_sample(FreespaceNear)`、青洗 |
| 合同 | 本文 + `multi_cam_contract.md` |

---

## 7. 风险与禁令（摘录）

- 禁止观测与规控双算最终行车 FS。
- 禁止把 FS/occupy 写进 FCM `VR_End`。
- 禁止为身后黑屏单独 `draw_rear_lanes`；改统一米窗。
- 禁止半套变道。
- 禁止用「改名 driving_plus」冒充能力包交付。
