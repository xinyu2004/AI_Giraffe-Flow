# octave_bridge（上位机 · 非 Giraffe 模块）

Host 侧规划调试环：扮演 **`gf_carla_io` 的联仿对端**，Octave/参考律只做规划；BEV **共用** `tools/gmt` 的 `bev_compose`。

```text
giraffe_client ──TCP（现有 cosim 协议）──► octave_bridge
                                              ├─ semantic_map → PlanningView
                                              ├─ runtime.plan_tick（.m 或 ref）
                                              ├─ PlanningResult → vehicle_cmd
                                              └─ bev_feed → LiveBevComposer（同板端画笔）
```

## 跑

```bash
# 终端 1：不要起 SIL gf_carla_io（端口独占）
cd carla_scenarios
python3 -m octave_bridge --port 7600
# 可选：--bev-out /tmp/host_bev.png

# 终端 2：照常
# GF_COSIM_HOST=127.0.0.1 GF_COSIM_PORT=7600 python3 -m giraffe_client
# + scenario_client
```

| 环境变量 | 含义 |
|----------|------|
| `GF_COSIM_PORT` / `--port` | 与 `giraffe_client` 一致（默认 7600） |
| `GF_OCTAVE_BRIDGE_ENGINE` | `ref`（默认，Python 1:1 ops）或 `octave`（需 oct2py+Octave） |
| `GF_OCTAVE_BRIDGE_BEV` | 可选：每 tick 写 BEV PNG |
| `GF_GMT_SRC` | `tools/gmt/src` 路径（CARLA 机无整仓时必设，内含 `gf_gmt/`） |

### CARLA 机上的 GMT（共用 BEV，避免二次调）

要对齐板端 Foxglove BEV，**必须**用同一套 `bev_compose`（`gf_gmt`），不能另写画笔。

推荐（由稳到省事）：

1. **`pip install -e <repo>/tools/gmt`**（或把整仓 checkout 到本机）— 不漂移  
2. **拷贝 `tools/gmt/src`，设 `GF_GMT_SRC`** 指向含 `gf_gmt` 的目录，例如：  
   `set GF_GMT_SRC=D:\path\to\gmt\src`  
3. 仅控车、暂不看 BEV：`--no-bev`（缺 GMT 时也会自动降级并 WARN）

说明：当前 bridge 用同一画笔出 PNG（`--bev-out`）；Studio 实时 WS 仍走板端 `GMT bridge foxglove` 或后续再挂 Host 发布。画笔一致 ≠ 已经开了 Foxglove 窗口。

## 目录

| 模块 | 职责 |
|------|------|
| `io_server` | 联仿听端口（协议仍是 cosim） |
| `semantic_map` | POD ↔ `PlanningView` / `PlanningResult`；FCM 同构填 Out 形给 BEV |
| `runtime` / `plan_ref` | 只规划；算法真源仍在 `octave_planning/*.m` |
| `bev_feed` | 只喂 `LiveBevComposer`，不重写 BEV |

## 不调两次

- 规划律：只改 `octave_planning/`（或与之 1:1 的 ops）
- BEV：只改 `bev_compose`
- 本包多出来的仅是运输（io_server）与解释器（runtime）

## 与板端

板端仍是 `gf_carla_io` + FCM + `planning.driving`。本包是 **开发旁路**；上板用 generate/compile，不要在板端再抄一版律。
