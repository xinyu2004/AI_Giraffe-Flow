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

  ┌──────────┐         ┌─────────────┐         ┌─────────────────────────────┐
  │systemd/  │ ──────► │     EM      │ ──────► │ daemons（按 gf-config）     │
  │init 虚线 │         │ gf_em_daemon│         │ · dlt-daemon?              │
  └──────────┘         │   · 入口    │         │ · RouDi? (iceoryx)         │
                       └──────┬──────┘         │ · SOME/IP daemon?          │
                              │ OSAL Spawn     │ · DDS?                     │
                              ▼                └─────────────────────────────┘
                       ┌────────────┐
                       │  SOA apps  │
                       └──────┬─────┘
                              │ runtime bring-up
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
| **systemd/init** | 系统侧保护层（**非 Giraffe**）；单一 service 只拉 EM | 虚线框 = OS |
| **EM** | `gf_em_daemon`（**入口**） | 按配置 Spawn 平台守护 + SOA apps |
| **daemons（按 gf-config）** | dlt / RouDi / SOME/IP / DDS? | EM 各拉一份；无则不起 |
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

- CARLA / Foxglove / GMT / gf-config UI（→ **Giraffe_Flow**；本图只写「按 gf-config」）
- 具体 OEM 算法细节、某条测试话题名
- 主机 GUI、离线 MCAP 工具链
- 已取消的 HOST 三件套并列（入口就是 EM）

---

## 出图注意

1. 主体 = 中间件环 + EM 分叉（右 `daemons（按 gf-config）` / 下 apps）。
2. 芯片名与 Flow 板内一致：`com · EM · exec · phm · sm · collector · OSAL · diag · ucm · log · dlt · per`（tsync 在环内）。
3. 箭头标动作（Spawn / Alive / NotifyFault / DoIP）。
4. 右框标题用 `daemons（按 gf-config）`，**不要**再加副标。
5. `systemd/init` 虚线；高度约等于 EM 芯片量级。
6. 环底单行对齐：`log → DLT` · `tsync` · `OSAL`。
7. 中文定稿后再画；EN 跟 `README.en.md`。

已出图：

| | 路径 |
|--|------|
| ZH GIF / SVG | `Giraffe_Modules.gif` · `Giraffe_Modules.svg` |
| EN GIF / SVG | `Giraffe_Modules.en.gif` · `Giraffe_Modules.en.svg` |

再生：`python3 result_pic/Giraffe_Modules/scripts/render_gif.py`（加 `--en` 同时出英文）。
