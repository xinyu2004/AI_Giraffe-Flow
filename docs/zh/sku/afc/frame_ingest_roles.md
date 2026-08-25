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

## publish_policy（债）

period / on-change 表驱动尚未落地；当前 gateway 固定周期同源发 Ego+In。
