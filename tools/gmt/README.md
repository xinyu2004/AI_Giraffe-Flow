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
| **Live** | 8766 | WebSocket | live_tap 旁观 / 记盘（回灌时默认只订**下游**） |
| **回灌** | 8767 | TCP | playhead inject seek |

- 回灌「跟 playhead 灌」开启时：**自动关 Live「跟随最新」**（避免拽走 playhead）；Live 仍可只记盘  
- 回灌结果：顶栏 **绿=已灌 / 红=跳过**，原因在状态栏（无弹窗）  
- 「回灌」Tab：事件表（墙钟 / topic / 已发布|跳过），可点行跳 playhead  
- 「变量轨」Tab：用户添加变量（每变量一行）；滚轮缩放时间窗；橙线 playhead  
- 墙钟：**方案 1** — session 一条 `session_meta` 锚点 + `(t_ns - t0_ns)`（非每行 wall_time）  
- 未加载 `project.yaml`：顶栏黄条提示；**回灌连接禁用**；Live 仍可仅记盘  

`GF_INJECT_LIVE=0` 可强制回灌时关掉 live_tap。

- 连接：WS 收 tap NDJSON，落盘 `session_live.jsonl`；勾选 **跟随最新**（默认）则 playhead 贴尾，DAG/先后更新  
- **取消「跟随最新」= 只记盘不跟播**：继续写 session，可停在某一帧 scrub / Tag（快捷键 `F` 切换）  
- 断开：保留 session，可 scrub / Tag  
- 高级：**仅跟随 live 文件…** + 传输条 **跟随文件** — 不连网，只 tail 已有 JSONL（是否跳最新仍由「跟随最新」控制）  
- Tag：`M` 标记点；`[` / `]` 片段；`Ctrl+R` / `Ctrl+Shift+R` 连接/断开  
- GMT **不启动 SIL / 不调用 run_sil**  

前提：`gf-config` A 页 `live_tap` 已开 + `vehicle-debug` 已 `compile_sil`。  
`run_sil` 将 tap 同时 fan-out 到 `GMT bridge live`（8766，`GF_LIVE_PORT`）与 Foxglove（8765）。

### 回灌（playhead）

SIL 侧（B1/B2 拓扑由 `run_sil` 环境变量决定；GMT 不管）：

```bash
GF_INJECT_SESSION=build/observability/session.jsonl \
  GF_INJECT_MODE=playhead \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

GMT：打开**同一** session → **回灌**页 → 连接 `host:8767` → 勾选「跟 playhead 灌」→ scrub。  
详见 [`apps/tools/iox_obs_inject/README.md`](../../apps/tools/iox_obs_inject/README.md)。

### GTKWave（离线时序）

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_gmt_vcd.sh
# 或：GMT measure export --format vcd --in …jsonl --out …vcd
```

CLI 入口：**`GMT`**。GMT GUI **不写 wiring**（配置仍只经 gf-config）。

Parent: [tools/README.md](../README.md)
