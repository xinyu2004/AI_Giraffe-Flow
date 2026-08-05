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

## 1. Live：实时看 + 实时落盘（推荐）

`run_sil` 读 `generated/observability.json`：live 有效则起  
`gf_iox_obs_tap`，fan-out 到 **GMT live**（8766）与 **Foxglove**（8765），可选 tee 落盘。

```bash
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# 已编过：
# GF_SKIP_COMPILE=1 bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

| 客户端 | 连接 |
|--------|------|
| **Foxglove Studio** | Open connection → `ws://127.0.0.1:8765` |
| **GMT GUI** | 打开 **project.yaml** → host:port → **连接**；可关 **跟随最新**（只记盘不跟播） |
| **回灌 playhead** | SIL：`GF_INJECT_MODE=playhead` → GMT「回灌」页连 `:8767`（跟 playhead 灌） |

Foxglove 连接后加 **Raw Messages** / **Plot**，勾选 `/gf/EgoMotion`、`/gf/Trajectory`。

落盘默认：`projects/.../build-sil/observability/session_live.jsonl`（`${BUILD}/observability/`；`GF_LIVE_SESSION` / `GF_OBS_OUT` 可改；`GF_LIVE_TEE=0` 关 tee）。

```bash
# 推荐：终端 run_sil + GUI 连接
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
GMT gui --project projects/oem_a/afc_with_uss
# 顶栏 Live 连接/录制；M=标记点；打开 session → 回灌
```

**另一台电脑：** 默认 `GF_WS_HOST=0.0.0.0`，Studio 填 `ws://<SIL 主机 LAN IP>:8765`。

**白名单：** A 页 `live_tap.services` → compose → `observability.json`。`production-release` 不编 tap。  
**tap 加入时机：** Verify / `compile_sil` 时 compose 自动把 `debug_bridge/iox_obs_tap` 写入 `GF_APPS`（勿手写进 apps）。

**画布：** B 页拖绿色/橙色圆点改边（Out 拉线用 Ctrl+拖）。

## 2. 事后录 session → MCAP（验证脚本）

```bash
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh
```

产物默认在 `${BUILD}/observability/`（即 `projects/.../build-sil/observability/`）：

| 文件 | 说明 |
|------|------|
| `session.jsonl` | 从主链 SIL 日志解析的事件 |
| `session_tagged.jsonl` | Tag 窗 |
| `session.mcap` | 多 topic MCAP |

```bash
GMT bridge foxglove --mcap projects/oem_a/afc_with_uss/build-sil/observability/session.mcap
```

## 2b. ADAS 场景 demo（合场景 · 无需 SIL）

**主文件** `overtake_acc_aeb.jsonl`：变道超车 → ACC → AEB。`AdasDemo` 是 JSONL topic，不是新 app。

```bash
python scripts/gen_adas_scenarios.py
GMT bridge foxglove --ws --synth-bev \
  --jsonl projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl --port 8765
# Studio → ws://127.0.0.1:8765 · Image + Plot(AdasDemo.*)

GMT gui --project projects/oem_a/afc_with_uss \
  --session projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl
```

注入：场景联调推荐  
`GF_INJECT_MODE=playhead GF_INJECT_LIVE=all bash …/run_sil.sh`  
→ **GMT 打开** `overtake_acc_aeb.jsonl` → 回灌播放  
（`run_sil` 不自动加载该 JSONL；默认 `GF_SYNTH_BEV=1`，Foxglove 用 **EgoMotion+Trajectory 合成 BEV**）。  
`AdasDemo` 在 GMT 变量轨对照剧本；主链 BEV 不依赖 JSONL 画图。

## 3. WebSocket 回放（非 live）

```bash
GMT bridge foxglove --ws --jsonl projects/oem_a/afc_with_uss/build-sil/observability/session_tagged.jsonl --port 8765
```

## 4. Tag 窗示例（CLI）

```bash
GMT measure tag --in projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl \
  --out projects/oem_a/afc_with_uss/build-sil/observability/session_tagged.jsonl --label demo
```

## 5. GMT GUI：录制 / Tag / 主机回放

```bash
GMT gui --project projects/oem_a/afc_with_uss \
  --session projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl
```

- **文件**：从日志录制、导入 NDJSON、跟随 live、导出 MCAP / **VCD**  
- **Tag**：● 标记点（`M`）/ ▬ 片段（`[` `]`）→ `session.tags.json`  
- **回放**：本窗 scrub；或菜单打开 Foxglove WS 回放；动画 DAG 跟 playhead  

## 5.1 GTKWave：时序对齐（与 Foxglove 互补）

| 工具 | 看什么 |
|------|--------|
| **Foxglove** | 语义 topic 实时 / 回放（值含义） |
| **GTKWave** | 离线时序、多轨对齐、抖动（`t_ns`） |

```bash
# 尖刺（stub fixture → VCD）
bash scripts/verify/oem_a_afc_with_uss/smoke_gmt_vcd.sh

# 或手工：
GMT measure export --format vcd \
  --in tools/gmt/fixtures/session_stub.jsonl \
  --out projects/oem_a/afc_with_uss/build-sil/observability/session_stub.vcd
gtkwave projects/oem_a/afc_with_uss/build-sil/observability/session_stub.vcd   # 若已安装
```

轨名：`gf.<Service>.<field>`（如 `gf.EgoMotion.seq`）。GUI：**文件 → 导出 VCD**。

## 6. G3 闭环回灌

**不要**与 gateway 同时发 EgoMotion。

```bash
# B1：替 gateway，全链消费者
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_inject.sh

# B2：单模块 DUT（例 sensing.uss）
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_inject_b2.sh

# 或手工 B1：
GF_SKIP_COMPILE=1 GF_INJECT_SESSION=projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# 手工 B2：
GF_SKIP_COMPILE=1 GF_INJECT_SESSION=projects/oem_a/afc_with_uss/build-sil/observability/session.jsonl \
  GF_INJECT_DUT=sensing.uss \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

`vehicle-debug` compose 会编 `debug_bridge/iox_obs_inject`；`production-release` 不编。  
详情：[tools/debug_bridge/iox_obs_inject/README.md](../../../tools/debug_bridge/iox_obs_inject/README.md)  
（构建产物仍在 `$GF_BUILD_DIR/apps/debug_bridge/...`，与 compose id 一致。）
