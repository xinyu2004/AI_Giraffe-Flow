# 中间件模块与 gf-config 配置规划

> 配套：[ROADMAP.md](ROADMAP.md) · [DESIGN.md](../architecture/DESIGN.md) · [P2_PLAN.md](P2_PLAN.md)  
> **状态（2026-08-04）：** **P3 两页 UI 已落地**（页 1 信号与应用 · 页 2 平台运行时：exec / **EM 启动表** / PHM / 日志 / Collector…）；废止「不做 DEM」旧口径。  
> **同日工具面：** gf-config 日志表行选中 UX + 重复 context Verify；撤销跳页；GMT **OTA/UDS** 单页汇合 OTA·DEM·Collector（见 [DOIP_OTA.md](DOIP_OTA.md)）。历史冻结字段见 §8。  
> **产品定位：** AUTOSAR **AP lite**（`gf_ara::*`）。后置项登记：[AP_LITE_BACKLOG.md](AP_LITE_BACKLOG.md)。

本文回答：

1. **`gf_ara::*` 各模块**完整 AP 视角要什么、我们分阶段做什么。  
2. **`gf-config` 配什么、几页、什么顺序** — 先信号图，再平台细节；GMT 不写配置。

---

## 0. 总原则

| # | 原则 |
|---|------|
| P1 | **配置仍分三层资产**：① 开关 · ② com 拓扑 · ③ 平台小表；**GUI 收成两页**（见 §4） |
| P2 | **只有 `com` 需要信号图**；其余模块不是第二套 dataflow |
| P3 | **`gf-config` = 作者 GUI**；**codegen = 生成/校验**；**GMT = 观测 / OTA 操作面**（**不写** wiring/req/platform） |
| P4 | **不做完整 Classic DEM**；必做 **Event Collector 最小集**（有 CP 则转发；无 CP/纯 DoIP 则 AP 侧 DEM-lite 子集） |
| P5 | **先 YAML 资产，后 GUI**；GUI 只编辑已冻结字段 |
| P6 | 对外命名 **`gf_ara::<fc>`**；文档可写对标 `ara::<fc>` |
| P7 | **工作流顺序**：打开 project → **先画应用节点与信号** → **再配平台运行时** → Verify / Generate |

```text
① 薄 SKU（profile/bindings/观测…）  ┐
② com 拓扑（节点 + 连线）           ├─→ gf-config【1 · 信号与应用】（默认首页）
                                   ┘         wiring.yaml + req 薄字段
③ runtime_modules + platform/*     ──→ gf-config【2 · 平台运行时】
                                              （含 Event Collector）
                                    │
                                    ▼
                         compose → gf.sor.json → generate / CMake
                                    │
                                    ▼
              GMT：只读 lineage / measure / Live·Inject；OTA/UDS（OTA·DEM·Collector）经 DoIP 操作（不写回配置）
```

---

## 1. 三层配置模型（资产）与两页 GUI（交互）

| 层 | 问题 | 载体 | gf-config（P3） |
|----|------|------|----------------|
| **① 开关（薄）** | 本 SKU 要不要 binding / 观测 / 剖面？ | `req.yaml` 薄字段 | **页 1** 顶栏/侧栏 |
| **①′ 模块开关** | 要不要编进 exec/phm/…？ | `req.runtime_modules` | **页 2** 顶部（与平台表同页） |
| **② 拓扑** | 谁 provide/require？边怎么走？ | `wiring.yaml` | **页 1** 画布（主战场） |
| **③ 清单** | FG？Alive？DID？Collector？ | `platform/*.yaml` | **页 2** 子导航 |

「要不要编模块」与「要了填什么」同属运行时，故 **runtime_modules 不再独占一页排在画图之前**。

---

## 2. 模块总表（规划全景）

图例：**配置负担** = 对集成工程师的工作量（相对 com）。

| 模块 | 对标 | 配置负担 | ① 开关 | ② 拓扑 | ③ 清单 | 实现阶段 | 备注 |
|------|------|----------|--------|--------|--------|----------|------|
| **core** | `ara::core` | 无 | 常开 | — | — | ✅ P0 | |
| **com** | `ara::com` | **高** | bindings | **wiring** | QoS 可选后置 | ✅ P0+ | **唯一信号图** |
| **osal** | （平台） | 低 | CMake | — | — | ✅ clock/thread/**process** | 不进 gf-config；EM 依赖 |
| **log** | `ara::log` | 低 | runtime_modules | — | 级别/通道 | P0–P3 lite | §3.5 |
| **exec** | `ara::exec` | 中 | runtime_modules | — | 进程↔FG + **em_launch** | ✅ P2 清单 · **OS EM** | §3.2 |
| **sm** | `ara::sm` | 中低 | runtime_modules | — | FG/转移 | ✅ P3 FG Off/Running/Updating | §3.3 |
| **phm** | `ara::phm` | 中 | runtime_modules | — | entity 表 | ✅ Logical + notify_sm / restart→EM | §3.4 |
| **collector** | Event Collector | 中 | runtime_modules / 随 phm·diag | — | 源/转发/存储 | ✅ P3 最小集；**非 Classic DEM** | §3.9 |
| **diag** | `ara::diag` | 中 | runtime_modules | — | DoIP + DID | stub → **P3 会话** | §3.6 |
| **ucm** | `ara::ucm` | 中 | runtime_modules | — | 包源/回滚 | Spike → **P3+GMT OTA** | §3.7 |
| **trace** | （扩展） | 低 | 可选 | — | 导出 | P2+ | |
| **per** / **tsync** | `ara::*` | 低 | runtime_modules | — | 路径/角色 | **P3 骨架** | |
| **nm** / 安全簇 | | 高 | runtime_modules | — | 策略 | P3+ | |
| **hal** | （扩展） | 中 | 板级 | — | 板级 yaml | P3z | |
| **Classic DEM 全栈** | Classic | — | — | — | — | **不做** | 编辑器/全量 FDC 等 |

---

## 3. 分模块：完整 AP 要什么 vs 我们配什么

### 3.1 `gf_ara::com`

| 完整 AP | Giraffe / gf-config |
|---------|---------------------|
| Service Interface、部署、实例、E2E… | **wiring** deployments + dataflows；bindings；Generate → Proxy/Skeleton |

**gf-config：** 页 1 画布 + 薄 bindings。  
**不做：** 在 SKU 区重复编辑每一条 dataflow。

### 3.2 `gf_ara::exec`（含 OS EM）

| 完整 AP | 我们的 ③ |
|---------|----------|
| Execution Manifest | **`exec.yaml`：** `name`、`function_group`、`depends_on[]`、`execution_client` |
| Process start / restart | **`em_launch.yaml`：** `name`、`binary`、`args[]`、`max_restarts` → `gf_em_daemon`（经 OSAL Spawn） |
| Machine State / 多机 | 再议 |

进程名只读自 wiring（非 `external.*`）。**gf-config：** 页 2「执行 / 功能组」+「**EM 启动表**」。  
运行期：com 底座 → EM → 按拓扑 Spawn Apps；`phm.on_failure: restart` + `GF_EM_MANAGED` → exit 75 relaunch。

### 3.3 `gf_ara::sm`

| 完整 AP | 规划 |
|---------|------|
| FG 状态机、与 exec 协同 | **P2：** `exec.yaml` → `function_groups[]`；**P3：** 状态机加深（可仍同文件或拆 `sm.yaml`，实现时冻结） |
| 复杂降级图 | P3+ |

**gf-config：** 页 2；P3 起可编辑转移/初始，不做完整「第二个 Stateflow」。

### 3.4 `gf_ara::phm`

| 完整 AP | 我们的 ③（`platform/phm.yaml`） |
|---------|--------------------------------|
| Alive / Deadline / Logical | **P2：** Alive + 可选 Deadline；**P3：** Logical + `notify_sm` / Collector |
| 跨 ECU PHM | 有 CP 时经 Collector 转发，不做第二套跨域 PHM |

**gf-config：** 页 2 表格。

### 3.5 `gf_ara::log`

载体：`platform/log.yaml`（`default_level`、`contexts[]`）。  
观测粗开关（live_tap/record）留在 **页 1 薄 SKU**，与 log 级别分工。

**gf-config（页 2 · 日志）：** 默认级别 + 按模块覆盖表；新增行模块可空、级别默认 `INFO`；**行号选中**（行号/模块浅蓝，级别枚举色不变）；compose **拒绝重复 context id**。

### 3.6 `gf_ara::diag` — DoIP / UDS 子集（不是 Classic DEM）

| 完整 AP | 我们的 ③（`platform/diag.yaml`） |
|---------|--------------------------------|
| DM、UDS、DoIP、DID/RID… | `standards`（14229 父 / 13400 子）+ `doip` + **`timing`** + **`ota_transfer`** + DID/RID 最小表 |
| Classic DEM 全栈 | **不做**；事件见 §3.9 |

**P3-4（已落地）：** 会话级 DoIP + GMT **OTA/UDS** 操作面（OTA · DEM-lite · Collector 同页）。字段与操作面见 [DOIP_OTA.md](DOIP_OTA.md)。  
**gf-config：** 页 2「诊断」——可折叠 doip / timing / ota_transfer；下载 SID 显式 `0x38`/`0x34`/`0x31`。不提供完整 DTC 防抖策略编辑器。  
**0x27 插件路径：** 不进 yaml；GMT 本地设置 + 板端 `GF_DIAG_SEC_PLUGIN`。

```yaml
# platform/diag.yaml（节选）
standards:
  iso_14229_uds: true
  iso_13400_doip: true
doip:
  enabled: true
  logical_address: 0x0E00
  tester_address: 0x0E80
  tcp_port: 13400
timing:
  s3_server_ms: 5000
  tester_present_period_ms: 2000   # 须 < s3_server_ms
  p2_server_ms: 50
  p2_star_server_ms: 5000
  security_delay_ms: 10000
ota_transfer:
  mode: request_file_transfer     # | request_download | routine_sil
  require_programming_session: true
  require_security: true
  max_block_length: 1024
```

### 3.7 `gf_ara::ucm`

| 阶段 | 内容 |
|------|------|
| P2 | `ucm.yaml` 空壳 + Spike 选型 |
| P3-4 | 编排 + SIL stub Activate；**操作面在 GMT OTA/UDS（DoIP）**；真 RAUC → P3z |

**gf-config：** 页 2 策略字段；**不**在 gf-config 里做刷写进度 UI。  
详见 [DOIP_OTA.md](DOIP_OTA.md) · [OTA_SPIKE.md](OTA_SPIKE.md)。

### 3.8 其余（P3 骨架 / P3+）

per、tsync、nm、crypto/iam/idsm/fw、hal — 见模块总表；板级 hal 跟 P3z。

### 3.9 Event Collector（P3 最小集 · 替代「不做 DEM」）

| 场景 | AP（Giraffe）职责 | 谁做状态/防抖/老化 |
|------|-------------------|-------------------|
| **有 MCU AUTOSAR CP** | 汇聚 PHM/应用/通信错误 → 规范化事件 → **转交 CP DEM**（跨域 IPC / gateway） | CP DEM |
| **无 CP / 纯 DoIP** | 同上收集 + **持久化/查询**；经 DoIP/UDS 子集向 tester 报告 | AP **DEM-lite**（事件库，挂在 diag/Collector 子系统） |

**无论有无 CP，都必须有收集机制。** DoIP 换的是总线，不是「可以没有事件管理」。

**配置（③，建议 `platform/collector.yaml` 或并入 `diag.yaml`，实现时冻结一种）：**

- 源：phm entity / 进程 / 通信错误码  
- 转发：`forward: cp_dem | local_store | both`  
- 本地：是否落盘、最大条数（DEM-lite）  
- 映射：内部 event_id → DTC（可选，最小表）

**gf-config：** 页 2「事件收集」子页（写 `collector.yaml`）。  
**GMT：** OTA/UDS 页 · Collector 单选 — 读本机 NDJSON 或 UDS `0x31 01 F201` 环缓；**DEM** 单选 — `0x19`/`0x14`（DEM-lite）。  
**不做：** Classic DEM 全编辑器、完整 FDC 状态机 GUI。

---

## 4. gf-config 目标形态（P3：两页）

> **P2 曾交付三页（A/B/C）。** 下表为 **P3 两页（已实现）**；文件契约不变。

### 4.1 窗口骨架

```text
┌─ gf-config ──────────────────────────────────────────────┐
│ 文件  视图                                                │
│ 打开 · 保存(Ctrl+S) · Verify(Ctrl+R) · Generate(Ctrl+G)   │
├──────────────────────────────────────────────────────────┤
│ [ 1 · 信号与应用 ]  [ 2 · 平台运行时 ]                      │
├──────────────────────────────────────────────────────────┤
│                   （当前页内容）                            │
├──────────────────────────────────────────────────────────┤
│ 状态栏：路径 · 已保存/未保存 · Verify 摘要                   │
└──────────────────────────────────────────────────────────┘
```

**默认打开页 1。**

### 4.2 页 1 · 信号与应用（主战场 · ② + 薄 ①）

| 区域 | 内容 |
|------|------|
| 中央画布 | 进程卡；Out→In；MCU external；右侧连线 / Lineage |
| **端口拖拽** | **裸拖 Out/In = 连线**（任一侧发起）；**Ctrl+拖拽 = 移动端口到另一边**。禁止再用「裸拖移动」盖住连线 |
| 顶栏或侧栏（薄 SKU） | `profile`、variant/topology/product、**bindings**、观测天花板（debug 推荐 `wiring_all`）、acceptance |
| **不出现** | DID/Alive/FG 大表、`runtime_modules` 长勾选（→ 页 2） |

编辑：`wiring.yaml` + `req.yaml` 薄字段。

**观测（与 GMT）：** 合同定天花板（debug 推荐 `live_tap.mode: wiring_all`；production 关）；**codegen** 写 `generated/src/obs_tap_main.cpp`；GMT 做会话焦点过滤。内部量走 debug 轨且 `replayable: false`。

### 4.3 页 2 · 平台运行时（①′ + ③）

| 区域 | 内容 |
|------|------|
| 顶部 | **`runtime_modules`** 勾选（过滤下方子页） |
| 子导航 | 执行/FG · PHM · 诊断 · 日志 · OTA(ucm) · **事件收集** ·（per/tsync：仅 runtime 勾选，暂无 YAML 子页） |
| 进程下拉 | 只读自页 1 wiring（`external.*` 默认不进 exec/phm） |

编辑：`req.runtime_modules` + `platform/*`。

### 4.4 用户一天路径（P3）

```text
打开 project.yaml
  → 【1】画 gateway → sensing/perception → planning.*（行泊）
  → 【1】必要时改 bindings / live_tap
  → 【2】勾 runtime_modules → 填 FG / Alive / DoIP / Collector
  → Ctrl+S → Ctrl+R → 看页 1 右侧 Lineage
  → Ctrl+G（需要时）
```

### 4.5 与 P2 三页的映射

| P2 | P3 |
|----|-----|
| A · SKU（含 runtime_modules） | 薄字段 → 页 1；**runtime_modules → 页 2** |
| B · 信号链接 | **页 1**（默认） |
| C · 平台 | **页 2**（加深 + Collector） |

---

## 5. 薄 SKU 字段对照（原 A 页）

| 字段 | 规划 |
|------|------|
| variant / topology / product / profile | **页 1** 保留 |
| capabilities | 高级折叠 |
| **runtime_modules** | **页 2** |
| bindings | **页 1** |
| observability（live_tap/record） | **页 1** |
| apps | 高级 / 由 wiring 推导为主 |
| acceptance | **页 1** 保留 |

---

## 6. 资产目录约定

```text
projects/<oem>/<sku>/
  project.yaml
  req.yaml                      # ① 薄 SKU + runtime_modules
  integration/wiring.yaml       # ②
  platform/
    exec.yaml                   # + function_groups（SM 极简/加深）
    phm.yaml
    diag.yaml
    log.yaml
    ucm.yaml
    collector.yaml              # P3：或并入 diag.yaml（二选一冻结）
  generated/
```

---

## 7. 与阶段的映射

| 阶段 | 中间件配置相关交付 |
|------|-------------------|
| **P2（已交付）** | platform 五文件；compose 校验；**A/B/C 三页**；SIL 消费 exec/phm；**无 Collector** |
| **P3（当前）** | **两页 UI（已落地）**；Collector 最小编辑；sm/phm 加深；DoIP/OTA·GMT；per/tsync 骨架；cert-ready 文档 |
| **P3z** | 板级 / 真 CP 台架 |
| **不做** | Classic DEM 全栈；**GMT 写配置**；页 1 变成完整 Vector 式 AP 配置器 |

---

## 8. 字段冻结清单（P2 已用；Collector 为 P3 草案）

### 8.1–8.5

`exec` / `phm` / `log` / `ucm` 字段与现网 `projects/**/platform/*.yaml` 对齐。  
**`diag`：** 除 DoIP/DID/RID 外，P3-4 冻结 `timing` + `ota_transfer`（见 §3.6 与 [DOIP_OTA.md](DOIP_OTA.md)）。

### 8.6 `platform/collector.yaml`（P3 草案 · 实现前可微调）

```yaml
schema_version: "0.1"
forward: cp_dem          # cp_dem | local_store | both
local_store:
  enabled: false
  max_events: 256
sources:
  - kind: phm            # phm | process | com
    ref: planning_alive
map_dtc: []              # { event_id, dtc, severity? }
```

无 CP 的 SKU：`forward: local_store`（或 `both`），由 diag/DoIP 读出。

---

## 9. 决策记录

### 9.1 已拍板（2026-07-20 · P2）

- [x] sm 极简并入 `exec.yaml`；log 建 `log.yaml`；C 页 P2 做；ucm 空壳

### 9.2 已拍板（2026-07-30 · P3 重规划）

- [x] gf-config **三页 → 两页**；默认 **信号与应用**；`runtime_modules` 进平台页  
- [x] 废止「不做 DEM」→ **Event Collector 最小集**（CP 转发 / DoIP DEM-lite）  
- [x] 安全口径：**经得起认证的支持**，不代认证  
- [x] GMT：**OTA/UDS sheet（DoIP）** — OTA · DEM-lite · Collector 同页；仍 **不写** 配置资产  
- [x] 真板 / 真 MCU：**P3z 冲刺门禁**，非主航道  
- [x] 画布：**裸拖 Out/In=连线；Ctrl+拖拽=移端口边**（修正移动盖连线）  
- [x] 观测：粗合同 + codegen tap + GMT 焦点；布局权威见根目录 [STRUCTURE.md](../../../STRUCTURE.md)

---

## 10. 一句话备忘

- **com** → 页 1 画线。  
- **exec(+sm) / phm / diag / log / ucm / Collector** → 页 2（要不要 + 小表）。  
- **收集错误必做**；完整 Classic DEM **不做**；**GMT 不写配置**。
