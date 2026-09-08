# Gateway 边界与 GfChannel（AFC）

## 边界规则

| 方向 | 通道 |
|------|------|
| 非 Giraffe ↔ Giraffe | **GfChannel**（通用 shm：图像或 blob POD） |
| Giraffe 内部模块间 | **iceoryx** 语义 |
| gateway 对外执行 | **egress TBD**（不锁死 CAN；SIL 示例：`gf.channel.vehicle_cmd`） |
| CARLA 联仿（两机） | **TCP cosim**（`cosim_protocol.h`） |

非 Giraffe 进程 **不上** iceoryx Provide/Require。

## 命名（已锁定）

| 名 | 位置 | 角色 |
|----|------|------|
| **`gf_carla_io`** | 板端 / SIL（Giraffe 侧独立程序） | 网络 ↔ GfChannel：真值/`fake_perc`/相机进，`vehicle_cmd` 出 |
| **`scenario_client`** | 上位机（`carla_scenarios`） | 布景 / 他车 IC / HUD；**不控 ego** |
| **`giraffe_client`** | 上位机（`carla_scenarios/giraffe_client`） | **唯一** UE ego 控车；真值+相机 ↔ `gf_carla_io` |

```text
scenario_client ──RPC──► UE
giraffe_client  ──RPC──► UE
       │ TCP cosim（GF_COSIM_HOST:PORT）
       ▼
gf_carla_io ──► GfChannel ──► gateway / FCM
gateway ──► vehicle_cmd ──► gf_carla_io ──► giraffe_client ──► UE
```

`run_sil`：`GF_FRAME_SOURCE=carla` → ingest exec **`gf_carla_io`**（命令不变）。  
`carla.env`：仅 HOST/PORT 等；**槽名用户无感**（compose/hpp）。

## SIL 槽

| 槽 | 写 | 读 |
|----|----|----|
| `gf.channel.front` | `gf_carla_io`（来自 giraffe_client 相机） | FCM / Foxglove |
| `gf.channel.vehicle_state` | `gf_carla_io` | gateway |
| `gf.channel.vehicle_cmd` | gateway | `gf_carla_io` → giraffe_client |
| `gf.channel.fake_perc` | `gf_carla_io` | FCM（假感知；**非**量产） |

主链相机 **常开**（不绑 Foxglove 订阅）；Foxglove 未订阅时仅不推 WS。  
多相机：cosim `slot_id` → `gf.channel.<id>`；上位机读  
`carla_scenarios/config/<product>/camera_contract.json`（`GF_CAMERA_CONTRACT`；compose/Verify 导出；**无** `GF_PROJECT_DIR`）。

## 产品裁剪

无 CARLA 联仿时可不部署 `gf_carla_io` / cosim 槽。ISP 进 FCM、总线进 gateway 时可零 GfChannel。

## 硬规则

- **默认仅 `giraffe_client` 控 ego**（ACC / 横向 / 天气等不得 seed hero）。
- **唯一例外：AEB 族**（`aeb_ego_seed`）可给 ego 一次 closing 初速；见 Giraffe `vehicle_cmd` 后 release const-vel。FCW / VRU-AEB 同属此例外。
- **无** `carla_cmd.json` / `carla_truth.json` / `planning_ctrl.json` / `front.yuv` 产品 IPC；HUD CTRL 用本机 UDP tip（`GF_CTRL_TIP_PORT`，默认 7610）。
- 运行时写盘：PER / OTA；Log 文件默认关；GMT 录制属上位机工具。

## 上位机规划旁路（开发）

`carla_scenarios/octave_bridge`：Host 扮演 `gf_carla_io` 联仿对端；规划 → `vehicle_cmd`；可选 Foxglove WS（默认 `:8765`，topic `/gf/driving/bev/compressed`，画笔=C `gf_host_bev_ws`，`GF_HOST_BEV_BIN`）。不替代板端 EM。

## 遗留债

- **入/出口 APP 边界**与**出口总线形态** — 未锁死（见下）。
- publish_policy：Ego/In/`vehicle_cmd` **period 10ms hold-last**（seq/ts 前进）；Out/Trajectory **on_change**。cmd 在新 Traj 边沿额外一拍（AEB），不是冻帧。首帧 Traj 前不发伪 thr/steer。映射表 / 取消同源双发仍是 OEM backlog。
- fake_perc 几何已由 `_lane_truth` + `_objects_truth` 填满 POD；非几何质量字段见 `backlog_truth_quality.md`。

### 入/出口 APP 边界 · 出口总线形态（为何 TBD）

当前 SIL 把「车态 ingest → Ego/Perception_In」和「Trajectory → 控车出口」塞在同一个进程  
`adapter.vehicle_can_gateway` 里；出口在联仿上是 GfChannel `vehicle_cmd`，**不是**量产 CAN/SOMEIP 帧。

未锁死的两件事：

1. **同一 SOA APP？** 量产可能拆成「入站网关 / 出站执行」两个部署单元，或继续一个 façade；OEM 总线拓扑与 EM 进程表决定，不在本仓库写死。
2. **出口总线形态？** 板端可能是 CAN FD / ETH SOMEIP / 私有 PDU；SIL 用 `vehicle_cmd` POD 只证明「规划→执行」语义，不规定线束与信号布局。映射表 + publish_policy 才是 OEM 差异面。
