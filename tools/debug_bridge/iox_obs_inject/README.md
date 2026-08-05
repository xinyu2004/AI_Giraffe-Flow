# iceoryx session inject（G3）

独立进程 `gf_iox_obs_inject`：`Send` 可灌服务（MVP：EgoMotion）。

## 铁律

**同一 service 永不双发布。** 回灌时不要同时跑 `vehicle_can_gateway` 的 EgoMotion 仿真。

## 拓扑：B1 / B2（谁在听）

| 模式 | 怎么开 | 跑什么 |
|------|--------|--------|
| **B1 全链边界** | inject on（见下） | RouDi + uss/fcm/planning；**无** gateway |
| **B2 单模块** | 再设 `GF_INJECT_DUT` 或 `GF_INJECT_APPS` | RouDi + DUT + inject |

`gf_iox_obs_inject` **不区分** B1/B2；拓扑由 `run_sil` 决定。

## 灌法：continuous / playhead

| `GF_INJECT_MODE` | 谁持 session | 行为 |
|------------------|--------------|------|
| **`playhead`** | **GMT（上位机）** | 监听 `GF_INJECT_PORT`（默认 **8767**）；GMT 打开 JSONL 后推帧；**不必**板端本地 session |
| **`continuous`** | **板端文件** | 读 `GF_INJECT_SESSION`（仅可灌 topic）；`GF_INJECT_MAX_EVENTS` 硬上限；可选 `GF_INJECT_LOOP=1` |

### playhead + GMT（推荐）

完整 session 在 GMT；板端用 **A/B 双缓冲**只缓存当前窗口，避免整文件进内存。  
窗口大小：`GF_INJECT_WINDOW_MAX_EVENTS`（默认 256，范围 16–4096；总缓存 ≈ 2×该值）。

```bash
# SIL — 无本地 session 亦可
GF_INJECT_MODE=playhead \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# → inject LISTENING :8767（events=0 until GMT session cmd）

# 主机 GMT
GMT gui --project projects/oem_a/afc_with_uss \
  --session projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl
# →「回灌」→ 连接 host:8767 →「跟 playhead 灌」→ scrub
# 非 EgoMotion：GMT 本地记粉；EgoMotion：cmd inject
# 板端 need_window → GMT window_begin/push/window_end
```

GMT **不**调用 `run_sil`；只连 inject 控制口。

### continuous（板端文件 + 限额）

```bash
GF_INJECT_SESSION=projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# 可选：GF_INJECT_MAX_EVENTS=20000  GF_INJECT_LOOP=1
```

### 控制协议（TCP，一行一个 JSON）

```text
→ {"cmd":"hello"} | {"cmd":"status"} | {"cmd":"seek","index":N}
→ {"cmd":"step"} | {"cmd":"play","rate":1.0} | {"cmd":"pause"}
→ {"cmd":"reset"} | {"cmd":"session","events":N}
→ {"cmd":"window_begin","slot":"A"|"B","base":N}   # N = session/list scan start (playhead index)
→ {"cmd":"push","slot":"A"|"B","index":i,"t_ns":…,"topic":"…","data":{…}}
→ {"cmd":"window_end","slot":"A"|"B"}
→ {"cmd":"inject","index":i,"t_ns":…,"topic":"…","data":{…}}
← {"op":"hello","proto":"gf_inject_ctrl","caps":["stream_window"],"window_max_events":256,"window_buffers":2,"events":0,…}
← {"op":"published","index":N,"topic":"...","injected":true|false}
← {"op":"need_window","from":N,"count":64}
← {"op":"eof"} | {"op":"error","msg":"..."}
# SIL log: LOAD A scan_from=1152 ego=[1155..1330] ego_n=64
#   scan_from = window_begin.base (session index, NOT EgoMotion ordinal / "Nth received")
#   ego=[first..last] = session indices of EgoMotion frames stored in the slot
```

## B2 单模块示例

```bash
GF_INJECT_MODE=playhead \
  GF_INJECT_DUT=sensing.uss \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

## 环境变量

| 变量 | 含义 |
|------|------|
| `GF_INJECT_SESSION` | session JSONL；**continuous 必填**；playhead 可选（stream 忽略整文件载入） |
| `GF_INJECT_MODE` | `continuous` \| `playhead` |
| `GF_INJECT_PORT` | playhead 控制端口（默认 8767） |
| `GF_INJECT_HOST` | bind（默认 `0.0.0.0`） |
| `GF_INJECT_LIVE` | 默认 `1`：回灌时保留 live_tap，但**去掉可灌服务**（只订下游） |
| `GF_INJECT_SERVICES` | 短名列表；默认 `EgoMotion` |
| `GF_INJECT_DUT` / `GF_INJECT_APPS` | B2 拓扑 |
| `GF_INJECT_MAX_EVENTS` | continuous 硬上限（默认约 20000） |
| `GF_INJECT_WINDOW_MAX_EVENTS` | playhead：每个 A/B 窗口最多事件数（默认 256，夹紧 16–4096） |
| `GF_INJECT_LOOP` | continuous：`1` = 播完再从头直到信号 |

playhead + live：GMT 可同时连 **8767（控制）** 与 **8766（旁观下游）**；开「跟 playhead 灌」时 GUI 会关 Live 跟随。

连接态日志（SIL stderr）：
- inject：`[GMT Inject] LISTENING`（黄）→ `CONNECTED from ip:ephemeral (listen :8767)`（绿）→ `DISCONNECTED`（青）；颜色由 inject 自身决定（`/dev/tty` / `GF_STATUS_COLOR`）
- live / Foxglove：同色规则；`peer=` 为**客户端临时端口**，服务端监听口固定（8765/8766/8767）
- 出错：红色
