# ADC：Freespace 所有权与 gf-config 修改方案

> 配套 [fs_fov_bev_scheme.md](./fs_fov_bev_scheme.md)、[multi_cam_contract.md](./multi_cam_contract.md)。  
> **已对齐：** 行泊都在 FS 里规划；环视出 `FreespaceNear`；行车三段合成出 **`Freespace`**；BEV 行车图只订规划成品；**不再用 `D_see_m` 当 ADC 行车规划尺**。  
> 本文是 **wiring / 数据流 / 落地顺序**，动手前对照。

---

## 0. 目标态一句话

```text
surround ──► FreespaceNear ──► parking（近场规划）──► ParkingTrajectory
                          └──► driving_plus（第三段输入）
fcm       ──► Out ───────────► driving_plus（前视段）
ego       ──► EgoMotion ─────► driving / parking / surround / mode

driving_plus 合成 前视+后视+环视
          ──► Freespace          ──► BEV 行车图（只订这个）
          ──► Trajectory         ──► gateway / MCU（路径+执行；ADC 不以 D_see_m 为尺）
```

两套 image：行车订 `Freespace`；泊车订 `FreespaceNear`。服务并存，不冲突。

---

## 1. 服务与类型

### 1.1 保持

| 服务 | 写 | 读 | 语义 |
|------|----|----|------|
| `FreespaceNear` | `perception.surround` | `planning.parking`、`planning.driving_plus` | 环视近场原料（36 扇区 + 轴）。**不改名。** |
| `SurroundWorld` | surround | parking | 真目标 / 真车位 |
| `Perception_MESSAGE_Out_St` | fcm | driving_plus | 前视标线 / DYN |
| `EgoMotion` | gateway | 各规划 / surround / mode | 车态（≠ FS） |
| `Trajectory` | driving_plus | gateway | 行车路径+执行 |
| `ParkingTrajectory` | parking | gateway | 泊车路径 |

### 1.2 新增

| 服务 | 写 | 读 | 语义 |
|------|----|----|------|
| **`Freespace`** | **`planning.driving_plus`** | **BEV / live_tap / record**（行车图） | 行车三段合成可行驶。规划空间 = 观测空间。 |

建议类型（与 Near 同形，避免两套网格哲学）：

```text
struct Freespace {
  uint64_t timestamp_ns;
  float d_occ_m[36];   // 融合后扇区半径（车体 +x 前）
  float d_front_m;     // 前楔内净空（可到 120）
  float d_rear_m;      // ≤ 35
  float d_left_m;
  float d_right_m;
  uint8_t valid;
};
```

放在 `projects/adc/interfaces/planning_driving/io_types.hpp`（规划成品，不是感知）。  
**禁止** surround 发布 `Freespace`；**禁止** BEV 用 Near+`D_see_m` 再融。

### 1.3 `Trajectory.D_see_m`（ADC）

- 总线字段可暂留（AFC / 旧 HUD）。
- **ADC 行车 tick 不以它为规划尺**；路径裁剪、停车、横向走廊只读 `Freespace`。
- 若 HUD 仍要数字：从 `Freespace.d_front_m`（或前楔扇区）**派生**，写回 `D_see_m` 仅作旁路显示，不当输入。

---

## 2. gf-config 改什么

真源：`projects/adc/cfg/wiring.yaml` + `req.yaml`；compose 后 canvas 会出 `Freespace` 口。

### 2.1 类型导入

- `planning_driving/io_types.hpp` 增加 `Freespace`。
- `req.yaml` / bindings 增加服务 `semantic.Freespace`（与现有 `FreespaceNear` 并列）。
- `req.yaml` `services:` 触发：`Freespace: trigger: on_change`（跟 Near）。
- `observability.record.services` 增加 `Freespace`（行车图验收）；Near 仍录给泊车。

### 2.2 `deployments` / `bindings`

**`planning.driving_plus`**

```text
requires:  EgoMotion, Perception_MESSAGE_Out_St, FreespaceNear
provides:  Trajectory, Freespace          # 新增 Freespace
```

bindings outputs 增加：

```yaml
- service: semantic.Freespace
  type: Freespace
```

**`perception.surround`**：不变（仍只出 Near + World）。

**`planning.parking`**：订 Near + World + Ego；生命周期由 DriveParkFG，不订 VehicleMode。  
**注意：** `deployments.requires` 必须含 `FreespaceNear`（与 bindings / dataflow 一致）。只补 canvas `port_sides` / `port_slot_order` 而不写 require，画布会缺独立 In 口，边会叠到别的端口上。Verify 已门禁 `wiring_port_consistency`。

**观测（live_tap `wiring_all`）**：compose 后 tap 自动能订到 `Freespace`；BEV ingest 改认 `Freespace`（行车 SKU），Near 仅泊车图。

### 2.3 `dataflows`（逻辑边）

现有保留：

```text
surround → FreespaceNear → driving_plus
surround → FreespaceNear → parking
surround → SurroundWorld → parking
fcm → Out → driving_plus
gateway → EgoMotion → driving_plus / parking / surround / mode
driving_plus → Trajectory → gateway
parking → ParkingTrajectory → gateway
```

**新增一条：**

```text
planning.driving_plus → Freespace → （观测：iox_obs_foxglove / live_tap）
```

观测进程若不在 `wiring.yaml` 的 deployments 里（GMT tap 旁路），则：

- dataflow 仍声明 `driving_plus provides Freespace`；
- live_tap `wiring_all` 订阅该 Provide；
- **不要**再加 `surround → FreespaceNear → foxglove` 当行车主路径。

若以后把 foxglove 收进 SKU wiring，再显式：

```text
from: planning.driving_plus
service: services.semantic.Freespace
to: host.iox_obs_foxglove   # 或现有 tap 进程名
```

### 2.4 画布（验收接线）

`planning.driving_plus` 右/下增加 **Out:Freespace**（与 Trajectory 并列）。  
左/上仍是 In:Ego、Out、Near——**ego 与 Near 同节点 = 规划入口，正确**。

禁止：把 `Freespace` 画在 surround 上。

---

## 3. 数据流（运行时）

### 3.1 行车

```text
[front cam] → fcm → Out ─────────────────┐
[fl/fr/rl/rr] → surround → FreespaceNear ┼→ driving_plus
[gateway] → EgoMotion ───────────────────┘
                         │ fuse（车体光学契约）
                         │  前：front.fov，深≤120
                         │  后：rear fov，深≤35
                         │  环：Near 侧包络 ~5.25
                         ├─ Freespace ──► BEV 行车（只投影）
                         └─ Trajectory ─► gateway（点列在 FS 内）
```

### 3.2 泊车

```text
surround → FreespaceNear + SurroundWorld ┐
gateway  → EgoMotion                     ┼→ parking
（生命周期：mode.drive_park → DriveParkFG；不订 VehicleMode）
                         └─ ParkingTrajectory → gateway
BEV 泊车图订 Near（或 parking 若日后裁剪再发，仍不与行车 Freespace 混口）
```

### 3.3 合成规则（driving 内，BEV 不算）

与 [fs_fov_bev_scheme.md](./fs_fov_bev_scheme.md) §2–3 相同：扇区 `r(θ)` 落在前楔 / 后楔 / 侧带，空路用各段 cap，有障取近。结果写入 `Freespace.d_occ_m[]`。

---

## 4. 代码触点（相对 wiring）

| 层 | 改 |
|----|----|
| 接口 | `planning_driving/io_types.hpp` + `Freespace` |
| gf-config | `wiring.yaml` provides/bindings/dataflows/canvas；`req.yaml` services + record |
| compose | 重新 Verify/Compose，生成 Proxy/Skeleton |
| driving_plus | fuse 写入并 `Send(Freespace)`；路径在 FS 内；不把 Near 空 cap 当规划尺 |
| BEV | ingest `Freespace`；ADC 行车 **停订 Near 主轮廓**；paint 只投影、连续闭合 |
| Host SIL | giraffe 仍灌 Near 给 surround；**不要** Host 再算一套行车 FS |

AFC 工程 **不**加 `Freespace` 服务（单摄仍 `D_see`）。

---

## 5. 分步落地（避免假完成）

| 步 | 交付 | 验收 |
|----|------|------|
| **W0** | 类型 + wiring + compose 口齐 | gf-config 画布 driving 有 Out:Freespace；surround 仍只有 Near |
| **W1** | driving fuse 发布 `Freespace`（可先与现 paint 公式 1:1） | 日志/iceoryx 有包；空路前扇区到 ~120，后 ≤35 |
| **W2** | BEV 改订 `Freespace`，去掉行车 Near 旁路融 | 切模式：行车图随 Freespace，泊车图仍 Near |
| **W3** | ADC tick 路径/停点只裁 FS；`D_see_m` 仅派生或忽略 | 无前车不短在 15；有前车前瓣咬车 |
| **W4** | paint 连续闭合 + 可选 ±fov/2 参考射线 | 与 Cam1 左右缘同一扇门（车体等角，不是屏上量 100°） |

**假完成：** 口上有 `Freespace`、仍 `(void)` 不发，或 BEV 继续 Near+`D_see` 自融。

---

## 6. 非目标

- 完整 FS 网格塞进 `Trajectory`
- FailSafe `Perception_FS_Out` 当可行驶
- ChaseCam / BEV 旁观外参当产品 FOV
- parking 做 120 m 前视融合
- 为屏上「看起来 100°」改合同 fov

---

## 7. 验收口诀

> Near 是环视原料；Freespace 是行车成品。  
> 泊车吃 Near，行车吃 Freespace。BEV 各订各的。  
> Ego 进规划节点正常。角来自 gf-config，深前 120 / 后 35 / 侧 1.5 车道。
