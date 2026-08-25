# giraffe_client (上位机 · 非 Giraffe 模块)

CARLA Client B：读 UE 真值 + 多路相机，收板端 `vehicle_cmd` 拧车，TCP ↔ **`gf_carla_io`**。

```bash
cd carla_scenarios
# carla.env: GF_CAMERA_CONTRACT=afc  GF_COSIM_HOST=...
python3 -m giraffe_client
```

| 变量 | 含义 |
|------|------|
| `GF_CAMERA_CONTRACT` | 短名 `afc` 或路径 `config/afc/camera_contract.json` |
| `CARLA_HOST` / `CARLA_PORT` | UE |
| `GF_COSIM_HOST` / `GF_COSIM_PORT` | 板端 `gf_carla_io` |
| `GF_COSIM_CAMERAS` | 可选，逗号分隔只传部分 id（如 `front`） |

`run_cases.py`（scenario_client）可自动拉起本进程。
