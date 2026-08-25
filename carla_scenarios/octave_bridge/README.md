# octave_bridge（上位机 · 非 Giraffe 模块）

Host 规划调试环：`gf_carla_io` 孪生 + 规划 → `vehicle_cmd`；可选 **Foxglove WS** 推共用 `bev_compose` BEV。

```text
giraffe_client ──cosim──► octave_bridge ──vehicle_cmd──► giraffe
                               │
                               ├─ plan_tick (octave / ref)
                               └─ bev_feed → Foxglove WS :8765
                                      topic /gf/driving/bev/compressed
```

## 跑

```powershell
$env:GF_GMT_SRC = ".\gmt\src"   # 或绝对路径；目录内需有 gf_gmt/
python -m octave_bridge --port 7600
# Studio → Open connection → ws://127.0.0.1:8765
# Image 面板订阅 /gf/driving/bev/compressed
```

另开 `run_cases`（giraffe 会自动起）。**不要**同时占 8765 的 SIL `run_sil` Foxglove。

| 环境 / 参数 | 含义 |
|-------------|------|
| `GF_COSIM_PORT` / `--port` | cosim（默认 7600） |
| `GF_OCTAVE_BRIDGE_FOXGLOVE_PORT` / `--foxglove-port` | Studio WS（默认 8765；`0` 关闭） |
| `--no-foxglove` | 只规划控车 |
| `GF_OCTAVE_BRIDGE_ENGINE` | `ref` 或 `octave` |
| `GF_GMT_SRC` | `…/gmt/src`（含 `gf_gmt/`）；Foxglove/BEV 需要 |

## 目录

| 模块 | 职责 |
|------|------|
| `io_server` | 联仿听端口 |
| `semantic_map` / `runtime` | View↔POD；只规划 |
| `bev_feed` | 喂同一 `LiveBevComposer` |
| `foxglove_ws` | 最小 Foxglove 子集（复用 `gf_gmt.bridge_foxglove`） |

## 与板端

画笔同一套；传输不同（Host WS vs SIL obs_tap）。上板仍 `generate`+`planning.driving`，勿抄律。
