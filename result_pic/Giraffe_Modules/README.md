# Giraffe_Modules（文字版布局稿）

> **板内中间件模块**如何起来、如何协作（`sm` / `phm` / `exec` / `com` …）。  
> 不是 Giraffe_Flow（那张讲 CARLA / Foxglove / GMT 外设与工具）。  
> 英文：[`README.en.md`](./README.en.md)

| 图 | 讲什么 |
|----|--------|
| **Giraffe_Flow** | 整机数据路径：外设 · 配置 · 主机工具 ↔ 板 |
| **Giraffe_Modules** | **板内** `middleware/*`：模块清单、启动、互相调用 |

真相源：[`middleware/README.md`](../../middleware/README.md)

---

## 建议整图构图（以模块为中心）

```text
┌──────────────────────────────────────────────────────────────┐
│  TITLE: Giraffe Modules · 中间件如何起来、如何协作              │
└──────────────────────────────────────────────────────────────┘

  ┌─────────────┐
  │ systemd/init│  系统侧 · 非 Giraffe（虚线框；高度≈HOST 一半）
  │ 系统侧守护   │
  └──────┬──────┘
         │
         ▼
       〔 HOST  ┌─ 平台守护（非 SOA）──────────────┐
               │  dlt-daemon（按需 · log.yaml sinks）│
               │       ↓                            │
               │  RouDi (iceoryx)                   │
               │       ↓                            │
               │  EM (gf_em_daemon)                 │
               └──────────────┬─────────────────────┘
                              │ OSAL Spawn（em_launch 拓扑）
                              ▼
                 ┌────────────────────────────┐
                 │   SOA apps（业务进程）        │
                 │   gateway · sensing · …    │
                 └─────────────┬──────────────┘
                               │ 每进程内：runtime bring-up
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                 进程内中间件环（本图主体）                        │
│                                                              │
│     exec Client ◄── Offer / Alive ──► phm                    │
│         │                              │                     │
│         │ EnsureGroup                  │ NotifyHealthFault   │
│         └──────────────► sm ◄──────────┘                     │
│                     Off / Running / Updating                 │
│                              │                               │
│                              ▼                               │
│                         collector ──persist──► per           │
│                         (DEM-lite / 事件)                     │
│                                                              │
│     com ──Proxy/Skeleton──► bindings                         │
│                             (iceoryx | SOME/IP | DDS)        │
│                                                              │
│     diag ──DoIP/UDS──► ucm ──► sm Updating + phm pause       │
│                           └──fail──► collector               │
│                                                              │
│     log → DLT  ·  tsync  ·  OSAL                             │
└──────────────────────────────────────────────────────────────┘

  FuSa 证据挂在：exec / phm / sm / collector … 的真实行为上
  （POLICY · cases · metrics · safety-case）
```

---

## 模块卡片（出图时每块一卡）

### 启动与生命周期

| 模块 | 一句话 | 关键协作 |
|------|--------|----------|
| **systemd/init** | 系统侧守护（**非 Giraffe**）；同级拉起 HOST | 虚线框 = OS 所有；脚本或 unit |
| **HOST · dlt-daemon** | COVESA DLT（**按需**：`log.yaml` sinks 含 `dlt`） | 上位机 dlt-viewer / GMT Logging |
| **HOST · RouDi** | iceoryx 通信底座 | com binding 依赖 |
| **HOST · EM** | `gf_em_daemon` | 拓扑 OSAL Spawn SOA apps |
| **OSAL** | 时钟 / 线程 / **process** Spawn·Wait·Kill | EM 唯一用它起停进程 |
| **exec / EM** | `ExecutionClient` + daemon | 读 em_launch；失败可 relaunch |
| **sm** | 功能组 Off ↔ Running ↔ Updating | runtime EnsureGroup；PHM 故障通知；UCM 进 Updating |
| **phm** | Alive / Deadline / Logical | App ReportAlive；失败 → log / collector / sm / EM restart |
| **runtime** | 进程内 bring-up 胶水 | log → SM → Exec Offer → PHM Alive → collector 钩子 |

### 通信与时间

| 模块 | 一句话 | 关键协作 |
|------|--------|----------|
| **com** | 统一 Event Proxy/Skeleton | → bindings；App 只认服务名 |
| **bindings** | iceoryx / SOME/IP / DDS / … | 被 com 调用；需 RouDi 等底座 |
| **tsync** | 时间同步骨架 | 依赖 OSAL Now；可裁剪 |
| **log** | 日志 lite → **DLT sink** | bring-up / 故障；上位机只走 DLT |

### 诊断 · OTA · 事件 · 持久化

| 模块 | 一句话 | 关键协作 |
|------|--------|----------|
| **collector** | 事件环 + DEM-lite → DTC | PHM/UCM/进程喂入；**per** 落盘；**diag** UDS 拉取 |
| **per** | 跨重启 KV | collector DTC / 版本等 |
| **diag** | DoIP + UDS | → **ucm** OTA；主机 GMT 只是客户端 |
| **ucm** | PackageManager + OtaOrchestrator | SM Updating + PHM pause；失败进 collector |

### 支撑（小字即可）

| 模块 | 说明 |
|------|------|
| **core** | Result / ErrorCode，全包依赖 |
| **hal** | 板级传感/执行骨架（P1+） |
| **trace** | 时序 → VCD（debug-path，非 ASIL 证据） |

---

## 关键调用链（文字）

**健康闭环**

```text
App ReportAlive → phm Evaluate
    → collector（+ 可选 per DTC）
    → sm NotifyHealthFault
    和/或 exec/EM RequestRestart（或 exit 75 relaunch）
```

**OTA 窗**

```text
DoIP(diag) → ucm OtaOrchestrator
    → sm Updating
    → phm SetPaused
    → 失败 → collector
```

**通信**

```text
App ──服务名──► com ──► bindings ──► iceoryx | SOME/IP | DDS
```

---

## 明确不画进本图

- CARLA / Foxglove / GMT / gf-config（→ **Giraffe_Flow**）
- 具体 OEM 算法细节、某条测试话题名
- 主机 GUI、离线 MCAP 工具链

---

## 出图注意

1. 主体 = 中间件环 + EM 启动箭头；不要再画一整圈外设。
2. 芯片名与 Flow 板内一致：`com · EM · exec · phm · sm · collector · OSAL · diag · ucm · log · dlt · per`（tsync 在环内）。
3. 箭头标动作（Spawn / Alive / NotifyFault / DoIP），不要只画框。
4. HOST 框 = 平台守护；SOA apps 在框外。`dlt-daemon` 副标写清按需配置。
5. 括号在左，**HOST 文字在括号右侧**（靠守护框）；`systemd/init` 虚线芯片高度≈HOST 一半。
6. 环底单行对齐：`log → DLT` · `tsync` · `OSAL`。
7. 中文定稿后再画；EN 跟 `README.en.md`。

已出图：

| | 路径 |
|--|------|
| ZH GIF / SVG | `Giraffe_Modules.gif` · `Giraffe_Modules.svg` |
| EN GIF / SVG | `Giraffe_Modules.en.gif` · `Giraffe_Modules.en.svg` |

再生：`python3 result_pic/Giraffe_Modules/scripts/render_gif.py`（加 `--en` 同时出英文）。
