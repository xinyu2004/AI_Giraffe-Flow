# Giraffe Measure Tool（GMT）

**English:** [README.md](README.md)

仅上位机：**架构 CI**、**measure**、**Foxglove 桥**、**GMT GUI**（选项目 → Live / Tag / 回放 / 回灌）。

多进程 SIL 联调时，终端日志很难对齐「谁在何时发了什么」。GMT 把同一条 tap 流接到本机时间轴与 Foxglove：**scrub / 倍速**对齐 DAG 与变量轨，**playhead 回灌**按帧灌 Ego（gateway 关闭、无双发），需要时再 **Tag → MCAP**。端口少、与 `run_sil` 一条命令配合——**不替代模块，但让模块可反复验证**。

| 入口 | 说明 |
|------|------|
| **`gf-config`** | 唯一作者 GUI（页 1 画布 = 设计期真图） |
| `GMT architect lineage\|dag` | CI / 导出 |
| `GMT measure record\|tag\|export\|import-ndjson` | 录制、裁剪、MCAP/**VCD**、tap NDJSON 导入 |
| `GMT bridge foxglove` | Studio live / JSONL（8765） |
| `GMT bridge live` | GMT GUI live WebSocket（8766） |
| **`GMT gui`** | Live / Tag / DAG / Graphics / Inject / **OTA/UDS（DoIP）** / 导出 |

```bash
pip install -e tools/gmt -e tools/gf-codegen
pip install -e 'tools/gmt[gui]'

GMT gui
GMT gui --project projects/oem_a/afc_with_uss
GMT gui --project projects/oem_a/afc_with_uss/project.yaml
```

**主路径：** 填 **Host** → 顶栏两通道可同时连：

| 通道 | 端口 | 协议 | 用途 |
|------|------|------|------|
| **Live** | 8766 | WebSocket | live_tap 旁观；可选「录制」落盘 |
| **回灌** | 8767 | TCP | playhead（GMT 下发窗口 / inject 帧） |

- 回灌「跟 playhead 灌」开启时：**自动关 Live「跟随最新」**；Live 仍可旁观/录制  
- 回灌结果：顶栏 **绿=已灌 / 红=跳过**，原因在状态栏  
- 「回灌」Tab：事件表；可点行跳 playhead；可选「循环」  
- **「OTA/UDS」Tab**（共用 DoIP + 下方 UDS 日志）：
  - 单选 **OTA / DEM / Collector**（配置仍只在 gf-config）
  - **OTA**：Start OTA → `gf_doip_ota_server`（SIL；非真刷写）；模块区收短，UDS 日志紧挨按钮
  - **DEM**：`0x19` 读 DTC · `0x14` 清除（DEM-lite；非 Classic DEM 编辑器）
  - **Collector**：本机 NDJSON 或 UDS `0x31 01 F201` 读板端环缓
- 「图形」Tab（对齐 CANoe Graphics）：按信号一行；滚轮 / ± 缩放时窗；拖左边线改名称列宽；橙线 playhead  
- 墙钟：session 一条 `session_meta` 锚点 + `(t_ns - t0_ns)`  
- 未加载 `project.yaml`：**回灌禁用**；Live 仍可旁观  

`GF_INJECT_LIVE=0` 可强制回灌时关掉 live_tap。

- **连接 Live**：WS 收流进内存；**默认不落盘**；「跟随最新」控制是否贴尾  
- **录制**：顶栏按钮；默认 `session_live.jsonl`（已有非空则问新建/覆盖）  
- 断开：停录制；保留内存 session，可 scrub / Tag  
- Tag：`M` 标记点；`[` / `]` 片段；Live/Inject 在顶栏连接  
- GMT **不启动 SIL**  

前提：`gf-config` A 页 `live_tap` 已开 + 已 `compile_sil`。  
`run_sil` 将 tap fan-out 到 Live（8766）与 Foxglove（8765）。

### 回灌（playhead）

完整 session 在 GMT；板端 inject 只持 A/B 小窗。SIL 可不设 `GF_INJECT_SESSION`。

```bash
GF_INJECT_MODE=playhead \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# 场景 demo 建议：GF_INJECT_LIVE=all（保留 Ego → BEV）
```

GMT：打开 session → **回灌** → 连接 `host:8767` → 「跟 playhead 灌」→ scrub。

**continuous**：板端读文件。见 [`iox_obs_inject`](../../tools/debug_bridge/iox_obs_inject/README.md)。

```bash
GF_INJECT_SESSION=…/overtake_acc_aeb.jsonl \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

### ADAS 场景 demo

主文件 `overtake_acc_aeb.jsonl`（变道 → ACC → AEB）。由 **GMT 打开 session / 回灌** 加载；`run_sil` 不会自动挂该文件。SIL 上 Foxglove BEV 来自 EgoMotion+Trajectory；Studio 不再依赖 `/gf/AdasDemo` topic。

```bash
python scripts/gen_adas_scenarios.py
# SIL：run_sil → GMT 打开 jsonl → 回灌播放
# 离线（无 SIL）也可：
GMT bridge foxglove --ws --synth-bev \
  --jsonl projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl --port 8765

GMT gui --project projects/oem_a/afc_with_uss \
  --session projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl
```

### GTKWave（离线时序）

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_gmt_vcd.sh
# 或：GMT measure export --format vcd --in …jsonl --out …vcd
```

CLI 入口：**`GMT`**。GMT GUI **不写 wiring**（配置只经 gf-config）。

### OTA/UDS 观测演示数据

```bash
# 种 Collector / DEM / 多级日志（SIL + DoIP），再开 GMT
bash scripts/verify/oem_a_afc_with_uss/smoke_phm_dem_doip.sh
# 或交互：
export GF_COLLECTOR_STORE=$PWD/projects/oem_a/afc_with_uss/build-sil/runtime/collector/events.ndjson
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
GMT gui --project projects/oem_a/afc_with_uss
```

上级：[tools/README.md](../README.md)
