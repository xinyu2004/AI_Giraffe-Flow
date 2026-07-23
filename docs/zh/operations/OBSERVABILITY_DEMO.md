# 可观测演示（P2 O/F + Live · 约 15 分钟）

> 配套：`GMT measure record|tag|export` · `GMT bridge foxglove`  
> 主链 SIL：`projects/oem_a/afc_with_uss`（**iceoryx**）  
> **说明：** `GMT bridge foxglove --ws` 是自研 Foxglove WebSocket **子集**，**不是** ROS 包 `foxglove_bridge`。  
> **主路径：** gf-config → `compile_sil` → `run_sil`（四脚本政策；验证 smoke 在 `scripts/verify/`）。

## 0. 前置（1 min）

```bash
source .venv/bin/activate
# gf-config A 页：profile=vehicle-debug，勾 live_tap，填白名单（如 EgoMotion / Trajectory）
# 若尚未编过 SIL：
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
```

## 1. Live：实时看 wiring 语义字段（推荐）

`run_sil` 读 `generated/observability.json`：live 有效则起 `gf_iox_obs_tap | GMT --ws`。

```bash
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# 已编过：
# GF_SKIP_COMPILE=1 bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

Foxglove Studio → **Open connection** → Foxglove WebSocket → `ws://127.0.0.1:8765`  
连接后加 **Raw Messages** / **Plot**，勾选 `/gf/EgoMotion`、`/gf/Trajectory`。

**另一台电脑：** 默认 `GF_WS_HOST=0.0.0.0`，Studio 填 `ws://<SIL 主机 LAN IP>:8765`。

**白名单：** A 页 `live_tap.services` → compose → `observability.json`。`production-release` 不编 tap。  
**tap 加入时机：** Verify / `compile_sil` 时 compose 自动把 `tools/iox_obs_tap` 写入 `GF_APPS`（勿手写进 apps）。

**画布：** B 页拖绿色/橙色圆点改边（Out 拉线用 Ctrl+拖）。

## 2. 事后录 session → MCAP（验证脚本）

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh
```

产物默认在 `build/observability/`：

| 文件 | 说明 |
|------|------|
| `session.jsonl` | 从 multiproc 日志解析的事件 |
| `session_tagged.jsonl` | Tag 窗 |
| `session.mcap` | 多 topic MCAP |

```bash
GMT bridge foxglove --mcap build/observability/session.mcap
```

## 3. WebSocket 回放（非 live）

```bash
GMT bridge foxglove --ws --jsonl build/observability/session_tagged.jsonl --port 8765
```

## 4. Tag 窗示例

```bash
GMT measure tag --in build/observability/session.jsonl \
  --out build/observability/session_tagged.jsonl --label demo
```
