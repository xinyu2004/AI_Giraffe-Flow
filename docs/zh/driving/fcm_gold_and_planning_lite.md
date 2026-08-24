# FCM 金样变量 & Planning lite

> 日期：2026-08 · SIL 产品 demo 口径（驾驶链路归档，不绑某一 SKU 文档树）。  
> 链：`carla_scenarios` → `<project>/runtime_ipc/carla_truth.json`（运行时生成）→ **仅 FCM** → iceoryx `Perception_MESSAGE_Out_St` → **planning** + **Foxglove BEV**。

## 总览

| 块 | SIL 是否填 | 谁消费 |
|----|------------|--------|
| `Perception_DYN_OBJ_Out` | 是（多车/行人） | planning（CIPV）、BEV |
| `Perception_LH_Out` | 是（本车道左右线 + 质量） | planning（居中）、BEV |
| `Perception_LA_Out` | 是（邻线；host avail≠2 时 FCM 可置 0） | **仅 BEV** |
| APP / STATIC / FCF / HLB / FS / DSTSR / LRE / AF | **否**（空） | — |

ONNX/`MakeFromDetect` 当前不写 Out；内容由 truth 驱动。freeze 只刷三处 `m_time_stamp` / `m_frame_id`。

契约头示例：`projects/afc/interfaces/fcm_perception/Perception_Out_messages.h`  
FCM：`…/apps/perception/fcm/src/main.cpp`  
Planning：`…/apps/planning/driving/src/main.cpp`  
BEV：`tools/gmt/src/gf_gmt/bev_compose.py`

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
| `m_LH_First_VR_Start` / `End` | 可视范围；BEV 只画到 VR_End；planning 作轨迹 horizon |
| `m_LH_Line_First_C0..C3` | 三次多项式；居中 → steer / 画线（C3 现为 0） |
| `m_LH_Lanemark_Type` | 实/虚；**仅 BEV** |
| Track/Color/MarkerWidth 等 | 协议占位 |

质量来自 truth：`lane_avail` / `lane_conf` / `lane_vr_end_m`（`assess_lane_poly_quality`）。  
大横向偏移 → **降级短 VR**，不整帧灭线；`|atan(C1)|>40°` 等才 `avail=0`。

---

## 3. LA（邻车道）— 用途

| 字段 | 用途 |
|------|------|
| `m_adj_line_num` | 邻线数（host 非 DETECTED 时可 0） |
| `m_LA_Line_Side` / `C0..C3` / `VR_*` / Confidence / Availability / Lanemark_Type | **仅 BEV 画邻线** |

Planning **不读 LA**（无变道逻辑）。

---

## 4. Planning lite 做了什么

进程：`planning.driving`（iox runtime `gf-planning-driving`）。

### 输入 / 输出

| | 内容 |
|--|------|
| **In** | iceoryx `Perception_MESSAGE_Out_St`（DYN CIPV + **LH**）；`EgoMotion` |
| **Out** | iceoryx `Trajectory`（16 点，沿 LH 中心 blend）；`runtime_ipc/planning_ctrl.json`（throttle/brake/steer/target_speed/mode） |
| **不读** | `carla_truth.json`（file truth 旁路已删） |

### 行为（lite，非量产 LKA）

| 模式 | 条件 / 动作 |
|------|-------------|
| `cruise` | 无 lead；目标约 12 m/s；静止有油门地板便于起步 |
| `pullaway` | 近停 + 前车距离安全 → 拉起 |
| `acc` | CIPV 跟车；期望间距 `clamp(max(8, v×1.6), 8…40)` m |
| `aeb` | 过近或 TTC 过小 → 重刹 |
| 横向 | LH 左右线 → 中心 `e_y` + `c1` → steer（非完整 LKA）；无 LH 则跟 ego.steer |
| 轨迹 | `FillLaneKeepTrajectory`：沿车道中心指数 blend，horizon 受 VR/车速限制 |

**没有：** 变道、吃 LA、HLB、静态障碍、FS。

---

## 5. BEV / obs_tap 注意

- BEV **只画 Out**；缺 `Availability` 字段时勿当 NA（obs_tap 历史 allowlist 曾漏该字段）。
- allowlist 应含：`m_LH_Availability_State`、`m_LA_Availability_State`、`m_*_Lanemark_Type`（见 `gf_codegen/generate_cmd.py` `_OBS_TAP_FIELD_ALLOW`）。
- 量程：`D_work≈120 m`，画布 `D_bev=130 m`；车道锚（host C1→ψ）。

---

## 6. 运行时目录（勿入库）

| 项 | 说明 |
|----|------|
| `projects/**/runtime_ipc/` | SIL 文件 IPC scratch；compose/`carla_scenarios` 运行时 `mkdir`；根 `.gitignore` 整目录忽略 |
| `projects/**/build-sil/`（及 `build-*/`） | SIL 构建树；勿打包 |
| 总清单 | [projects/UPLOAD_CHECKLIST.md](../../../projects/UPLOAD_CHECKLIST.md) |

相关驾驶/SIL 角色： [../sku/afc/frame_ingest_roles.md](../sku/afc/frame_ingest_roles.md) · 质量 backlog：[../sku/afc/backlog_truth_quality.md](../sku/afc/backlog_truth_quality.md)
