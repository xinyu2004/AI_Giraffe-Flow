# 中间件模块与 gf-config 配置规划

> 配套：[P2_PLAN.md](P2_PLAN.md) · [DESIGN.md](../architecture/DESIGN.md) · [ROADMAP.md](ROADMAP.md)  
> **状态（2026-07-20）：** 决策已冻结（见 §9）；`afc_with_uss/platform/*.yaml` 空壳已落盘；gf-config 目标形态见 §4。

本文回答两件事：

1. **`gf_ara::*`（对标 `ara::*`）各中间件模块**，完整 AP 视角要什么、我们分阶段做什么。  
2. **`gf-config` 到底配置什么** — 避免把 A 页做成「第二个 Vector」，也避免把一切塞进 GMT。

---

## 0. 总原则（先读）

| # | 原则 |
|---|------|
| P1 | **配置分三层**：① SKU 要不要 · ② com 谁连谁 · ③ 平台小表（manifest） |
| P2 | **只有 `com` 需要「信号图」级配置**；其余模块 **不是** 第二套 dataflow |
| P3 | **`gf-config` = 作者 GUI**；**codegen = 生成/校验**；**GMT = 只读评审与度量**（不写配置） |
| P4 | **不做 Classic DEM**；诊断走 **`ara::diag` / `gf_ara::diag`** |
| P5 | **先 YAML 资产，后 GUI**；GUI 只编辑已冻结字段 |
| P6 | 命名对外一律 **`gf_ara::<fc>`**，文档可写对标 `ara::<fc>` |

```text
① SKU（要不要编进镜像）     → req.yaml · gf-config「SKU」页（薄）
② com 集成拓扑（谁连谁）     → wiring.yaml · gf-config「信号链接」页（主战场）
③ 平台清单（exec/phm/diag…） → platform/*.yaml · gf-config「平台」页（后置）
                                    │
                                    ▼
                         compose → gf.sor.json → generate / CMake
                                    │
                                    ▼
                         GMT：只读 lineage / measure（不写回）
```

---

## 1. 三层配置模型

| 层 | 问题 | 载体 | gf-config |
|----|------|------|-----------|
| **① 开关** | 本 SKU 要不要这个 FC / binding / app？ | `req.runtime_modules` / `bindings` / `apps` / `capabilities` | **SKU 页（瘦身）** |
| **② 拓扑** | 哪个进程 provide/require 哪个服务？边怎么走？ | `wiring.yaml` | **信号链接页** |
| **③ 清单** | 进程进哪个 FG？Alive 周期？DID 表？log 默认级？ | `platform/*.yaml` | **平台页（后置）**；P2 可手改 YAML |

**和「完整 ARA」的关系：**  
完整 AP 里 exec/sm/phm/diag/ucm 都有较重 Manifest；我们把它们收成 **③ 的小表**，而不是假装「只勾要不要」。  
「要不要」是 ①；「要了之后填什么」是 ③；只有 com 的「服务关系」是 ②。

---

## 2. 模块总表（规划全景）

图例：**配置负担** = 对集成工程师的工作量（相对 com）。

| 模块 | 对标 | 配置负担 | ① 开关 | ② 拓扑 | ③ 清单 | 实现阶段 | 备注 |
|------|------|----------|--------|--------|--------|----------|------|
| **core** | `ara::core` | 无 | 常开 | — | — | ✅ P0 | 无独立配置 |
| **com** | `ara::com` | **高** | bindings 勾选栈 | **wiring 主配置** | QoS/实例可选后置 | ✅ P0+ | **唯一信号图** |
| **osal** | （平台） | 低 | 架构 CMake | — | — | ✅ P0 | 不进 gf-config |
| **log** | `ara::log` | 低 | runtime_modules | — | 默认级别/通道 | P0–P2 | 见 §3.5 |
| **exec** | `ara::exec` | 中 | runtime_modules | — | 进程↔FG/依赖/上报 | P1 stub → **P2 清单** | 见 §3.2 |
| **sm** | `ara::sm` | 中低 | runtime_modules | — | FG 状态/转移（可极简） | P1 stub → **P2 极简 / P3 加深** | 见 §3.3 |
| **phm** | `ara::phm` | 中 | runtime_modules | — | supervised entity 表 | P1 stub → **P2 清单** | 见 §3.4 |
| **diag** | `ara::diag` | 中 | runtime_modules | — | DoIP + DID(/RID) | P1 stub → **P2 清单** | **非 DEM**；见 §3.6 |
| **ucm** | `ara::ucm` | 中 | runtime_modules | — | 包源/回滚策略（后置） | P1 stub → **P2 Spike / P3** | 见 §3.7 |
| **trace** | （扩展） | 低 | 可选 | — | 导出开关 | P2 | 服务 GMT/录制 |
| **per** | `ara::per` | 低 | runtime_modules | — | 存储路径/配额（后置） | P1 骨架 → P3 | |
| **tsync** | `ara::tsync` | 低 | runtime_modules | — | 主从角色（后置） | P1 骨架 → P3 | |
| **nm** | `ara::nm` | 中 | runtime_modules | — | 网络通道 | P3 | |
| **crypto / iam / idsm / fw** | 安全簇 | 高 | runtime_modules | — | 策略表 | P3+ | 不进 P2 |
| **hal** | （扩展） | 中 | 板级 profile | — | 板级 yaml | P3 | 非 ARA FC |
| **DEM** | Classic | — | — | — | — | **不做** | 明确排除 |

---

## 3. 分模块：完整 AP 要什么 vs 我们配什么

### 3.1 `gf_ara::com`（配置最重 · 已有主路径）

| 完整 AP | Giraffe / gf-config |
|---------|---------------------|
| Service Interface、Someip/DDS 部署、实例、E2E… | **wiring**：deployments provides/requires + dataflows；bindings 勾选栈；Generate → Proxy/Skeleton |
| | SOME/IP 数字 ID / `.fdepl` → 随 vsomeip 轨后置，**不是** req.bindings 本身 |

**gf-config：** 信号链接页（必做）+ SKU 页 bindings（薄）。  
**不做：** 在 A 页重复编辑每一条 dataflow。

---

### 3.2 `gf_ara::exec`（`ara::exec`）

| 完整 AP | 我们的 ③（`platform/exec.yaml`） |
|---------|----------------------------------|
| Execution Manifest：进程、FG、启动配置、资源组、依赖 | **最小集：** `name`、`function_group`、`depends_on[]`、`execution_client` |
| Machine State / 多机 | **不做（P2）**；P3 再议 |

**① 开关：** `runtime_modules` 含 `exec`（或平台默认常开）。  
**② 拓扑：** 无（进程列表来自 wiring.deployments，exec 只引用）。  
**gf-config：**  
- 现：**不强制 GUI**；YAML。  
- 后：平台页「进程运行」——下拉 FG、勾选上报；进程名只读自 wiring。

**校验：** `name` ∈ wiring 且非 `external.*`（或 external 显式排除）。

---

### 3.3 `gf_ara::sm`（`ara::sm`）

| 完整 AP | 我们的规划 |
|---------|------------|
| 功能组状态机、请求/拒绝、与 exec 协同 | **P2：** 极简 — 默认 FG 列表 + 「启动进入 Running」；或与 exec 同文件 `function_groups[]` |
| 复杂降级图 | **P3** |

**① 开关：** `runtime_modules: sm`（可与 exec 同开）。  
**② 拓扑：** 无。  
**③（已冻结）：** **并入 `platform/exec.yaml` → `function_groups[]`**；**不建** `sm.yaml`。复杂降级图 → P3。

**gf-config：** 平台页「执行 / 功能组」——FG 名单 + 初始状态 + 进程隶属；不做完整状态机编辑器。

---

### 3.4 `gf_ara::phm`（`ara::phm`）

| 完整 AP | 我们的 ③（`platform/phm.yaml`） |
|---------|--------------------------------|
| Alive / Deadline / Logical supervision | **Alive + 可选 Deadline**；`on_failure: log\|notify_sm\|terminate`（P2 先实现 log） |
| 跨 ECU PHM | **不做（P2）** |

**① 开关：** `runtime_modules: phm`。  
**gf-config（P2）：** 平台页表格：entity ↔ process、周期、超时。

---

### 3.5 `gf_ara::log`（`ara::log`）

| 完整 AP | 我们的配置 |
|---------|------------|
| DLT 应用/上下文、远程、过滤 | **①** 模块开关；**③** 默认级别（app/ctx）、是否落盘（可选） |
| | **不做** 完整 DLT 网络配置器（P2） |

**载体（已冻结）：** 建 **`platform/log.yaml`**（`default_level`、`contexts[]`）；后期再扩。  
SKU 页可保留极简 `observability.record` / `trace_export`（录制/导出粗开关，与 log 级别分工）。

**gf-config（P2）：** 平台页「日志」编辑 `log.yaml`。

---

### 3.6 `gf_ara::diag`（`ara::diag`）— 不是 DEM

| 完整 AP | 我们的 ③（`platform/diag.yaml`） |
|---------|--------------------------------|
| DM、UDS、DoIP、DID/RID、安全访问… | **DoIP enable + logical_address**；**DID 最小表**；RID 可选 |
| Classic **DEM** | **明确不做** |

**① 开关：** `runtime_modules: diag`。  
**gf-config（P2）：** 平台页「诊断」——DoIP 开关 + DID 表；不提供 DTC/防抖编辑器。

---

### 3.7 `gf_ara::ucm`（`ara::ucm`）

| 完整 AP | 我们的规划 |
|---------|------------|
| 包传输、激活、回滚、V-UCM | **P2：** `platform/ucm.yaml` **空壳** + Spike 选型；stub 可链 |
| 真台架 A/B | **P3** |

**① 开关：** `runtime_modules: ucm`。  
**gf-config（P2）：** 平台页「OTA」只读/极少字段（enabled、allow_rollback）；真策略 P3。

---

### 3.8 其余模块（规划占位，不进 P2 主验收）

| 模块 | ① | ③（将来） | 阶段 |
|------|---|-----------|------|
| **per** | runtime_modules | 路径/配额 | P3 |
| **tsync** | runtime_modules | 角色/域 | P3 |
| **nm** | runtime_modules | 通道 | P3 |
| **crypto/iam/idsm/fw** | runtime_modules | 策略 | P3+ |
| **trace** | 可选 | 导出目标 | P2 服务 O/F 轨 |
| **hal** | 板级 profile | 板级 yaml | P3 |
| **core / osal** | 常开 / CMake | — | 已有 |

---

## 4. gf-config 最终样子（已冻结：P2 做齐三页）

> **平台页放在 P2，不进 P3** — 配置入口不定，后面 SIL/codegen 都难对齐。

### 4.1 窗口骨架

```text
┌─ gf-config ──────────────────────────────────────────────┐
│ 文件  视图                                                │
│ 打开 · 保存(Ctrl+S) · Verify(Ctrl+R) · Generate(Ctrl+G)   │
│ 导入 hpp/fidl · 退出                                      │
├──────────────────────────────────────────────────────────┤
│ [ A · SKU ]  [ B · 信号链接 ]  [ C · 平台 ]               │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                   （当前页内容）                            │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ 状态栏：路径 · ✓已保存 / 未保存 · Verify 结果摘要            │
└──────────────────────────────────────────────────────────┘
```

无独立工具栏按钮堆叠；常用动作在 **文件/视图** 菜单 + 快捷键（与现网一致）。

### 4.2 A · SKU（薄 · ① 开关）

| 区块 | 内容 |
|------|------|
| 标识 | variant / topology / product |
| 能力 | capabilities 勾选 |
| 中间件开关 | **runtime_modules** 勾选（core/com/log/exec/phm/sm/diag/ucm…） |
| 通信栈 | **bindings** 勾选（iceoryx/dds/someip…） |
| 观测粗开关 | observability.record / trace_export（可选保留） |
| 验收 | lineage_required + required_services |

**不出现：** DID 表、Alive 周期、FG 详情、连线、apps 长列表（apps → 高级折叠或移出）。

### 4.3 B · 信号链接（主战场 · ② com）

| 区域 | 内容 |
|------|------|
| 中央画布 | 进程卡、In/Out 端口（绿/橙=已连，红=未连）、MCU 金框、边、品红路径点 |
| 右侧「连线」 | dataflow 列表、搜索 |
| 右侧「Lineage」 | Verify/Generate 后自动切入的检查报告 |

**不出现：** exec/phm/diag 表单（去 C 页）。

### 4.4 C · 平台（③ 清单 · P2 必做）

左侧子导航（或顶部分段），右侧表单；**进程下拉只读自 B 页 wiring**（external.* 默认不进 exec/phm）。

| 子页 | 编辑文件 | UI |
|------|----------|-----|
| 执行 / 功能组 | `platform/exec.yaml` | FG 列表；进程表（name/FG/depends/execution_client） |
| 健康 PHM | `platform/phm.yaml` | entity 表 |
| 诊断 diag | `platform/diag.yaml` | DoIP 开关+地址；DID/RID 表（可空） |
| 日志 | `platform/log.yaml` | default_level；contexts 表 |
| OTA ucm | `platform/ucm.yaml` | 空壳字段（enabled/source/rollback）；注明 stub |

保存：与 A/B 一样 **Ctrl+S** 写盘；**Verify** 校验 process 引用 + 合并进 SOR。

### 4.5 用户一天路径

```text
打开 project.yaml
  → A：勾本车要哪些模块/栈
  → B：画 gateway→fcm/uss→planning（+ MCU）
  → C：补 FG / Alive / DoIP（log 默认即可；ucm 先空壳）
  → Ctrl+S → Ctrl+R（Verify）→ 看 B 右侧 Lineage
  → 需要代码时 Ctrl+G（Generate）
```

### 4.6 P2 落地顺序（配置轨）

1. ✅ 字段冻结 + `platform/*.yaml` 空壳（`afc_with_uss` 已落）。  
2. compose 读 `project.platform` → 校验 → `platform_manifest`。  
3. **gf-config C 页** 编辑五文件（与 A 瘦身可并行）。  
4. SIL / X 消费 exec+phm。

---

## 5. A · SKU 页瘦身对照（与现状）

| 现状字段 | 规划 |
|----------|------|
| variant / topology / product | **保留** |
| capabilities | **保留**（产品标签） |
| runtime_modules | **保留**（① 开关；勾选 = 编进镜像） |
| bindings | **保留**（通信栈开关；≠ fdepl） |
| observability | **保留极简** record/trace；细级别在 **log.yaml**（已建） |
| apps | **迁出 GUI**（CMake profile / 手改 yaml）或折叠「高级」 |
| acceptance | **保留** lineage 门禁；required_services 可逐步「从 wiring 推导」 |
| （未来）逐模块详细表单 | **禁止进 A** → 进 C / YAML |

---

## 6. 资产目录约定（项目内）

```text
projects/<oem>/<sku>/
  project.yaml                  # 索引：wiring / req / platform/*
  req.yaml                      # ① SKU
  integration/wiring.yaml       # ② com 拓扑
  platform/
    exec.yaml                   # exec + SM 极简 function_groups（无单独 sm.yaml）
    phm.yaml
    diag.yaml                   # ara::diag；无 dem.yaml
    log.yaml                    # 已建；后期再扩字段
    ucm.yaml                    # P2 空壳
  generated/                    # compose/generate 产出（勿手改）
```

**SOR：** compose 合并为 `platform_manifest`；校验 process 引用。  
**手写 yaml 合计（afc_with_uss）：** project + req + wiring + 3×oem + **5×platform** = **11**（另 + lineage 生成报告）。

---

## 7. 与阶段的映射

| 阶段 | 中间件配置相关交付 |
|------|-------------------|
| **P2** | platform 五文件；compose 校验；**gf-config A/B/C 三页**；SIL 消费 exec/phm；ucm 空壳+Spike；sm∈exec；**无 DEM** |
| **P3** | sm 状态机加深；ucm 真后端；per/tsync/nm；板级；diag 台架 |
| **不做** | DEM；GMT 写配置；A 页变成完整 AP 配置器 |

P2 细则仍以 [P2_PLAN.md](P2_PLAN.md) 的 R/P/X/O/B… 子轨为准；**本文是「配什么」的主规格**，P2_PLAN 的 P 轨实现应对齐 §3 / §6。

---

## 8. 字段冻结清单（P2 实现用）

### 8.1 `platform/exec.yaml`

```yaml
schema_version: "0.1"
function_groups:          # SM 极简：仅名单 + 默认初始
  - id: MachineFG
    initial: Running
processes:
  - name: adapter.vehicle_can_gateway   # ∈ wiring，非 external
    function_group: MachineFG
    depends_on: []
    execution_client: true
```

### 8.2 `platform/phm.yaml`

```yaml
schema_version: "0.1"
entities:
  - id: planning_alive
    process: planning.driving
    alive_period_ms: 100
    alive_timeout_ms: 300
    deadline_ms: null
    on_failure: log
```

### 8.3 `platform/diag.yaml`

```yaml
schema_version: "0.1"
doip:
  enabled: true
  logical_address: 0x0E00
dids: []    # { id, name, access, size, map_service?, map_field? }
rids: []
```

### 8.4 `platform/log.yaml`

```yaml
schema_version: "0.1"
default_level: INFO
contexts: []   # { id, level }
```

### 8.5 `platform/ucm.yaml`（空壳）

```yaml
schema_version: "0.1"
enabled: false
package_source: ""
allow_rollback: true
```

---

## 9. 已拍板（2026-07-20）

- [x] sm：**并入 `exec.yaml`**（`function_groups`）；不建 `sm.yaml`
- [x] log：**建 `platform/log.yaml`**，后期再扩
- [x] gf-config「平台」页：**P2 做**（与 A/B 一起定型）
- [x] ucm：**P2 空壳 `ucm.yaml`**

---

## 10. 一句话备忘

- **com** → 画线（gf-config **B**）。  
- **exec(+sm) / phm / diag / log / ucm** → 要不要（**A**）+ 小表（**C** ↔ `platform/*`）。  
- **diag = `ara::diag`**；**DEM 不做**；**GMT 不写配置**。
