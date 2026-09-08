# FCM 金样变量 & Planning lite

> 日期：2026-08 · SIL 闭环载荷归档（驾驶链路，不绑某一 SKU 文档树）。感知/规划用来压中间件，不是产品。  
> 链：`giraffe_client`（`_lane_truth` + `_objects_truth` → `GfFakePercPod` / cosim）→ **FCM** → iceoryx `Perception_MESSAGE_Out_St` → **planning** + **Foxglove BEV**。

## 总览

| 块 | SIL 是否填 | 谁消费 |
|----|------------|--------|
| `Perception_DYN_OBJ_Out` | 是（多车/行人） | planning（CIPV）、BEV |
| `Perception_LH_Out` | 是（本车道左右线 + 质量） | planning（居中）、BEV |
| `Perception_LA_Out` | 是（邻线；host avail≠2 时 FCM 可置 0） | **仅 BEV** |
| `Perception_STATIC_OBJ_Out` | 是（墙/护栏等静物；无则 0） | planning（phantom obj）、BEV |
| `Perception_DSTSR_Out` | 是（灯→`e_stopAhead`/`e_trafficSignals`；限速牌） | planning（红/黄灯 phantom stop）、BEV |
| APP / FCF / HLB / FS / LRE / AF | **否**（空） | — |

**尺子分层（A 现在，后面只加 B，不改 A 含义）：**

| 层 | 字段 | 现在 | 后挂（不改 A） |
|----|------|------|----------------|
| A 本车道前向 | `m_LH_First_VR_End` | 质量门 + cap；规划当 `x_end`（标线尺 `D_vr`）；BEV **灰线**画到这里 | 真相机丢线时同一字段变短 |
| A 本车道后向 | `m_LH_First_VR_Start` | 恒 0 | 环视填负值 |
| A' 邻道前向 | `m_LA_View_Range_End` | BEV 邻线 + 看见远点；规划不读 | 变道第二走廊 |
| A' 邻道后向 | `m_LA_View_Range_Start` | 恒 0 | 邻道后方空档 |
| B 路沿 | `Perception_LRE_Out` | 空 | 隔离带；禁止当左邻道 |
| C 参与者 | DYN / STATIC / DSTSR | 前向 `d≥0` 跟停；规划 `D_occ` | 后车 `Long_Distance<0` |
| 驾驶尺（内部） | **不是 FCM 字段** | `D_see = min(D_vr, D_occ, D_fov, D_wx, cap)+slew`；`D_fov`＝光学楔；路径/`v_cap`/BEV 青洗与 HUD `D` | 天气 `D_wx`；相机缩短仍走 A 的 `VR_End` |

**禁止把两把尺子合成一把：** 标线还在 120 ≠ 敢当畅通 120。前车走 `D_occ`，弯道走光学 `D_fov`（方位楔，不是航向），都不写回 `VR_End`。不要发明 FCM `D_see_m`。不要用 `|Δheading|` 冒充可视（已删 `D_bend`）。

前车/墙不写 `VR_End`。SIL 地图线还在就写长 VR。

ONNX/`MakeFromDetect` 当前不写 Out；内容由 truth 驱动。SIL（非 colorbar）Out 只在 fake_perc 更新时发，不重发冻帧。

契约头示例：`projects/afc/interfaces/fcm_perception/Perception_Out_messages.h`  
FCM：`…/apps/perception/fcm/src/main.cpp`  
Planning：`…/apps/planning/driving/src/main.cpp`  
BEV 金源：`tools/gmt_board/iox_obs_foxglove`（`bev_compose.cpp` → `gf_foxglove_paint`）。SIL=`gf_foxglove_ws`；Host octave=`gf_host_bev_ws`。

---

## 1. DYN（动态目标）— 用途

| 字段 | 用途 |
|------|------|
| `m_OBJ_VD_Count` / `m_OBJ_Ped_Count` | 车辆/行人计数；planning 用 VD 选 lead |
| `m_OBJ_VD_CIPV_ID` | CIPV；planning 跟车/AEB，BEV 描边 |
| `m_Obj_item[].m_OBJ_ID` | 目标 ID；BEV 调色板 |
| `m_OBJ_Object_Class` | 车/行人等；BEV 样式 |
| `m_OBJ_Long_Distance` | 纵向距；ACC/AEB + BEV x |
| `m_OBJ_Lat_Distance` | 横向距；BEV y |
| `m_OBJ_Relative_Long_Velocity` | 相对纵向速；TTC / HUD |
| `m_OBJ_Heading` | 航向；BEV 旋转 |
| `m_OBJ_Width` / `m_OBJ_Length` | 框尺寸；BEV |
| `m_OBJ_Lane_Assignment` 等 | 写占位；planning **未读** |

Truth 侧多目标：`carla_scenarios` `_objects_truth.py` → `dyn_n` / `obj{i}_*` / `cipv_id`。

---

## 2. LH（本车道 Host Line）— 用途

| 字段 | 用途 |
|------|------|
| `m_hostline_num` | 0=无效（质量门控失败）；≥2 正常左右线 |
| `m_LH_Estimated_Width` | 车道宽；planning / BEV |
| `m_LH_Side` | 1=左 / 2=右 |
| `m_LH_Confidence` | 低则丢弃（planning / BEV） |
| `m_LH_Availability_State` | 0=NA / 1=预测降级 / 2=检测；**硬清零仅极端几何** |
| `m_LH_First_VR_Start` / `End` | Start 现为 0（后向预留）；End = 标线有效尽头（质量门+cap，**不含前车**）；BEV **灰线**画到 End；规划 `x_end`＝`D_vr`。青帽/HUD `D` 用规划内部 `D_see`，不读此字段当驾驶尺 |
| `m_LH_Line_First_C0..C3` | 三次多项式；居中 → steer / 画线（C3 现为 0） |
| `m_LH_Lanemark_Type` | 实/虚；**仅 BEV** |
| Track/Color/MarkerWidth 等 | 协议占位 |

质量来自 truth：`lane_avail` / `lane_conf` / `lane_vr_end_m`（`assess_lane_poly_quality`）。  
大横向偏移 → **降级短 VR**；`|atan(C1)|>40°` → **近场降级**（仍出线），不整帧灭线；width 坍塌等才 `avail=0`。

---

## 3. LA（邻车道）— 用途

| 字段 | 用途 |
|------|------|
| `m_adj_line_num` | 邻线数（host 非 DETECTED 时可 0） |
| `m_LA_Line_Side` / `C0..C3` / `VR_*` / Confidence / Availability / Lanemark_Type | **仅 BEV 画邻线** |

发链上 ±1 外沿（side 1 / 4）以及 next-next（5 / 6，只给显示；四车道要 5 条边）。对向/隔离带不进同向前 Driving 链（后挂 LRE）。邻线 `VR_End` 与 host 各自写质量门+cap。规划 **不读 LA**。

Planning **不读 LA**（`allow_lc` 仅旗标；变道走廊后挂）。

---

## 3b. DSTSR / STATIC — 填空（契约字段，不删）

| 块 | 填什么 | 谁消费 |
|----|--------|--------|
| DSTSR | 红灯→`e_stopAhead`(196)；黄灯→`e_trafficSignals`(164)；限速牌→`e_std_*` | planning 把红/黄打成 `cls_reg_stop`（停车线，**不**走 occupy）；BEV 可画牌 |
| STATIC | 护栏/墙等静物 | planning 当静止 obj；墙不进 DYN AEB |

无灯/无静物时计数为 0，结构仍在。`GfFakePercPod` v2 尾带这两类；v1 520 B 仍可读。

---

## 4. Planning lite 做了什么

**纵向/规控（第四版）：** [planning_lon_v4.md](./planning_lon_v4.md) · [planning_v4_how.md](./planning_v4_how.md)。Host：`m_plan_tick`（路径+分段速度、视野滞回、≤8 目标）。C 等效果认可后再 generate。下表是 v3 现状备忘，不是目标。

进程：`planning.driving`（iox runtime `gf-planning-driving`）。

### 输入 / 输出

| | 内容 |
|--|------|
| **In** | iceoryx `Perception_MESSAGE_Out_St`（DYN CIPV + **LH**）；`EgoMotion` |
| **Out** | iceoryx `Trajectory`（路径 + thr/brk/steer/…）；SIL 控车出口 GfChannel `vehicle_cmd` |
| **假感知** | GfChannel `fake_perc` → FCM（**非**量产算法；无 `carla_truth.json`） |
| **不读** | `carla_truth.json`（file truth 旁路已删） |

### 行为（lite，非量产 LKA）

| 模式 | 条件 / 动作 |
|------|-------------|
| `aeb` | 分类 `th=3`：已在刹停包络内 → **brake=1**。车道坏也刹。无 latch、无 0.55 缓刹 |
| `cruise` 地板 | 分类 `th=0` 且车道可用、`|e_y|≤lat_ey_slow`；目标 = `cruise_v_mps` |
| hold（mode 仍 `cruise`） | 车道不可用或 `|e_y|>lat_ey_slow`；或跟停且间距不够 / 切车偏移。油门 0 |
| `pullaway` | 跟车 + **本车道** `|lat|≤lat_merge` + 近停 + 间距在 `d_stop` 之外 |
| `acc` 跟车 | `th=1` 且已在运动；目标间距 `≥ d_stop + acc_gap_over_stop`；超 `acc_v_max` 只刹不加油 |
| `acc` 横穿谨慎 | `th=2`：不加油，移动时轻刹 |
| 横向 | LH → `e_y`+`c1`→steer；`|e_y|` 过大则 `gf_lane_usable=0`，steer→0（限速在 LKA 内） |
| 轨迹 | `m_lat_traj`：车道不可用时 y=0；horizon 受 VR/车速 + cal |

**分类（`gf_lon_classify`，先分类再动作）：**

| th | 含义 |
|----|------|
| 0 none | 无 lead、`d>lon_max`、或 `|lat|>lat_aeb_m`（邻道远目标 / CIPV 跳走） |
| 1 follow | `|lat|<lat_acc_m` 且尚未进入刹停包络 |
| 2 cross | ACC 锥外、AEB 锥内、`d<lon_cross_d_m` |
| 3 aeb | 锥内且 `d_stop = v²/(2a)+v·t_react+d_min+margin`，或 TTC，或接触 `d≈0` |

接触（`d<0.5`）仍是 lead，不当空路。ACC 目标间距不得进入 AEB 包络。切车 `|lat|≈2.6` 在 ACC 锥内，偏移目标不 pullaway。  
**参数集：** `octave_planning/common/gf_plan_cal.m` ↔ `gf_octave_planning/plan_cal.hpp`。  
**没有：** 变道、吃 LA、HLB、静态障碍、FS、AEB latch、Host/板端后处理壳。

---

## 5. BEV / obs_tap 注意

- BEV **只画 Out**；缺 `Availability` 字段时勿当 NA（obs_tap 历史 allowlist 曾漏该字段）。
- allowlist 应含：`m_LH_Availability_State`、`m_LA_Availability_State`、`m_*_Lanemark_Type`（见 `gf_codegen/generate_cmd.py` `_OBS_TAP_FIELD_ALLOW`）。
- 量程：`D_work≈120 m`，画布 `D_bev=130 m`；车道锚（host C1→ψ）。
- HUD `D` 与青区 = 可见路面（铺到视线尽头，尽头实心青横杠）。不画 FOV 虚线。灰线仍到各线 `VR_End`。路径只画在青区里。斜三角只在本车道 DYN 开口。不要发明 FCM `D_see_m`。

前向验收（不拿环视/变道逼本刀）：

- 高速 + 本车道前车 ~17 m：灰线仍到地图 VR；HUD `D` ≈ 17，青线在 ~17 m 开口，斜到邻线 VR。
- 邻道车（`|lat|≈2`）：不开口，驾驶尺不被邻道车砍。
- 空直道：HUD `D` 跟 host VR，青洗拉满走廊，无斜三角。
- 空弯道：灰线可仍长；青区/路径停在可见路面尽头，尽头实心青横杠；无 FOV 虚线、无「有前车」斜三角。
- 四车道、ego 第 2 条：5 条边 / 4 个走廊（含 next-next）。
- 最左 + 隔离带：无左邻、无左三角。
- 本车道质量门短 VR、邻线仍在：灰线短。

---

## 6. 运行时目录（勿入库）

| 项 | 说明 |
|----|------|
| `projects/**/runtime_ipc/` | 仅 replay/file 写 yuv 时才有；GfChannel 联仿不再创建。根 `.gitignore` 整目录忽略 |
| `projects/**/build-sil/`（及 `build-*/`） | SIL 构建树；勿打包 |
| 总清单 | [projects/UPLOAD_CHECKLIST.md](../../../projects/UPLOAD_CHECKLIST.md) |

相关驾驶/SIL 角色： [../sku/afc/frame_ingest_roles.md](../sku/afc/frame_ingest_roles.md) · 质量 backlog：[../sku/afc/backlog_truth_quality.md](../sku/afc/backlog_truth_quality.md)
