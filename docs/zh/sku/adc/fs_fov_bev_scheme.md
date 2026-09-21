# ADC：FOV / 距离包络 / 融合 FS / BEV 画法（整套方案）

> 配套 [multi_cam_contract.md](./multi_cam_contract.md)、[freespace_and_dsee_plan.md](./freespace_and_dsee_plan.md)、两把尺子。  
> **观测 / CARLA 编号 / paint bev.mount / Foxglove raw 金源：** [optical_mount_fs_plan.md](./optical_mount_fs_plan.md)（env 1/2/3/4 ↔ windshield·bev_afc·bev_adc·overhead；paint 配置在 iox_obs_foxglove）。  
> **目标：** 前后距离与 FOV **唯一、可延续**；来自 **gf-config 用户配置**；pygame 与 BEV **同一扇门**；行泊都在 FS 里规划，BEV **只验规划融合后的 FS**。

---

## 0. 一句话

```text
gf-config 相机安装（外参 + fov）
  → camera_contract / generated hpp
  → 感知 Near 扇区包络 + 规划 fuse
  → surround：FreespaceNear（泊车 / 行车第三段）
  → driving_plus：Freespace（行车三段成品）→ BEV 行车只订这个
  → ADC 行车不以 D_see_m 为尺，且 **不写 / BEV 不画**（详见 freespace_wiring_plan.md）
```

旁观（ChaseCam / BEV 虚拟相机）**只用于互验看得清**，**不进**产品 FOV，**不进** `D_see`。

---

## 0.1 参数归属：SOR / 标定 / BEV 旁观（先分清再谈光学）

生活直觉「远处像素小 → 汇聚」是对的；工程上要把量拆成三类，**禁止混写进同一层公式**。

| 类 | 是什么 | 典型量 | 谁定 | 谁用 |
|----|--------|--------|------|------|
| **SOR / 产品合同** | 客户/SKU 冻结的能力边界与默认 | 前深 cap **120 m**；Near 前重叠 **~15 m**；后深 **35 m**；扇区数 **36**；默认 front.fov **100°**（未改配置时） | SOR → `fs_envelope_cal` / compose 注入 | Near 空场 cap、fuse 远顶上限、米窗前后沿互验 |
| **标定 / gf-config（真光学）** | 相机安装与成像几何 | 每槽 `mount.{x,y,z,pitch,yaw,roll,fov}`；分辨率 `w×h`；可选内参（fx,fy,cx,cy）若有 | 用户配置 → `camera_contract` | **前视光学契约**、pygame Cam、光锥∩地面、侧包络重标定 |
| **BEV / Chase 旁观** | 只为「看得清」的虚拟相机 | `CamBack` / `CamHeight` / `CamLook`、米窗裁切、线宽颜色 | 观测实现 | **仅 paint**；**禁止**当产品 FOV / 写进 FS / `D_see` |

**侧 7：** 名义写在 cal（SOR 冻结），**语义**是环视外参 → 地面交线标定出的近场横距；外参大改应重标定，不是前视 FOV 算出来的。

```text
SOR 定「能多远 / 默认多宽角」
标定定「这台车相机从哪看、朝哪看、张多大」
BEV 定「旁观者站哪才看得见」——与前两行无关
```

---

## 0.2 真正的光学契约（前视；补生活直觉）

### 生活说法 → 工程说法

| 生活 | 工程 |
|------|------|
| 远处东西在画面里很小、往中间收 | 针孔/透视投影：物距大 → 像高/像宽占像素少；平行线交于灭点 |
| 能看见的路面是一块「近宽远收」的区域 | **相机光锥 ∩ 地面（z=0）**，再加远距/质量门 |
| FS 来自摄像头模拟感知 | 前空场作者 = **前视可见地面**（± 障碍占用），不是旁观鸟瞰审美，也不是「车原点等方位角楔」 alone |

### 定义（产品前视槽 `front`）

坐标系：车体 **+x 前、+y 左、+z 上**。相机位姿来自合同 `front.mount`（例：x≈0.55 m，z≈1.35 m，pitch≈−5°，fov=100°）。

```text
光学空场（前，空路）=
    { 地面点 P | P 落在前视光锥内
                 ∧ 纵向距离 ≤ d_empty（SOR 远顶 / VR / 质量门）
                 ∧ 像素有效（在图像矩形内、可选畸变模型） }

有障：在上述集合上按车道带减去障碍（兔耳 = 结果）
```

**光锥**由标定给出：光心 `C = mount.(x,y,z)`，姿态 `pitch/yaw/roll`，水平/垂直张角（合同 `fov`；若仅给水平 fov，竖直由宽高比推，或另配 vfov）。

**近大远小**出在哪：

1. **图像域（感知真源）：** 同一物理宽，远则占像素少 —— 这是契约的成像事实。  
2. **地面域（FS 轮廓）：** 同一光锥落到 z=0，空路边界应是 **光锥∩地面∩远顶**；在 BEV 上通常呈近宽、向远收窄的斑（钥匙孔/梯形类），**不是**「从车原点拉两条等 θ 射线甩到 120 m」的大 V。  
3. **BEV 旁观相机：** 只把已经算好的地面轮廓投到屏上；**不参与**定义光学契约。

### 与实现的关系（诚实口径）

| | **真光学契约（已落地前空场）** | **旧代理（已替换）** |
|--|------------------------------|----------------------|
| 边 | 相机光心发出的 FOV 边缘（图像矩形）∩ 地面 | 车体原点方位 `\|atan2(y,x)\| ≤ fov/2` |
| 深 | `x ≤ d_empty`（SOR / VR） | `r = d_empty / cosθ` |
| 近大远小 | 图像投影事实；地面为空场 = 光锥可见斑 | 代理不编码像素；扇区易读成大 V |
| 参数 | `fs_envelope_cal` mount 默认 = `camera_contract` front | 仅 fov 角 |

侧/后瓣仍分域：侧吃标定横距（现冻 7）；后吃后槽 FOV + SOR 35 m；**7 不进前光锥**。

### 实现要点（`fuse_driving_fs.hpp`）

```text
FrontEmptyR(θ) = max { t | P=t·(cosθ,sinθ) ∈ 前视图像矩形 ∧ P.x ≤ d_empty }
Empty 层：FrontEmpty（光锥）| SideEmpty(7) | RearEmpty(后FOV∧35)
→ OccupyByLane → 兔耳
```

mount 默认 front：`x=0.55, z=1.35, pitch=-5°, fov=100°, 2048×1536`（≈3MP；与 ADC `camera_contract` 一致）。
环视 fl/fr/rl/rr：`1280×800`（≈1MP）；侧包络 **7 m**（fl/fr 主贡献；rl/rr 后角）。
中置后视 `rear`：`1920×1080`（≈2MP），yaw=180°，fov=120°，后包络 **35 m**；进**后视感知节点**（≠ surround）。

---

## 1. 唯一源（配置 → 运行）

| 真源 | 产物 | 谁读 |
|------|------|------|
| **gf-config** `frame_ingest` 各槽 `mount.{x,y,z,pitch,yaw,roll,fov}` | compose → `camera_contract.json` + `kMount*` / 每槽 mount | Host pygame、板端 ingest、光学楔 |
| 产品默认（未改配置时） | ADC/AFC **front.fov = 100°**（挡风玻璃） | 前视楔默认 |
| 包络距离 cal（SOR 分解冻结；目标进 compose 生成） | [`fs_envelope_cal.hpp`](../../../../projects/adc/interfaces/fs_envelope/fs_envelope_cal.hpp) | surround Near、driving fuse；**禁止**业务里再写一套 7/35/15/120 |

### 1.1 前 / 侧 / 后：谁拥有什么（禁止混谈）

| 瓣 | 数字（冻结名） | 拥有域 | 不是什么 |
|----|----------------|--------|----------|
| **前** | `kFsFrontFovDeg` / `kFsFrontFarCapM` / `kFsNearFrontCapM` | 前视 FOV + 光学远顶；减障出兔耳；Near 前 cap 仅重叠带 | 环视侧宽当空场墙；空 Near 前 cap ≠ 砍远顶 |
| **侧** | `kFsSideCapM`（7） | **仅侧瓣**环视近场横距 | 前/后空场侧墙 |
| **后** | `kFsRearFovDeg` / `kFsRearCapM`（35） | 后 FOV + 光学远顶；合拢=后顶 | 与侧 7 取 min；整后半球 |

**禁止：**

- 业务里再发明第二套「see_fov=50 内锥」当*可视*角（历史规划保守锥 ≠ 安装 FOV）。
- BEV / Foxglove 另写死一套与合同无关的前向张角。
- 旁观 Cam2 FOV（~78°）冒充产品前视。

**延续性：** 用户在 gf-config 改 `front.mount.fov` → compose → pygame Cam1 与 BEV 前楔同步变；规划光学楔读**同一 fov**（或 compose 注入的常量），不手改三处。

---

## 2. 方位包络：距离 + FOV（冻结表）

坐标系：车体 **+x 前、+y 左**。

### 2.1 前视（FCM / 挡风玻璃，ADC = AFC）

| 量 | 值 | 含义 |
|----|-----|------|
| **FOV** | **合同 `front.mount.fov`**（默认 **100°**） | pygame 画面左右缘 = ±FOV/2 射线 |
| **远距极限** | **120 m**（`d_cal_cap`） | 空路敢开/融合前向可到此；有障取近 |
| **Near 前向产品 cap** | **~15 m** | 仅 surround 近场重叠；**空 cap 不钳 `D_see`** |
| 谁拥有远目标 | FCM Out | surround **不**合成前向远目标 |

**光学楔：**  
- **前空场（已落地）：** §0.2 光锥∩地面（光心=`front.mount`）。  
- **`D_fov` / 弯道收尺：** 现阶段仍可用车体方位 `|atan2(y,x)| ≤ FOV/2` 与 Cam1 左右缘粗对齐；与 FS 前瓣光锥**同 fov 源**，公式可分步对齐。  
不再用「内 50°」。

### 2.2 后向（周视）

| 量 | 值 | 含义 |
|----|-----|------|
| **可见极限距离** | **35 m**（锁死） | 与 env#2 `bev_afc` / AFC paint 米窗后沿互验 |
| **FOV** | 后向槽 `mount.fov`；无独立后摄配置时用标定默认 **120°** | 后向等角楔，非整后半球 |
| 楔心 | −x（车尾方向） | 扇区仅在楔内给后向 cap |

### 2.3 侧向（环视）

| 量 | 值 | 含义 |
|----|-----|------|
| **侧向净空** | **~7 m（2×3.5 m 车道）** | 由环视安装俯仰/高度 + 地面交线得到的**近场横距**；配置外参变则应重算/重标定，现阶段冻结为包络 |
| 纵向带 | x∈(0, ~10]（近场） | 不替代前视 120 m |
| FOV | 各侧槽 `mount.fov`（合同默认 90°） | 用于投影/扇区归属；**包络横距**用上表 7，不拿 FOV 在 120 m 处甩腰 |

侧向「能看到约 7 m」= **安装几何 → 地面可见半径的横距结果**，与前视 100°×120 m 不是同一公式；唯一性在于：**外参来自 gf-config，包络表由此标定冻结**。

### 2.4 旁观（仅互验，非产品）

| | env#2 `bev_afc` | paint ADC `bev.mount`（env#3 旁观对齐） |
|--|------------|---------------------|
| 后向站位 | **−35 m** | **CamBack = 35 m**，米窗 **x∈[−35,+120]** |
| 前向 | 俯仰/高度可调观感 | 前窗仍到 +120 |
| 与产品 FOV | **无关** | **无关** |

---

## 3. 规划融合（行泊都在 FS 里）

### 3.1 数据

```text
FreespaceNear（36 扇区 + 轴）  ← surround，按 §2 包络填空 / 咬障
FCM Out / 本车道 / DYN         ← 前视远距与 occupy
fuse（driving_plus）           ← 前处理
  → 空 Near 前向 cap 不钳 D_see
  → 有真实前向近障才钳
  → D_see = slew(min(D_vr, D_occ, D_fov, D_wx, …))
  → D_fov 用合同 front.fov 方位楔（唯一）
Trajectory.D_see_m             ← 前向驾驶尺标量（完整网格不上 traj）
```

泊车：直接吃 Near + World；**不做** 120 m 前视融合。

### 3.2 「规划融合后的 FS」（BEV 验的唯一形状）

判断序：`FrontEmpty`(光锥∩地面∩远顶) / `SideEmpty`(7) / `RearEmpty`(后FOV∧35) → `OccupyByLane` → 兔耳。

| 扇区落在 | 空路 | 有障 |
|----------|------|------|
| **前视光锥**（mount+fov，默认 100°） | `FrontEmptyR`：图像矩形反投地面 ∧ `x≤d_empty` | 车道带 AABB 射线 → 兔耳 |
| **后 FOV** | `RearEmpty`：`d_rear/\|cosθ\|`（无 7） | 咬近 |
| **侧** | `SideEmpty`：仅 7 | 咬近 |

前光学 = 摄像头契约；大 V 旧代理（车体 `d/cosθ`）已替换。7 不进前/后空场。

---

## 4. BEV 画法（ADC）

### 4.1 米窗与相机

- 米窗：**x∈[−35,+120]**（后 35 与 Chase 互验；前 120）
- 虚拟相机：CamBack≈45（在后顶 −35 之后），自车略偏画面中上，后顶合拢可读
- 灰线：仍到各线 **`VR_End`**（标线尺，不与 FS 混）

### 4.2 主画：规划成品轮廓（ingest 不融）

**行车（DrivingActive，含 SpotSearch）**

1. Ingest `Freespace` + `Trajectory` + 感知 `Out`（灰线/DYN）
2. 只投影 `Freespace.d_occ_m[]` 闭合扇区环；**不**订 raw Near 当主轮廓
3. **不画** `Dxx` / `LC` / 青洗 / FOV 虚线（ADC 无 `D_see_m` 旁路）

**泊车（ParkingActive）**

1. Ingest `FreespaceNear` + `ParkingTrajectory` + `SurroundWorld`（槽）
2. 主轮廓 = Near；路径 = ParkingTrajectory

### 4.3 前/后瓣外形从哪来

- **前空场：** 光学契约 `光锥∩地面∩x≤d_empty`（`FrontEmptyR`）；**减障**按射线命中 → 兔耳。
- **后空场：** `后 FOV ∧ x=−35`；**不**与侧 7 取 min；合拢=后顶可见。
- **侧：** 仅侧瓣吃 7。
- BEV 只投影规划 `d_occ_m`。
- 前扇若仍「车体方位大 V」→ 检查是否误用旧 `d/cosθ` 代理或 mount 未进公式。

### 4.4 路径 / 车框

- 行车路径：裁在 `Freespace.d_front_m` 内
- 车框：FCM DYN + SurroundWorld；后 35 m 内应看得见（互验）

### 4.5 与 pygame 对齐验收

| 操作 | 期望 |
|------|------|
| Cam1 看左右缘 | = 合同 front.fov |
| 空直道 | 前光学远顶跟 `d_empty`；侧腰 ≈ 7；后顶 35（无侧墙掐） |
| 有侧前车 | 射线减障 → 兔耳；路径跟正前 `d_front` |
| Cam2 / BEV 身后 | 后顶 35 m 可读合拢势 |

---

## 5. 环视 → 5 m 的定位（延续）

```text
gf-config 侧/环视外参（高、俯仰、fov）
  → 光线与地面交线 → 近场横距标定
  → 冻结为侧包络（现阶段 7 m ≈ 2 车道）
```

- **不是**「前视 100° 在某距离上的宽度」。
- 外参大改时：重标定侧包络，改配置/表，**不**在 paint 里拍脑袋改宽。

---

## 6. 落地顺序（实现地图）

| 步 | 内容 | 触点 |
|----|------|------|
| A | 合同 FOV 唯一：规划 `see_fov` / BEV / Near 前楔 = `front.mount.fov`（默认 100；后续 compose 注入） | `gf_plan_cal`、`freespace_near`、`bev_compose`、codegen |
| B | 后向锁 35 m + 后 FOV 楔（配置或 cal 120°） | Near、Host `_REAR_M`、米窗 |
| C | 侧 7 保持；文档写明来自安装标定 | Near、`_surround_truth` |
| D | BEV 只画 §3.2 融合轮廓；去掉 ADC 双套青洗 | `bev_compose.cpp` |
| E | 文档与 `multi_cam_contract` 互链；删除「内 50°」可视说法 | 本文件 + 合同 |

**假完成禁止：** 名上读了合同、扇区仍按超宽角拉到 `D_see`。

---

## 7. 非目标

- ChaseCam / BEV 旁观外参 ≠ 产品槽
- 完整 FS 网格上 Trajectory
- FailSafe `Perception_FS_Out` 当 freespace
- 观测端另算一套最终 FS（BEV 只投影规划已发的 `Freespace` / 泊车 `Near`）

---

## 8. 验收口诀

> 角来自 gf-config；前 100°（合同）深可 120；后 35 m；侧约 1.5 车道。  
> BEV 只看融合 FS 楔；与 Cam1 左右缘同一扇门；旁观 35 只互验。
