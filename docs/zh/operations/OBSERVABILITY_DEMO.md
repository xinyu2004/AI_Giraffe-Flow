# 可观测演示（P2 O/F + P2.5 Live · 约 15 分钟）

> 配套：`GMT measure record|tag|export` · `GMT bridge foxglove`  
> 主链 SIL：`projects/oem_a/afc_with_uss`（**iceoryx**；与 CycloneDDS 旁路无关）  
> **说明：** `GMT bridge foxglove --ws` 是自研 Foxglove WebSocket **子集**，**不是** ROS 包 `foxglove_bridge`。

## 0. 前置（1 min）

```bash
source .venv/bin/activate
# 若尚未编过 SIL：
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
```

## 1. Live：实时看 wiring 语义字段（P2.5 · 推荐）

旁路进程 `gf_iox_obs_tap` 经 iceoryx **只订** `EgoMotion` + `Trajectory`，stdout NDJSON → GMT WS → Studio。

```bash
bash projects/oem_a/afc_with_uss/scripts/run_sil_live_foxglove.sh
# 已编过可：
# GF_SKIP_COMPILE=1 bash projects/oem_a/afc_with_uss/scripts/run_sil_live_foxglove.sh
```

Foxglove Studio → **Open connection** → Foxglove WebSocket → `ws://127.0.0.1:8765`  
连接成功后加 **Raw Messages** 或 **Plot** 面板，勾选 `/gf/EgoMotion`、`/gf/Trajectory`（Studio 会发 `subscribe`，桥才推二进制 Message Data）。  
终端应出现 `subscribe sub=… channel=…`，随后字段（如 `speed_mps` / `point_count`）会更新。

**另一台电脑连本机：** 脚本默认 `GF_WS_HOST=0.0.0.0`。Studio 填 `ws://<跑 SIL 那台的局域网 IP>:8765`。防火墙需放行 8765。

**白名单：** `req.yaml` → `observability.live_tap.services`（gf-config A 页）；compose 写入 `generated/observability.json`，脚本经 `GF_OBS_LIVE_SERVICES` 传给 tap。`production-release` 剖面不编 tap。

**画布单端口：** B 页右键某个 Out/In 点 → 移到左/右/上/下（只动该服务，例如只移 EgoMotion）。

等价手工管道：

```bash
# 先起四进程 SIL（gateway 参数 0 = 常驻），再：
build/apps/tools/iox_obs_tap/gf_iox_obs_tap \
  | GMT bridge foxglove --ws --stdin --host 0.0.0.0 --port 8765
```

资源提示：仅多一个订阅者；GMT/Studio 在上位机。量产 / HIL 应用 **vehicle-debug** 才开 tap，production 关掉。

---

## 2. 事后录 session → MCAP（P2 O/F）

```bash
bash projects/oem_a/afc_with_uss/scripts/smoke_sil_observability.sh
```

产物默认在 `build/observability/`：

| 文件 | 说明 |
|------|------|
| `session.jsonl` | 从 multiproc 日志解析的事件 |
| `session_tagged.jsonl` | Tag 窗 |
| `session.mcap` | 多 topic MCAP |

```bash
GMT bridge foxglove --mcap build/observability/session.mcap
# Studio → Open local file
```

HTTP 分享（可选）：

```bash
GMT bridge foxglove --mcap build/observability/session.mcap --serve --port 8765
```

## 3. WebSocket 回放（非 live）

```bash
GMT bridge foxglove --ws --jsonl build/observability/session_tagged.jsonl --port 8765
```

## 4. Tag 窗示例

```bash
GMT measure tag --in build/observability/session.jsonl \
  --out build/observability/window.jsonl \
  --from-ns 0 --to-ns 500000000 --label first_500ms
GMT measure export --in build/observability/window.jsonl --out build/observability/window.mcap
```

## 验收对照

- [x] Record：SIL 日志 → JSONL
- [x] Tag：时间窗 / label
- [x] 真实 session → MCAP
- [x] Foxglove：Studio 打开 MCAP；可选 WS 回放 / HTTP
- [x] **Live WS**：iceoryx tap → `--ws --stdin`，语义字段 `/gf/EgoMotion` + `/gf/Trajectory`
- [x] CI fixture：`scripts/smoke_ta.sh` 仍回归 stub export
