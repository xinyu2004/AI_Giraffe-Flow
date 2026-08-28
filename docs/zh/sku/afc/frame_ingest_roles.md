# frame_ingest / camera_slot / CARLA 联仿职责

## 主路径

```text
gf-config（Save → Verify）→ compile_sil → runtime/{bin,lib} → run_sil → GMT
```

- **帧源**：freeze SOP 默认 `isp`；SIL 用 **`GF_FRAME_SOURCE`**：`isp` / `carla` / `replay` / `colorbar` / `none`
- **ego_source**：`gateway` / `carla` / `inject` — 车态进 gateway（`carla`/`inject` → GfChannel `vehicle_state`）
- **`scenario_client`**（`carla_scenarios/`）：可异机；Python OK；不经 GfChannel
- **`giraffe_client`**：上位机 UE Client；TCP → **`gf_carla_io`**
- **相机合同**：`GF_CAMERA_CONTRACT` → `carla_scenarios/config/<product>/camera_contract.json`（compose/Verify 导出）

## GfChannel（通用 shm）

| 槽 | 用途 |
|----|------|
| `gf.channel.front` | 相机（联仿由 giraffe_client 供给） |
| `gf.channel.vehicle_state` | → gateway |
| `gf.channel.vehicle_cmd` | gateway → 联仿控车 |
| `gf.channel.fake_perc` | → FCM（假感知） |

## gf_frame_ingest（C++）

Create 相机槽后 **exec** 独立模块（**无 Python**）：

| 源 | 二进制 |
|----|--------|
| colorbar | `gf_frame_colorbar` |
| replay | `gf_frame_replay` |
| carla | **`gf_carla_io`** |
| isp | ingest 内持槽（板端） |

## 两机联仿

```text
上位机: scenario_client + giraffe_client ──RPC──► UE
板端:   GF_FRAME_SOURCE=carla → gf_carla_io ◄──TCP──► giraffe_client
```

详见 [gateway_boundary.md](./gateway_boundary.md)。

Host 关相机 / Python NV12 门控与规划时间片：[host_fps_sil_hil.md](../../driving/host_fps_sil_hil.md)。板上视频走 C++ ingest，不要复用 giraffe 的 Python 转码。

## publish_policy

`req.yaml`：Ego/In/`vehicle_cmd` period 10ms hold-last；Out on_change + `expect_fps`；`vehicle_state`/`fake_perc` on_change。运行时 FrameWatch 对身份 Error、对预算 Warn。OEM 映射表（源信号 → 哪些包）仍是 backlog，SIL 仍可同源各 due 各发。
