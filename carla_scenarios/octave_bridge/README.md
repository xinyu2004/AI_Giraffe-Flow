# octave_bridge（上位机 · 非 Giraffe 模块）

Host 规划调试环：`gf_carla_io` 孪生 + **Octave `.m`** → `vehicle_cmd`；Foxglove WS 推共用 `bev_compose` BEV。

```text
giraffe_client ──cosim──► octave_bridge ──vehicle_cmd──► giraffe
                               │
                               ├─ oct2py → octave_planning/afc/*.m
                               └─ bev_feed → Foxglove WS :8765
                                      topic /gf/driving/bev/compressed
```

规划运行真源是 `.m`（需本机 Octave CLI + `oct2py`，**不用开 GUI**）。CI/SIL 仍跑转译后的 C++。

## 跑

```powershell
$env:GF_GMT_SRC = ".\gmt\src"
python -m octave_bridge --port 7600
# Studio → ws://127.0.0.1:8765 → Image → /gf/driving/bev/compressed
```

`octave_planning/` 放到 `carla_scenarios` 旁边或里面，或设 `GF_OCTAVE_PLANNING`。  
另开 `run_cases`。不要和 SIL Foxglove 抢 `:8765`。

| 环境 / 参数 | 含义 |
|-------------|------|
| `GF_COSIM_PORT` / `--port` | cosim（默认 7600） |
| `GF_OCTAVE_BRIDGE_FOXGLOVE_PORT` / `--foxglove-port` | Studio WS（默认 8765；`0` 关闭） |
| `--no-foxglove` | 只规划控车 |
| `GF_OCTAVE_PLANNING` | `octave_planning` 根（含 `afc/m_lon_acc_aeb.m`） |
| `GF_GMT_SRC` | `…/gmt/src`（含 `gf_gmt/`） |

## 目录

| 模块 | 职责 |
|------|------|
| `io_server` | 联仿听端口 |
| `semantic_map` | POD ↔ PlanningView / PlanningResult |
| `runtime` | 长驻 oct2py，调 `.m` |
| `bev_feed` / `foxglove_ws` | 同一 `LiveBevComposer` |

## 规划基线（lite）

见 `docs/zh/driving/fcm_gold_and_planning_lite.md` §4。改算法只改 `octave_planning/afc/*.m`。
