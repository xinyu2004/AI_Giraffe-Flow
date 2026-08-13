# frame_ingest / bridge / scenarios 职责（为什么拆开）

## 完整前视产品路径

`carla_bridge` **必须**（相对 FCM）：没有图像 tip，FCM 无法按产品路径运行。  
`frame_ingest.bridge.enabled=true` 表示 Flow 起 tip 写端（类 ISP 适配）。

| 角色 | 负责 | 不负责 |
|------|------|--------|
| **frame_ingest** | tip 插座：`pixel_format`、paths、`ego_source`、是否起 bridge | pygame、ACC 剧情、变道脚本、FCM 内部算法 |
| **carla_bridge** | 挂 tip 相机→YUV、ego tip、**仅**执行 Giraffe cmd；**不** spawn hero/lead；长驻重连（**非 systemd**） | 布景、pygame、truth、初速 IC |
| **run_cases / cases** | Client A：布 lead/天气、**摆位+IC**（方案1）、pygame、truth；`run_cases.py` 长驻少开关窗（**非 systemd**） | 连续控 ego、写 FCM tip |
| **CARLA UE** | 仿真 **server**（RPC `:2000`） | — |
| **manual_control.py** | CARLA 官方/人开（可选，勿与 scenario 抢同一车） | 不是 Giraffe 产品组件 |
| **Foxglove** | 产品侧可视化（BEV + tip CompressedImage） | 与 scenario 窗口并存 |

### client / server（HIL 常双机）

| 角色 | 是什么 | 典型机器 |
|------|--------|----------|
| **Server** | CARLA **UE** | Windows 仿真机 |
| **Client A** | `carla_scenarios/cases/**/*.py` | 常与 UE 同机 |
| **Client B** | SIL `frame_ingest` → `carla_bridge` | Linux SIL |

两端 Python 都是 client，都连同一 UE。HIL 下各有一份 `carla.env`（`CARLA_HOST` 不同）。

```text
Windows:  carla_scenarios/carla.env  → cases/.../acc.py ──RPC──┐
                                                    ├→ UE :2000 (server)
Linux:    projects/<sku>/carla.env → run_sil → bridge ─┘
          tip 写在 SIL 本机 /tmp/gf_front.yuv → FCM
```

- **`run_sil.sh`**：起 bridge 时 **自动加载** SKU `carla.env`（无需 `enable_*.sh`）。  
- **不要**把 scenario 的 `CARLA_HOST=127.0.0.1` 抄到 SIL；SIL 缺 SKU 文件会 WARN。

### 为什么 `acc.py` 不替代 bridge？

1. **bridge = tip 适配层（假 ISP）** — 场景脚本随 case 换，不应重写 tip 协议。  
2. **scenarios = 功能 case** — 真值 / 布世界，不是 tip 写端。  
3. **pygame ≠ 产品可视化** — 产品观测走 Foxglove。

## 已删除（产品冻结）

- `bridge.dry_run`：完整 CARLA 产品路径下无意义；开发无 UE tip 自检仅用 bridge **CLI/env**。  
- `bridge.demo_lane_change*`：变道/剧情由 `carla_scenarios/` 定义。

## 环境变量与两份 carla.env

| 文件 | 谁读 | 仓库 |
|------|------|------|
| `carla_scenarios/carla.env` | scenario / `run_cases` | 跟踪（通用，默认 `127.0.0.1`） |
| `projects/oem_a/afc_no_uss/carla.env` | `run_sil` → bridge | gitignore；从 `carla.env.example` 复制 |

| 变量 | 用途 |
|------|------|
| `CARLA_HOST` / `CARLA_PORT` | **UE（server）** 地址 |
| tip 路径（如 `/tmp/gf_front.yuv`） | **SIL 本机文件**（bridge RPC 取帧后写出） |
| `GF_CARLA_PYTHON` | SIL 上含匹配 `carla` 的解释器（SKU `carla.env`） |
| `GF_CARLA_WAIT_S` | 首次连 UE 的耐心窗口（秒） |
| `GF_CARLA_CONNECT_TIMEOUT_S` | 单次 RPC 超时（远程 HIL 建议 ≥10） |
| `GF_CARLA_BRIDGE_ON_FAIL` | 默认 `reconnect`：掉线/换场景重挂 tip；勿再用 `exit` 当实验室默认 |
| `GF_CARLA_RECONNECT_S` | 重连间隔（秒） |
| `GF_PIXEL_FORMAT` / tip paths | 见 freeze / frame_ingest |

连接后两边打印同一版本条，便于双机对照：

```text
===
carla API  client=…  server=…
===
```

### CI / 批量 case

```powershell
# 场景机：编辑 carla_scenarios\carla.env 后
# 无 SIL → ACC/AEB 应为 fail（no_giraffe_control），不再假绿
python carla_scenarios\run_cases.py
```


```bash
# SIL：cp carla.env.example carla.env 后直接 run_sil，再跑场景
./projects/oem_a/afc_no_uss/scripts/run_sil.sh
```

- 判定契约见 [scenarios.md](./scenarios.md)：scenario 不控 ego；时距 / 碰撞 / cmd 新鲜度。  
- 场景与 SIL **独立生命周期**。

## 方案1 边界（已落地方向）

- 两 client **同 UE 端口**（如 `:2000`）。  
- ego（`role_name=hero`）：scenario **可摆位 + AEB 初速 IC**；连续控车 **仅 Giraffe→bridge**。  
- bridge **等待** scenario hero，不再自己造车。  
- 除 **EM** 外不使用 systemd；bridge / `run_cases` 均为会话子进程长驻。  
- SIL 心跳：`carla_fps` / `tip_write` / `tip_read` / `fcm_read`。

```bash
# 场景机（长驻 Client A）
python3 carla_scenarios/run_cases.py cases/longitudinal
# SIL：重启 run_sil 以加载新 bridge
```

## 后续计划（待讨论）

- **HIL 双 client 延时优化**（验通后）：tip 改 SHM / 减 RPC；自适应超时。  
- **inject 仅跑 planning**（无 FCM / 无图像）。  
- frame_ingest UI 继续收口。
