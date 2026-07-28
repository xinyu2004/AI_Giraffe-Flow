# Giraffe Measure Tool (GMT)

Host-only：**架构 CI**、**measure**、**Foxglove bridge**、**GMT GUI**（选项目 → Live 连接 / Tag / 回放）。

| 入口 | 说明 |
|------|------|
| **`gf-config`** | 唯一作者 GUI（B 画布 = 设计期真图；可导出 Graphviz） |
| `GMT architect lineage\|dag` | CI / 导出 |
| `GMT measure record\|tag\|export\|import-ndjson` | 日志录制、裁剪、MCAP/**VCD**、tap NDJSON 导入 |
| `GMT bridge foxglove` | Studio live / JSONL 回放（8765） |
| `GMT bridge live` | GMT GUI live NDJSON WebSocket（8766，stdin tap fan-out） |
| **`GMT gui`** | Live / Tag / 先后·动画 DAG / **变量轨** / **回灌 playhead** / 导出 |

```bash
pip install -e tools/gmt -e tools/codegen
pip install -e 'tools/gmt[gui]'

GMT gui
# 或（目录 / project.yaml 均可，与 gf-config 同一入口）：
GMT gui --project projects/oem_a/afc_with_uss
GMT gui --project projects/oem_a/afc_with_uss/project.yaml
```

**主路径：** 填 **Host**（本机 `127.0.0.1` / 远端局域网 IP）→ 顶栏两通道可**同时**连：

| 通道 | 端口 | 协议 | 用途 |
|------|------|------|------|
| **Live** | 8766 | WebSocket | live_tap 旁观；可选「录制」落盘（回灌时默认只订**下游**） |
| **回灌** | 8767 | TCP | playhead stream（GMT 下发窗口 / inject 帧） |

- 回灌「跟 playhead 灌」开启时：**自动关 Live「跟随最新」**（避免拽走 playhead）；Live 仍可旁观/录制  
- 回灌结果：顶栏 **绿=已灌 / 红=跳过**，原因在状态栏（无弹窗）  
- 「回灌」Tab：事件表（墙钟 / topic / 已发布|跳过），可点行跳 playhead；可选「循环（到结尾确认）」  
- 「变量轨」Tab：用户添加变量（每变量一行）；滚轮缩放时间窗；橙线 playhead  
- 墙钟：**方案 1** — session 一条 `session_meta` 锚点 + `(t_ns - t0_ns)`（非每行 wall_time）  
- 未加载 `project.yaml`：顶栏黄条提示；**回灌连接禁用**；Live 仍可旁观  

`GF_INJECT_LIVE=0` 可强制回灌时关掉 live_tap。

- **连接 Live**：WS 收流进内存；**默认不落盘**；「跟随最新」控制 playhead 是否贴尾  
- **录制**：顶栏「录制」按钮（录制中红底「录制中」）；默认 `session_live.jsonl`；若已存在非空文件则问 **新建**（`session_live_YYYYMMDD_HHMMSS.jsonl`）或 **覆盖**  
- 断开：停止录制（若有）；保留内存 session，可 scrub / Tag  
- 高级：**仅跟随 live 文件…** + 传输条 **跟随文件** — 不连网，只 tail 已有 JSONL  
- Tag：`M` 标记点；`[` / `]` 片段；`Ctrl+R` / `Ctrl+Shift+R` 连接/断开  
- GMT **不启动 SIL / 不调用 run_sil**  

前提：`gf-config` A 页 `live_tap` 已开 + `vehicle-debug` 已 `compile_sil`。  
`run_sil` 将 tap 同时 fan-out 到 `GMT bridge live`（8766，`GF_LIVE_PORT`）与 Foxglove（8765）。

### 回灌（playhead = GMT stream）

**playhead**：完整 session 在上位机 GMT；板端 inject 只持 A/B 小窗（`caps: stream_window`）。  
SIL 可不设 `GF_INJECT_SESSION`（stream-only）；GMT 打开 JSONL → 连接 8767 → scrub 时 `inject` 单帧 / 板端 `need_window` 时 GMT 填窗。

```bash
# SIL（stream / 无本地 session 文件）
GF_INJECT_MODE=playhead \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# 可选：仍可传路径作 hint，playhead 不把整文件载入板端内存
# GF_INJECT_SESSION=build/observability/session.jsonl GF_INJECT_MODE=playhead bash …
```

GMT：打开 session → **回灌**页 → 连接 `host:8767` → 勾选「跟 playhead 灌」→ scrub。  
「循环（到结尾确认）」：板端 `eof` 时弹窗是否从 0 再来一圈。

**continuous**：板端读文件（仅可灌 topic + `GF_INJECT_MAX_EVENTS` 上限）；可选 `GF_INJECT_LOOP=1`。见 [`apps/tools/iox_obs_inject/README.md`](../../apps/tools/iox_obs_inject/README.md)。

```bash
GF_INJECT_SESSION=build/observability/session.jsonl \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

### ADAS 场景 demo（阶段 0 · 无需 Vision Pilot）

**主文件：** `overtake_acc_aeb.jsonl`（变道超车 → ACC → AEB）。`AdasDemo` 仅为 JSONL topic，不是新 app。

```bash
python scripts/gen_adas_scenarios.py
# Foxglove
GMT bridge foxglove --ws --synth-bev --speed 1.0 \
  --jsonl projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl --port 8765
# Studio → ws://127.0.0.1:8765 → Image: /gf/camera/front/compressed
#          Plot: AdasDemo.speed_mps · lead_dist_m · lane_offset_m · brake_active

# GMT 变量轨
GMT gui --project projects/oem_a/afc_with_uss \
  --session projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl
```

注入联调（二选一）：`GF_INJECT_MODE=playhead`（GMT 打开同一 jsonl 回灌）或  
`GF_INJECT_MODE=continuous GF_INJECT_SESSION=…/overtake_acc_aeb.jsonl`。

### GTKWave（离线时序）

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_gmt_vcd.sh
# 或：GMT measure export --format vcd --in …jsonl --out …vcd
```

CLI 入口：**`GMT`**。GMT GUI **不写 wiring**（配置仍只经 gf-config）。

Parent: [tools/README.md](../README.md)
