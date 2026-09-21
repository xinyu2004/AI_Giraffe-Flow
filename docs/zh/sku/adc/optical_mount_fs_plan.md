# 观测相机 / BEV mount / Foxglove 金源 — 完整计划

> 收口 2026-09-15 讨论。配套 [fs_fov_bev_scheme.md](./fs_fov_bev_scheme.md)、[multi_cam_contract.md](./multi_cam_contract.md)。  
> **本稿只管：CARLA 旁观编号、文件命名、paint `bev.mount`、Foxglove raw 金源归属。**  
> 产品光学（front/side/rear → 7/35 冻结）仍见合同 / `fs_envelope_cal`（gf-config 确认时生成常量）。

---

## 1. 一句话

```text
carla.env 里旁观仍编号 1/2/3/4
  ↔ 磁盘文件名用语义名：windshield / bev(afc|adc) / overhead
paint（iox_obs_foxglove）只持有 afc、adc 的 bev.mount
Foxglove 金源 = 通信 raw（image、POD…）按 SKU 分，不是规划 .m
产品相机 mount ≠ 旁观 mount；BEV 不算最终 FS
```

---

## 2. CARLA：`carla.env` 编号 ↔ 文件名

**规则：** 环境/启动配置里继续写 **1 / 2 / 3 / 4**；落地文件与文档用 **名称**，禁止口头长期叫 ChaseCam1/2/3。

| `carla.env` 编号 | 文件名（建议） | 角色 |
|------------------|----------------|------|
| **1** | `windshield.mount` | 风挡前视旁观 / 与产品 front 可对齐验视 |
| **2** | `bev_afc.mount`（或 `bev.mount` 仅 AFC 场景） | **AFC BEV** 旁观；参数 = **原 AFC paint**（CamBack≈35，Height≈40，Look≈60） |
| **3** | `bev_adc.mount` | **ADC BEV** 旁观；参数 = 现 ADC 旁观（如 Back≈45，Height≈48，Look≈40） |
| **4** | `overhead.mount` | 俯视旁观 |

放置：

```text
carla_scenarios/…/  （或 CARLA 工程约定目录）
  windshield.mount
  bev_afc.mount
  bev_adc.mount
  overhead.mount
carla.env（或等价）:
  camera_1 = windshield
  camera_2 = bev_afc
  camera_3 = bev_adc
  camera_4 = overhead
```

说明：

- **编号只活在 CARLA/env**；代码与文档引用优先文件名。  
- 2=AFC BEV、3=ADC BEV（若你口头说错过「3 也是 afc」，以本表 SKU 分为准）。  
- 这些文件描述 **仿真旁观相机**；**不是** 产品 SOR 的 front/side/rear 光学合同。

---

## 3. Paint：`bev.mount` 只在 iox_obs_foxglove

Foxglove BEV 画布的观测投影 **与 CARLA 目录解耦**：

```text
tools/gmt_board/iox_obs_foxglove/config/
  afc/bev.mount.json     # 与 carla 编号 2 / bev_afc 数值对齐（默认同源拷贝）
  adc/bev.mount.json     # 与 carla 编号 3 / bev_adc 数值对齐
```

| 项 | 约定 |
|----|------|
| 谁读 | `gf_foxglove_paint`（`bev_compose`） |
| 怎么选 | `GF_BEV_SKU=afc\|adc`；或 `GF_MOUNTS_JSON` 覆盖路径 |
| 做什么 | 只做 **视角投影**；**不算** FS、不改 7/35 |
| 不放 | `carla_scenarios/config/*/mounts.json`（已属错误归属，应收掉） |

**Paint 工程位置：**

```text
tools/gmt_board/iox_obs_foxglove/
  CMake → gf_foxglove_paint / gf_foxglove_ws / gf_host_bev_ws
  无 afc、adc 源码子目录；SKU 用 env + config/<sku>/
```

与 CARLA 的关系：数值宜与编号 2/3 **对齐**（改 CARLA 旁观后同步 paint 配置，或 compose 从同一表生成两边），但 **文件必须在 paint 树下**，因为消费者是观测进程，不是 CARLA。

---

## 4. 「金源」在本计划中的含义

此处 **金源 ≠ 规划 Octave `.m`**。

| 金源（观测） | 含义 |
|--------------|------|
| **是什么** | 与 Foxglove / paint 通信的 **raw**：camera image、Ego/Out/FS/Traj 等 POD 或通道数据 |
| **按谁分** | **AFC / ADC SKU**（进程、topic、contract、是否 ingest `Freespace` 等） |
| **bev.mount 关系** | 只决定 raw **怎么画到 BEV 图**；不产生 raw |

规划金源（`.m` / oct_gen）仍在 `projects/afc`、`projects/adc`，另线管理；本计划不混谈。

---

## 5. 产品光学（提醒，非本文件主角）

| | 归属 |
|--|------|
| front / side / rear **产品** mount | gf-config → `camera_contract` |
| 能看多远/多宽（≈7、35、fov） | **gf-config 确认时算一次** → 写入 `fs_envelope_cal.hpp`（或 generated）**当常量** |
| 运行时 | fuse/Near **只读常量**，不每拍派生 |

`fs_mounts.hpp`（paint 侧）**只加载 bev 观测**；不要再在运行时从产品 mount 算包络。

---

## 6. 架构图

```text
                    ┌─ carla.env: 1/2/3/4
                    │     ↓
                    │  windshield.mount / bev_afc.mount / bev_adc.mount / overhead.mount
                    │     （CARLA 旁观，仿真里看）
                    │
gf-config 产品 mount ──compose──► fs_envelope_cal 常量 (7/35/fov)
                    │                    ↓
                    │              planning fuse → Freespace（地面真源）
                    │                    ↓ ingest
                    │
SKU raw 金源 ──────────► iox_obs_foxglove (paint)
  image / POD / …              ↑
                    config/afc|adc/bev.mount.json  （仅投影）
```

---

## 7. 落地阶段

### P0 — 归属纠正（立刻）

1. 删除或停用 `carla_scenarios/config/*/mounts.json` 作为 paint 配置源。  
2. 新建 `tools/gmt_board/iox_obs_foxglove/config/afc/bev.mount.json`、`…/adc/bev.mount.json`（内容分别来自原 AFC 35/40/60 与现 ADC 旁观）。  
3. `fs_mounts.hpp` / `bev_compose` 默认读上述路径（`GF_BEV_SKU`）。  
4. 文档与 `carla_scenarios/config/README.md` 写明：旁观编号在 env，文件名用语义名；paint 只用自己的 `bev.mount`。

### P1 — CARLA 四文件命名

1. 在 CARLA/场景侧落地 `windshield.mount`、`bev_afc.mount`、`bev_adc.mount`、`overhead.mount`。  
2. `carla.env`（或等价）映射 1→windshield，2→bev_afc，3→bev_adc，4→overhead。  
3. 与 paint 的 afc/adc `bev.mount` 做一次数值对表（允许注释写「对齐 env #2/#3」）。

### P2 — 金源（Foxglove raw）按 SKU 验收

1. 列 AFC vs ADC：哪些 topic/POD/image 进 paint。  
2. 验收：换 `GF_BEV_SKU` 只改投影与米窗策略，不改错 SKU 的 raw 集合。  
3. ADC 主轮廓仍只 ingest 规划 `Freespace`（BEV 不算 FS）。

**现状：** `GF_BEV_SKU` 已分窗；AFC/ADC raw 集合差异随进程/contract 走，完整 topic 清单可另开验收表（不阻塞 P0/P1）。

### P3 — 产品包络 compose 冻结（可并行）

1. gf-config Verify 后生成/更新 `fs_envelope_cal`（或 generated hpp）。  
2. 去掉运行时 Derive 侧后包络的路径（若仍残留）。

**现状：** `fs_envelope_cal.hpp` 已手写冻结 7/35/fov；运行时 `fs_mounts` 只载 paint bev。compose 自动 emit 可后置。

---

## 8. 验收口诀

> env 里是 1/2/3/4；磁盘是 windshield / bev_afc / bev_adc / overhead。  
> paint 只有 `iox_obs_foxglove/config/{afc,adc}/bev.mount`；和 CARLA 目录分开。  
> 金源 = Foxglove raw（图与 POD），按 SKU；bev.mount 只投影。  
> 7/35 是产品 mount 在 gf-config 确认时冻成的常量，不是旁观文件算的。

---

## 9. 禁止

- 把产品 front/side/rear 写进 paint 的 `bev.mount`。  
- 在 `carla_scenarios` 里塞 paint 专用配置当长期真源。  
- 口头 ChaseCam1/2/3 代替文件名。  
- BEV 用 mount 重算 FS。  
- 把规划 `.m` 和 Foxglove raw 都叫「金源」而不加限定。

---

## 10. 落地状态（2026-09-15）

| 项 | 状态 |
|----|------|
| paint `iox_obs_foxglove/config/{afc,adc}/bev.mount.json` | 已落地；`fs_mounts.hpp` 默认读此路径 |
| `carla_scenarios/config/*/mounts.json` 作 paint 源 | **已删除** |
| spectator `windshield/bev_afc/bev_adc/overhead.mount.json` | 已落地；`_view` V 循环 1/2/3/4 |
| `carla.env` 映射注释 | 已更新 |
| 包络常量 `fs_envelope_cal.hpp` | 已冻结（P3 stage-A；compose 自动生成可后置） |
| Foxglove raw 按 SKU（P2） | 现有 `GF_BEV_SKU` 分窗；topic 清单验收另跟 |

验收口诀见 §8。
