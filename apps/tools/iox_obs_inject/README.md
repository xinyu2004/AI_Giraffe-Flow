# iceoryx session inject（G3）

独立进程 `gf_iox_obs_inject`：从 session JSONL `Send`（MVP：EgoMotion）。

## 铁律

**同一 service 永不双发布。** 回灌时不要同时跑 `vehicle_can_gateway` 的 EgoMotion 仿真。

## 拓扑：B1 / B2（谁在听）

| 模式 | 怎么开 | 跑什么 |
|------|--------|--------|
| **B1 全链边界** | 只设 `GF_INJECT_SESSION` | RouDi + uss/fcm/planning；**无** gateway |
| **B2 单模块** | 再设 `GF_INJECT_DUT` 或 `GF_INJECT_APPS` | RouDi + DUT + inject |

`gf_iox_obs_inject` **不区分** B1/B2；拓扑由 `run_sil` 决定。

## 灌法：continuous / playhead（等不等 GMT）

| `GF_INJECT_MODE` | 行为 |
|------------------|------|
| **`continuous`**（默认） | 按 session 时间自己灌完，**不等 GMT** |
| **`playhead`** | 监听 `GF_INJECT_PORT`（默认 **8767**），**等 GMT** seek/step/play |

事件 **index 与 GMT session 一致**（全部非 `tag_meta` 行）。非白名单 topic 可 seek，但不 `Send`。

### continuous

```bash
GF_INJECT_SESSION=build/observability/session.jsonl \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

### playhead + GMT

```bash
# SIL 机
GF_INJECT_SESSION=build/observability/session.jsonl \
  GF_INJECT_MODE=playhead \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# → inject 挂起，监听 :8767

# 主机 GMT（打开【同一】session）
GMT gui --project projects/oem_a/afc_with_uss \
  --session build/observability/session.jsonl
# →「回灌」页 → 连接 host:8767 → 勾选「跟 playhead 灌」→ scrub
```

GMT **不**调用 `run_sil`；只连 inject 控制口。

### 控制协议（TCP，一行一个 JSON）

```text
→ {"cmd":"hello"} | {"cmd":"status"} | {"cmd":"seek","index":N}
→ {"cmd":"step"} | {"cmd":"play","rate":1.0} | {"cmd":"pause"}
← {"op":"hello","proto":"gf_inject_ctrl",...}
← {"op":"published","index":N,"topic":"...","injected":true|false}
```

## B2 单模块示例

```bash
GF_INJECT_SESSION=build/observability/session.jsonl \
  GF_INJECT_DUT=sensing.uss \
  GF_INJECT_MODE=playhead \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

## 环境变量

| 变量 | 含义 |
|------|------|
| `GF_INJECT_SESSION` | session JSONL |
| `GF_INJECT_MODE` | `continuous` \| `playhead` |
| `GF_INJECT_PORT` | playhead 控制端口（默认 8767） |
| `GF_INJECT_HOST` | bind（默认 `0.0.0.0`） |
| `GF_INJECT_LIVE` | 默认 `1`：回灌时保留 live_tap，但**去掉可灌服务**（只订下游） |
| `GF_INJECT_SERVICES` | 短名列表；默认 `EgoMotion` |
| `GF_INJECT_DUT` / `GF_INJECT_APPS` | B2 拓扑 |

playhead + live：GMT 可同时连 **8767（控制）** 与 **8766（旁观下游）**；开「跟 playhead 灌」时 GUI 会关 Live 跟随。

连接态日志（SIL stderr）：
- inject：`LISTENING` → `GMT control CONNECTED from ip:port` → `DISCONNECTED`
- live bridge：`state=LISTENING|CONNECTED|DISCONNECTED`
