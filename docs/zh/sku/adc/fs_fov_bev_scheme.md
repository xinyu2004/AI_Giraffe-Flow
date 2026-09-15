# ADC：FOV / 距离包络 / 融合 FS / BEV 画法（整套方案）

> 配套 [multi_cam_contract.md](./multi_cam_contract.md)、[freespace_and_dsee_plan.md](./freespace_and_dsee_plan.md)、两把尺子。  
> **目标：** 前后距离与 FOV **唯一、可延续**；来自 **gf-config 用户配置**；pygame 与 BEV **同一扇门**；行泊都在 FS 里规划，BEV **只验规划融合后的 FS**。

---

## 0. 一句话

```text
gf-config 相机安装（外参 + fov）
  → camera_contract / generated hpp
  → 感知 Near 扇区包络 + 规划 fuse
  → surround：FreespaceNear（泊车 / 行车第三段）
  → driving_plus：Freespace（行车三段成品）→ BEV 行车只订这个
  → ADC 行车不以 D_see_m 为规划尺（详见 freespace_wiring_plan.md）
```

旁观（ChaseCam / BEV 虚拟相机）**只用于互验看得清**，**不进**产品 FOV，**不进** `D_see`。

---

## 1. 唯一源（配置 → 运行）

| 真源 | 产物 | 谁读 |
|------|------|------|
| **gf-config** `frame_ingest` 各槽 `mount.{x,y,z,pitch,yaw,roll,fov}` | compose → `camera_contract.json` + `kMount*` / 每槽 mount | Host pygame、板端 ingest、光学楔 |
| 产品默认（未改配置时） | ADC/AFC **front.fov = 100°**（挡风玻璃） | 前视楔默认 |
| 包络距离 cal（可进配置扩展；现阶段文档冻结） | 前 cap / 后 cap / 侧 cap | surround Near、BEV 米窗 |

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

**光学楔（唯一）：** 相对车头 +x 的方位角 `|atan2(y,x)| ≤ FOV/2`。  
弯道收尺、融合前向扇区、BEV 前瓣，都用**这一把**，不再用「内 50°」。

### 2.2 后向（周视）

| 量 | 值 | 含义 |
|----|-----|------|
| **可见极限距离** | **35 m**（锁死） | 与 ChaseCam=2 / BEV 米窗后沿互验 |
| **FOV** | 后向槽 `mount.fov`；无独立后摄配置时用标定默认 **120°** | 后向等角楔，非整后半球 |
| 楔心 | −x（车尾方向） | 扇区仅在楔内给后向 cap |

### 2.3 侧向（环视）

| 量 | 值 | 含义 |
|----|-----|------|
| **侧向净空** | **~5.25 m（1.5×3.5 m 车道）** | 由环视安装俯仰/高度 + 地面交线得到的**近场横距**；配置外参变则应重算/重标定，现阶段冻结为包络 |
| 纵向带 | x∈(0, ~10]（近场） | 不替代前视 120 m |
| FOV | 各侧槽 `mount.fov`（合同默认 100°） | 用于投影/扇区归属；**包络横距**用上表 5.25，不拿 100° 在 120 m 处甩腰 |

侧向「能看到约 5 m」= **安装几何 → 地面可见半径的横距结果**，与前视 100°×120 m 不是同一公式；唯一性在于：**外参来自 gf-config，包络表由此标定冻结**。

### 2.4 旁观（仅互验，非产品）

| | ChaseCam=2 | BEV 虚拟相机（ADC） |
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

对每个方位角扇区半径 `r(θ)`：

| 扇区落在 | 空路 `r` | 有障 |
|----------|----------|------|
| **前视 FOV 楔内**（±front.fov/2） | **`D_see`**（可到 120） | `min(Near, D_see)` |
| **后视 FOV 楔内** | **min(35, Near 后 cap)** | 咬近 |
| **侧向 / 楔外** | **侧包络 ~5.25**（或 Near 侧） | 咬近 |
| 前向楔外且非侧 | 不拉到 `D_see` | Near 近场 |

这就是 **唯一验收轮廓**：不是「FS 环 + 另画青洗」两套。

---

## 4. BEV 画法（ADC）

### 4.1 米窗与相机

- 米窗：**x∈[−35,+120]**（后 35 与 Chase 互验；前 120）
- 虚拟相机：CamBack≈35，自车略偏画面中上，保证身后 35 m 可读
- 灰线：仍到各线 **`VR_End`**（标线尺，不与 FS 混）

### 4.2 主画：融合 FS 轮廓

1. Ingest `FreespaceNear.d_occ_m[]` + `Trajectory.D_see_m`
2. 按 §3.2 生成 `r_fused[i]`（角宽用合同 FOV，**禁止** `cosθ>0.15` 这种超宽前拉）
3. 极坐标折线：`(r·cosθ, r·sinθ)` → 透视投影
4. 线色加粗、与 AFC 青洗区分；**有 Near 时不画** 本车道青洗走廊 / `D` 横杠（避免双套）
5. HUD 仍可显示 `Dxx` / `LC`（数字同源），但**几何验收只看 FS 轮廓**

### 4.3 「进大远小」从哪来

- **不要**手工把远端画窄。
- **要**等角楔（合同 FOV）+ BEV 透视：近处角宽占屏大、远端往灭点收。
- 前扇若仍「平顶盖路」→ 一定是角宽 > 合同 FOV 或误把侧向扇区拉到 `D_see`。

### 4.4 路径 / 车框

- 路径：仍只画在前向敢开内（≤ `D_see`），与融合前楔一致
- 车框：FCM DYN + SurroundWorld；后 35 m 内应看得见（互验）

### 4.5 与 pygame 对齐验收

| 操作 | 期望 |
|------|------|
| Cam1 看左右缘 | = 合同 front.fov |
| BEV 前楔左右射线 | = 同一 ±FOV/2 |
| 空直道 | 前瓣深 ≈ `D`（可 ~120），腰 ≈ 侧 5.25，后瓣深 ≈ 35 @ 后 FOV |
| 有近前车 | 前瓣短 ≈ 车距；`D` 同步短 |
| Cam2 / BEV 身后 | 约 35 m 感知可读；**不**要求后瓣角宽 = 前 100° |

---

## 5. 环视 → 5 m 的定位（延续）

```text
gf-config 侧/环视外参（高、俯仰、fov）
  → 光线与地面交线 → 近场横距标定
  → 冻结为侧包络（现阶段 5.25 m ≈ 1.5 车道）
```

- **不是**「前视 100° 在某距离上的宽度」。
- 外参大改时：重标定侧包络，改配置/表，**不**在 paint 里拍脑袋改宽。

---

## 6. 落地顺序（实现地图）

| 步 | 内容 | 触点 |
|----|------|------|
| A | 合同 FOV 唯一：规划 `see_fov` / BEV / Near 前楔 = `front.mount.fov`（默认 100；后续 compose 注入） | `gf_plan_cal`、`freespace_near`、`bev_compose`、codegen |
| B | 后向锁 35 m + 后 FOV 楔（配置或 cal 120°） | Near、Host `_REAR_M`、米窗 |
| C | 侧 5.25 保持；文档写明来自安装标定 | Near、`_surround_truth` |
| D | BEV 只画 §3.2 融合轮廓；去掉 ADC 双套青洗 | `bev_compose.cpp` |
| E | 文档与 `multi_cam_contract` 互链；删除「内 50°」可视说法 | 本文件 + 合同 |

**假完成禁止：** 名上读了合同、扇区仍按超宽角拉到 `D_see`。

---

## 7. 非目标

- ChaseCam / BEV 旁观外参 ≠ 产品槽
- 完整 FS 网格上 Trajectory
- FailSafe `Perception_FS_Out` 当 freespace
- 观测端另算一套最终 FS（只允许按 §3.2 **同源公式**用已 ingest 的 Near + `D_see_m` 上色）

---

## 8. 验收口诀

> 角来自 gf-config；前 100°（合同）深可 120；后 35 m；侧约 1.5 车道。  
> BEV 只看融合 FS 楔；与 Cam1 左右缘同一扇门；旁观 35 只互验。
