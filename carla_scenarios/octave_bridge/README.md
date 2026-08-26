# octave_bridge（上位机 · 非 Giraffe 模块）

Host 规划调试环：`gf_carla_io` 孪生 + **Octave `.m`** → `vehicle_cmd`；Foxglove WS 推共用 `bev_compose` BEV。

```text
giraffe_client ──cosim──► octave_bridge ──vehicle_cmd──► giraffe
                               │
                               ├─ oct2py → octave_planning/afc/*.m
                               │            ↑ 阈值：common/gf_plan_cal.m
                               └─ bev_feed → Foxglove WS :8765
                                      topic /gf/driving/bev/compressed
```

规划运行真源是 `.m`（需本机 Octave CLI + `oct2py`）。**无后处理壳**；阈值在 `gf_plan_cal`。  
**先改 `.m`，Host 认完再 `gf-octavecoder generate` 出 C。** 每拍一次 `m_plan_tick`（`traj_n × obj_n_max`），不占满时间片。

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
| `GF_OCTAVE_PLAN_LOG` | `1` = 每 0.5s 打 `.m` 的 mode/thr/brk/steer/lat |
| `GF_OCTAVE_KILL_STALE` | 默认 `1`：启动前清残留 `octave_bridge`/`octave-cli`（`--no-kill-stale` 关） |

改阈值：只改 `octave_planning/common/gf_plan_cal.m`。改完**重启** bridge。C++ `plan_cal.hpp` 等效果认可后再 generate。

纵向 v4：Host 入口 `m_plan_tick`（路径 + 分段速度 + 执行）。BEV 画计划：路径按 `points_v_mps` 着色，青色虚线 `D_see`，顶栏 `V`/`D`/`T`。日志：`v_plan` / `a_req` / `Dsee` / `T` / `Docc` / `lc`。标签 cruise/acc/aeb 只描述力度。合同：[docs/zh/driving/planning_lon_v4.md](../../docs/zh/driving/planning_lon_v4.md)。

`run_cases` 退出时会杀 `giraffe_client` 进程树；bridge **不**杀 giraffe（由 run_cases 管）。

## 目录

| 模块 | 职责 |
|------|------|
| `io_server` | 联仿听端口 |
| `semantic_map` | POD ↔ PlanningView / PlanningResult |
| `runtime` | 长驻 oct2py，调 `.m`（无壳） |
| `bev_feed` / `foxglove_ws` | 同一 `LiveBevComposer` |

## 规划基线（lite）

见 `docs/zh/driving/fcm_gold_and_planning_lite.md` §4。算法结构在 `afc/*.m`，阈值在 `gf_plan_cal`。
