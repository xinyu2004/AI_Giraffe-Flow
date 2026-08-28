# giraffe_client (上位机 · 非 Giraffe 模块)

CARLA Client B：读 UE 真值 + 多路相机，收板端 `vehicle_cmd` 拧车，TCP ↔ **`gf_carla_io`**。

```bash
cd carla_scenarios
# carla.env: GF_CAMERA_CONTRACT=afc  GF_COSIM_HOST=...
python3 -m giraffe_client
```

| 变量 | 含义 |
|------|------|
| `GF_GIRAFFE_CAM` | `0`（默认）= 不挂相机、不 NV12、不发图；`1` = 按合同开视频。SIL/HIL 复用见 [host_fps_sil_hil.md](../../docs/zh/driving/host_fps_sil_hil.md) |
| `GF_COSIM_CMD_WAIT_S` | 仅用于「首包 cmd 迟迟不来」的日志（默认 2 s）。**不阻塞**世界钟；cmd 用 overlay-latest，没有 wait。Host Octave 金源仍可 window=1，见 [host_fps_sil_hil.md](../../docs/zh/driving/host_fps_sil_hil.md) |
| `GF_CAMERA_CONTRACT` | 短名 `afc` 或路径 `config/afc/camera_contract.json`（仅 `GF_GIRAFFE_CAM=1`） |
| `CARLA_HOST` / `CARLA_PORT` | UE |
| `GF_COSIM_HOST` / `GF_COSIM_PORT` | 板端 `gf_carla_io` 或本机 octave_bridge |
| `GF_COSIM_CAMERAS` | 可选，逗号分隔只传部分 id（如 `front`）；相机关闭时无效 |

`run_cases.py`（scenario_client）可自动拉起本进程。
