# carla_bridge — CARLA RGB tip（afc_no_uss）

可选 tip：从 CARLA（或 dry-run）写 wave-B 帧协议，并执行 gateway 写入的变道 cmd。  
**不**进入 `gf_ara`；CARLA 不在产品评估范围。

## 依赖

- 真 CARLA：安装对应版本的 `carla` Python 包（随 CARLA 发行包 / egg）
- dry-run：仅 Python 3 标准库（无 UE 也可验帧协议）

```bash
# 示例（版本以你的 CARLA 为准）
pip install /path/to/CARLA/PythonAPI/carla/dist/carla-*-py3*.egg
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `CARLA_HOST` / `CARLA_PORT` | `127.0.0.1` / `2000` | UE 服务端（可远程） |
| `GF_CARLA_FRAME_PATH` | `/tmp/gf_front.rgb` | 写给 fcm 的 raw RGB |
| `GF_CARLA_CMD_PATH` | `/tmp/gf_carla_cmd.json` | 读 gateway 变道 cmd |
| `GF_CARLA_CAM_W` / `H` | `640` / `480` | |
| `GF_CARLA_BRIDGE_DRY_RUN` | `0` | `1` = 无 CARLA 写合成帧 |
| `GF_CARLA_BRIDGE_ON_FAIL` | `exit` | 连不上：`exit`（码 0）或 `idle` |

## 帧 / cmd 协议

与 [SIM_SPIKE.md](../../SIM_SPIKE.md) 一致：`*.rgb` + `*.json`；cmd：

```json
{"lane_change":"left","speed_mps":null,"seq":1,"timestamp_ns":0}
```

## 运行

```bash
# 无 UE：协议自检
GF_CARLA_BRIDGE_DRY_RUN=1 python3 carla_bridge.py

# 真 CARLA
CARLA_HOST=127.0.0.1 python3 carla_bridge.py

# 或经 SIL 包装
bash projects/oem_a/afc_no_uss/scripts/run_carla_sil.sh
```
