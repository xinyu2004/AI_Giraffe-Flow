# SOR 编写与 OEM 导入契约

> 文档版本：0.3  
> **English:** [sor-authoring.md](../../en/architecture/sor-authoring.md)  
> 配套：[DESIGN.md §5](DESIGN.md) · [WORKFLOW.md §3](../operations/WORKFLOW.md)

---

## 1. 角色与产物（简化版）

| 角色 | 只维护 | 不维护 |
|------|--------|--------|
| **模块工程师** | 本仓 / 各业务仓 `io_types.hpp`（POD struct） | JSON/YAML fragment、`provides`/`requires`、SKU 差异 |
| **系统工程师** | `projects/<oem>/<vehicle>/` 下 OEM DBC、wiring、`req.yaml` | 模块算法实现 |
| **DevOps** | `req.yaml` 的 `acceptance`、CI 门禁、部署 profile | 信号连线细节 |
| **工具** | 内部合并 → `gf.sor.json` + 闭环报告 | — |

**原则：** 模块侧**不产生中间 JSON**；集成出问题改 wiring / OEM 策略，**不**让模块团队重出 fragment。

---

## 2. 四类输入 + 一个入口（`project.yaml` 不替代业务文件）

| # | 文件 | 谁维护 | 内容 |
|---|------|--------|------|
| 1 | 各模块 **`io_types.hpp`** | 模块工程师 | 数据形状（struct） |
| 2 | **`oem/oem_import.dbc`** | 系统工程师 | OEM 车身信号（每车型可不同） |
| 3 | **`integration/wiring.yaml`** | 系统工程师 | provide/require、bindings、dataflows |
| 4 | **`req.yaml`** | 系统工程师 + DevOps | SKU、能力、profile、**验收项** |
| — | **`project.yaml`** | 系统工程师 | **仅索引**以上路径 + compose 输出；不含业务细节 |

示例工程：[projects/oem_a/afc_with_uss/](../../../projects/oem_a/afc_with_uss/)

```text
io_types.hpp ──┐
oem_import.dbc ┼── project.yaml（索引）──► compose ──► gf.sor.json + lineage 报告
wiring.yaml ───┤
req.yaml ──────┘
```

高配 / 低配：模块**无感**；改 `req.yaml` + `wiring.yaml` 即可。

---

## 3. 一句话生成 gf.sor.json（集成工程师）

```bash
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
```

[`project.yaml`](../../../projects/oem_a/afc_with_uss/project.yaml) 声明：

- OEM：`oem/oem_import.dbc`（+ 可选 `oem/oem_import.yaml`）
- 连线：`integration/wiring.yaml`
- 交付：`req.yaml`
- 模块 hpp 路径（在 wiring 的 `modules[]` 中登记）
- 输出：`gf.sor.json` + `reports/signal_lineage_report.yaml`

工具**内部**完成（不落地模块 JSON）：

```text
parse hpp structs  +  import oem(dbc)  +  apply wiring  +  merge req  →  gf.sor.json  →  lineage_check
```

---

## 4. 模块工程师：只交 io_types.hpp

示例目录：[projects/oem_a/afc_with_uss/interfaces/](../../../projects/oem_a/afc_with_uss/interfaces/)

```cpp
// perception_driving/io_types.hpp — 只描述数据形状
struct EgoMotion { ... };
struct DrivingObjectList { ... };
```

- 不需要 `module.meta.yaml`（已删除，内容在 wiring）
- 不需要 `synthesize` / `import module` / 任何 JSON
- 连到哪个 semantic 服务：**模块无感**，由 wiring 配置

---

## 5. 系统工程师：三层集成（在 `projects/<oem>/<vehicle>/`）

### 5.1 OEM 层 — `oem/oem_import.dbc`

主机厂只给 DBC。本仓 demo 使用提炼后的 [`oem_import.dbc`](../../../projects/oem_demo/vehicle_demo/oem/oem_import.dbc)（集成工程师按车型维护；**全量 OEM 通信矩阵**如何收纳进仓另议，见 §7）。

可选 [`oem_import.yaml`](../../../projects/oem_demo/vehicle_demo/oem/oem_import.yaml)：集成侧策略（白名单、USS 摘要、gateway provide 列表）。**非 OEM 交付物**；P1 可由 `import oem --dbc` 脚手架生成初稿。

### 5.2 连线层 — `integration/wiring.yaml`

替代原「开会 + module.meta.yaml」。包含：

- `modules[]`：登记各模块 `hpp` 路径与 `process id`
- `deployments`：`provides` / `requires`
- `bindings`：semantic 服务 ↔ hpp struct 名
- `dataflows`：进程间边

示例：[integration/wiring.yaml](../../../projects/oem_demo/vehicle_demo/integration/wiring.yaml)

### 5.3 交付层 — `req.yaml`

SKU、拓扑、runtime 裁剪、部署 profile、**DevOps 验收**（golden SOR 路径、必选服务、lineage 是否必须通过）。

示例：[req.yaml](../../../projects/oem_demo/vehicle_demo/req.yaml)

### 5.4 项目入口 — `project.yaml`

把 DBC + wiring + req + base SOR + 输出路径捆在一起，供 `compose --project` 使用。**不**把 wiring 或 req 内容内联进 project。

---

## 6. 信号闭环（替代开会）

`compose` 结束后自动 `lint --lineage`，产出 `signal_lineage_report.yaml`：

| 检查 | 说明 |
|------|------|
| requires 有 provider | 模块要的 semantic 必须有人 provide |
| DBC → semantic | 白名单信号已映射或显式 excluded |
| 单一 gateway | 车速等关键字段不重复 provide |
| 未消费/未连接 | warning，可升级 error |

P1：`gmt architect wiring --read-only` 只读画布标红缺口；P1+ 拖拽写回同一 wiring 文件。

---

## 7. OEM DBC 提炼（本仓 demo）

| 文件 | 角色 |
|------|------|
| `projects/.../oem/oem_import.dbc` | **import 用精简 DBC**（`--dbc` 指向此文件） |
| `projects/.../oem/dbc_vehicle_can.extract.yaml` | 人工 review 用提炼表（按需） |
| `projects/.../interfaces/` | 各模块 `io_types.hpp`（跟交付项目走，无顶层共享目录） |

报文 → semantic 要点（节选）：

- `P_VEHICLE_INFO` → `services.semantic.EgoMotion`（`adapter.vehicle_can_gateway`）
- `P_APA_STS` → `services.semantic.VehicleModeStatus`（gateway）
- `P_APA_SLOT*` / `VISION_OBSTACLE*` → 泊车/驾驶感知模块侧消费或对比
- `PDC_INFO` / `P_USS_*` 大批量 → **独立模块 `sensing.uss`** 解码并摘要为 `services.semantic.UssZones`（`types.UssZones`），**不进 SOR 逐探头**
- `perception.parking` 订阅 `UssZones`，融合输出 `ParkingWorld`（`zone_mask` / `uss_nearest_cm` 来自 `UssZones`）

---

## 8. 命令速查

```bash
# 集成工程师（主路径）
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml

# 校验 golden / 本地调试
gf-codegen lint projects/oem_b/adc_full/golden/gf.sor.json
gf-codegen lint --lineage gf.sor.json --out reports/signal_lineage_report.yaml

# 代码生成（SOR 稳定后）
gf-codegen generate gf.sor.json --out generated/
```

**不再推荐**（模块侧中间产物）：

```bash
# ❌ 模块工程师不应执行
gf-codegen synthesize module --from-hpp ...
gf-codegen import module ... -o sor/fragments/xxx.json
```

---

## 9. 与 golden 的关系

[projects/oem_b/adc_full/golden/gf.sor.json](../../../projects/oem_b/adc_full/golden/gf.sor.json) 为 P0 主示范 golden（各项目应自建，勿共用）。  
`req.yaml` 的 `acceptance.sor_golden` 指向**本项目** golden；CI 对 compose 输出做 diff。  

Golden = 已知正确的 SOR 快照（回归/验收），不是板端运行文件。何时更新、不是什么：见 [走查 §3](../../../projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md#3-golden对照用的正确答案sor)。  
P1 目标：`compose --project` 输出与对应项目 golden 对齐。

---

## 10. 缺口（P1 工具）

| 项 | 状态 |
|----|------|
| `compose --project` 一键实现 | P1 |
| `lint --lineage` | P1 |
| GMT 只读连线画布 | P1 并行 |
| `oem_import.yaml` 从 DBC 脚手架生成 | P1 可选 |
