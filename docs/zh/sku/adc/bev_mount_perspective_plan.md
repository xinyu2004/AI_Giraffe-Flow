# BEV mount — 先垂直俯视验收钥匙孔，再斜视变换（方案）

> **LC P3 走廊后置。**  
> **不加** `GF_BEV_PROJECTION` 或第二套投影模式；主链与 paint 逻辑保持原样。  
> **只改** `iox_obs_foxglove/config/adc/bev.mount.json`：先写成接近垂直俯视 → 验钥匙孔 + **顺带证明 mount 生效** → 再改回/调成斜视旁观。  
> 配套 [fs_fov_bev_scheme.md](./fs_fov_bev_scheme.md)、[optical_mount_fs_plan.md](./optical_mount_fs_plan.md)、[backlog.md](./backlog.md)。

---

## 1. 一句话

```text
一切保持正常（仍走 BevCam::project + bev.mount）
验收阶段：把 adc/bev.mount 调成高空近垂直俯视 → 看钥匙孔 FS
确认形状 OK 且改 json 画面会变（mount 真吃到了）
再改 mount 做斜视透视变换
```

---

## 2. 边界

| 项 | 做法 |
|----|------|
| 新环境变量 / ortho 代码路径 | **不要** |
| `bev_compose` 投影公式 | **不改**（除非发现 bug） |
| 规划 `Freespace` / 7·35 | **不改**迁就画面 |
| `config/adc/bev.mount.json` | **改**（验收用垂直姿 → 通过后改斜视） |
| CARLA spectator | 可选同步；不以 carla 为准，以 paint json 为准 |
| LC 走廊 | 后置 |

---

## 3. paint 实际吃哪些 mount 字段

`bev_compose` 里相机朝向由 **位姿 + 地面注视点** 决定，不是单独用 `pitch` 当主旋钮：

```text
cpos = (x, y, z)
tgt  = (look_x, y, 0)     # 看向地面上的 look_x
fwd  = normalize(tgt - cpos)
```

另用 `oy_ego_frac` / `y_far_px` / `fov` 标定像素焦距。

因此「垂直俯视」≈：

| 意图 | 建议 |
|------|------|
| 相机在车上方 | `x≈0`（或很小）、`y=0`、`z` 很大（如 80–120） |
| 几乎竖直往下看 | `look_x≈0`（注视自车脚下地面）→ fwd 接近 −Z |
| 盖住米窗 | `z` 够高 + `fov` 够大（如 70–90），使 x∈[−35,+120]、\|y\|≳20 都进画 |

`pitch` 若 json 有写入但 **当前 paint 朝向不读 pitch**，验收以 `x/z/look_x` 为准；勿指望只改 pitch 变俯视。

---

## 4. 阶段一：垂直俯视 mount（验收钥匙孔）

### 4.1 当前验收 mount（已写入）

文件：`tools/gmt_board/iox_obs_foxglove/config/adc/bev.mount.json`（近 nadir）。  
斜视恢复值写在该文件 `note` 字段。与 CARLA 无关。

### 4.2 钥匙孔应见（米制直觉，近俯视下接近「地图」）

| 瓣 | 应见 | 禁止 |
|----|------|------|
| 前 | 近宽远收（光锥∩地） | 原点等角大 V 铺到 120 |
| 侧 | ≈±7 m | 当前 FOV 侧墙 |
| 后 | 合拢 ≈−35 m | 后半球乱铺 |
| 前车 | 前瓣砍短；灰线可更远 | VR 冒充青区 |

叠画：规划 `d_occ` 环为主；可对 `[fs][diag]` 扇区点。

### 4.3 过门清单

| ID | 检查 |
|----|------|
| O1 | 后沿 ~−35、侧 ~±7 |
| O2 | 前瓣收窄 ≠ 大 V |
| O3 | 前车砍短 |
| O4 | 弯道不铺满 120 |
| O5 | 与 diag 同扇区点大致同米 |
| **M** | **证明 mount 生效**（下节） |

---

## 5. 阶段一附带：证明 `bev.mount` 生效

垂直姿本身就在走同一条 `InitBevMountFromFile` → `BevMount()` → `make_bev_cam` 路径。

任选 **一次** A/B（只改 json，重载 paint）：

| 试验 | 操作 | 期望 |
|------|------|------|
| M-a | `z`: 100 → 60 | 地面「放大」、边更易出画 |
| M-b | `look_x`: 0 → 40 | 注视前移，自车不在画面中心/构图明显变 |
| M-c | `x`: 0 → −20 | 相机后移，前后留白变化 |

- **画面随 json 变** → mount 链路 OK，可进入阶段二。  
- **怎么改都不变** → 先修加载路径（`GF_MOUNTS_JSON` / `GF_BEV_SKU` / 读错 afc 文件），**禁止**先做斜视调参。

改完 A/B 后把验收用垂直姿（或约定基线）恢复，再跑 O1–O5。

---

## 6. 阶段二：改 mount 做斜视变换

仅当 O1–O5 + **M** 通过：

1. 把 `adc/bev.mount.json` 调成产品旁观斜视（现网量级可作起点：`x≈−45, z≈48, look_x≈40, oy_ego_frac≈0.62`…）。  
2. 目标：−35 仍看得见、自车约在屏 0.55–0.65 高、前 120 不顶死。  
3. 形状争议以 **阶段一垂直姿** 为准；透视只验观感。  
4. 定稿后可选对齐 carla env#3。

仍 **不改** 规划 FS 公式。

---

## 7. 总顺序

```text
改 adc/bev.mount → 近垂直俯视
  → 钥匙孔 O1–O5 + 试验 M（mount 生效）
  → 再改同一 json → 斜视旁观
  → （可选）LC P3 等后置项
```

无新开关、无第二套投影。

---

## 8. 明确不做

- `GF_BEV_PROJECTION` / 专用 ortho 代码分叉  
- 垂直验收不过就拧斜视「掩盖」  
- BEV 重算 FS；改 7/35 迁就画面  
- LC 走廊  

---

## 9. 验收口诀

> 不换代码换 mount；先抬头顶再斜看。  
> 钥匙孔要对；改 z/look 画面要动。  
> 俯视过关，才许斜视变换。
