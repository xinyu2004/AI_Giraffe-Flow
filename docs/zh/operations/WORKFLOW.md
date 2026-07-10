# Giraffe Flow 操作流程

> 文档版本：0.1  
> **English:** [WORKFLOW.md](../../en/operations/WORKFLOW.md)  
> 配套设计：[DESIGN.md](../architecture/DESIGN.md)  
> 说明：主机工具 **`gf-codegen` MVP 已可用**（compose/lint/suggest/类型 generate）。板端 runtime / iceoryx 双进程仍为计划中（P0 轨 B）。GMT 画布为 P1。

---

## 0. 角色与环境

| 角色 | 主要环境 | 常用产物 |
|------|----------|----------|
| 架构师 | 上位机 | SOR、DAG、信号 review 报告 |
| 中间件 / 工具开发 | 上位机 + 可选板端交叉编译 | runtime、tools、schemas |
| 应用开发（感知/规控） | 上位机 → 板端 | 手写业务 + 生成的 com |
| 集成 / 测试 | 桌面 → 台架 → 实车 | profile、录制包、trace |

**不要**把 Importer / Codegen / DAG / GTKWave 装进量产镜像。

---

## 1. 仓库获取与目录约定（落地后）

```text
AI_Giraffe-Flow/
  schemas/
  middleware/
  tools/
  apps/
  deploy/profiles/
  docs/zh/   docs/en/
```

建议先读：

1. [README_zh.md](../../../README_zh.md)  
2. [DESIGN.md](../architecture/DESIGN.md)  
3. 本文  

评审通过后再初始化仓骨架与 Phase 0 实现。

---

## 2. 日常功能开发流程（已有稳定 SOR 时）

适用于：在既有服务接口上改感知 / 规划 / 控制逻辑。

```text
拉取平台仓（锁定 schema/runtime 版本）
  → 修改 apps/<domain>/src（禁止改 generated/）
  → 本地 desktop profile 编译与联调
  → 需要新信号？走「第 3 节 OEM / SOR 变更」，不要在业务里直接读 DBC
  → 提交；CI：单元 + 多进程冒烟
```

原则：

- 业务只依赖 **稳定服务名**（如 `ObjectList`、`Trajectory`、`VehicleMotion`）
- 生成的 `gf_ara::com` Proxy/Skeleton 由 codegen 管理，手改会在下次生成时丢失

---

## 3. OEM 与车型集成流程（四类输入 + compose）

目标：模块只交 `io_types.hpp`；系统工程师在 `projects/<oem>/<vehicle>/` 维护集成工件，**一条命令**出 `gf.sor.json`，用自动闭环替代开会扫表。

详细契约：[sor-authoring.md](../architecture/sor-authoring.md) · 走查：[afc_with_uss 集成走查](../../../projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md) · 角色：[PROCESS_ROLES.md](../../../projects/PROCESS_ROLES.md)

### 3.1 角色与 hpp 归属

| 角色 | 交付 | 环境 |
|------|------|------|
| 模块 / 外仓 | `io_types.hpp`（常仅接口可见） | 落入对应项目 `projects/.../interfaces/` |
| 系统工程师 | DBC、wiring、req、project；wiring **引用** 本项目 hpp | `projects/` |
| DevOps | `req.yaml` 的 `acceptance`、CI | 上位机 CI |

布局：[MODULE_INTERFACE_LAYOUT.md](../../../projects/MODULE_INTERFACE_LAYOUT.md)。**不要**把 `middleware/ucm|diag` 当成模块 IO。接口与 DBC 均在各 `projects/<oem>/<product>/` 下维护。

### 3.2 集成（主路径）

```bash
# 推荐先走 AFC+USS 走查文档，再 compose
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
```

其它示例：`projects/oem_a/afc_no_uss`、`projects/oem_b/adc_full`。  
产出：`gf.sor.json` + `reports/signal_lineage_report.yaml`（闭环不过则失败）。

P0 golden：[projects/oem_b/adc_full/golden/gf.sor.json](../../../projects/oem_b/adc_full/golden/gf.sor.json)

### 3.3 门禁（替代开会）

1. **lineage 报告**：缺映射、缺 provider、冲突连线  
2. **人工只审差异项**（或 GMT 只读画布标红，P1）  
3. 通过后再 `gf-codegen generate`

### 3.4 DevOps 验收与 Golden（`req.yaml`）

`req.yaml` 的 `acceptance` 段声明：

- `sor_golden`：指向**本项目** `golden/gf.sor.json`（已知正确的 SOR 快照）  
- `lineage_required`：信号闭环是否阻断合入  
- `required_services`：该 SKU 必须存在的 semantic 服务  

**Golden 是什么：** compose 输出的对照答案，用于回归与 CI，不是板端运行文件，也不是 OEM 架构报告。有意改接口/连线时才更新 golden；日常试验不要覆盖。  

完整说明：[走查 §3 Golden](../../../projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md#3-golden对照用的正确答案sor) · 主示范：[adc_full/golden/](../../../projects/oem_b/adc_full/golden/)

CI 在合入 / 发版前执行 compose + lint + golden diff；**不**把 codegen 装进量产镜像。

### 3.5 Breaking 服务变更

若必须改稳定服务字段形状：

1. bump `gf.sor` schema / 服务版本  
2. 同时更新订阅方（各 app 的 requires）——优先由 codegen 给出编译错误  
3. CI 失败即阻断，直到所有 requires 对齐  

---

## 4. 新建服务 / 应用流程

1. 在 `req.yaml` 或 SOR 中定义 `types` + `services`  
2. 在 `deployments` 中声明进程与 `provides` / `requires`  
3. lint → DAG review → codegen  
4. 在 `apps/<name>/src` 实现 Skeleton 业务回调  
5. 挂进功能组与 PHM 监督项  
6. desktop 联调后再加 board profile  

---

## 5. 多进程联调流程（桌面 T0）

### 5.1 建议启动顺序

1. 平台：`exec_manager`、`phm`（及需要的路由组件）  
2. 共享信号：`vehicle.motion_gateway`  
3. 传感器：`radar`、`camera_ingest`  
4. `perception` → `planning` → `control`  
5. `ivi`（可选）  

顺序可由 EM 按 manifest 依赖自动执行（实现后）。

### 5.2 Binding 切换

| 场景 | 建议 binding |
|------|----------------|
| 同机高频 | iceoryx |
| ROS 可视化 / 原型 | DDS |
| 对真实 ECU | SOME/IP |
| 自动选择同机优先 | `auto`（计划中） |

切换应只动 manifest / 环境变量，不改编应用逻辑。

### 5.3 观测

- 设计态：DAG / 信号 review 对照「预期拓扑」  
- 运行态：开环形缓冲 trace；需要时导出 GTKWave  
- 复杂复现：开 Record（可先全量于 desktop）  

---

## 6. 板端带工具联调（T1）

```text
板端：runtime + 业务进程 + 轻量 Trace Agent（采样）
主机：codegen（若需）、DAG、GTKWave、离线回放、ROS 工具
连接：以太网拉取采样 bag / VCD；勿在板端跑完整建筑师 GUI
```

注意：

- 板端关闭全量 payload 录制  
- 与桌面使用**同一 SOR**，仅 profile 改为 `board`  

---

## 7. 台架 / HIL（T2）

- 启用真实 SOME/IP / 传感器 HAL  
- PHM：Alive / Deadline + 重启预算  
- 验证：雷达进程杀进程 → 感知降级、控制保守策略、IVI 可挂但不死控制  

---

## 8. 上车调试（T3）

使用 `vehicle-debug` profile：

| 开启 | 关闭 |
|------|------|
| 采样 Record Agent | 主机 GUI、codegen |
| 远程日志 dump | 全量 ICEORYX 镜像到磁盘 |
| SOME/IP 诊断探针（如需） | desktop 专用模拟节点 |

现场问题：

1. 抓采样 bag + 关键 meta（时间窗、车型、SOR 版本）  
2. 回实验室离线 Replay + Signal / Trace 对照  
3. 根因若在映射 / 服务契约 → 回第 3 节改 SOR，而不是 hotfix 业务乱接信号  

---

## 9. 量产裁剪（T4）

`production` profile：

- 保留：EM、PHM、SM、必要业务进程与 binding  
- 关闭：Record、ROS 依赖、诊断探针、冗长日志级别  
- 制品：仅 `gf-runtime` 相关；无 `gf-tools`  

发版检查清单：

- [ ] SOR schema 版本锁定  
- [ ] 无未映射强制信号  
- [ ] 控制链无 GUI / Python 工具依赖  
- [ ] PHM 重启预算与降级路径复核  
- [ ] IVI 对端 SoC 故障隔离实测  

---

## 10. 架构师工作流（DAG + 信号）

适用于版本评审或 OEM 导入后的设计门禁。

1. 加载当前 `gf.sor.json`  
2. **DAG Viewer**  
   - 按功能组折叠  
   - 点边查看 binding 与 QoS  
3. **Signal Lineage**  
   - 查询 `VehicleMotion.speed`、关键 perception outputs  
   - 导出订阅者表，作为评审附件  
4. 与上一版本 SOR diff：新增边、删除提供方、一书多订变化  
5. 通过后再 codegen / 合入主干  

**铁律：** 不以手绘 PPT 作为通信真相源；以 SOR 为准。

---

## 11. 移植到新 SoC / OS（概要）

1. 实现或移植 `middleware/osal`（线程、时钟、共享内存、进程）
2. 实现本板 `middleware/hal`（雷达 SDK、相机、CAN）  
3. 确认 binding 库可用性；不可用则关掉或换实现  
4. 新增 `deploy/profiles/<soc>.yaml`（亲和性、内存池）  
5. 跑同一套 apps（参考进程）冒烟，再接客户工程  

业务仓与平台仓版本矩阵写入客户工程 README。

---

## 12. 建议的评审门禁（上传仓库后）

在实现前，至少完成一次书面评审：

| 议题 | 文档 |
|------|------|
| AP 模块取舍是否认同 | DESIGN §2 |
| 三协议与 API 命名 | DESIGN §3–4 |
| SOR 是否作为唯一契约 | DESIGN §5 |
| 进程粒度与雷达 / IVI | DESIGN §6–7 |
| Monorepo 策略 | DESIGN §10 |
| OEM 导入是否可操作 | 本文 §3 |

评审结论可记在 `docs/zh/architecture/REVIEW_NOTES.md`（可选，评审时再建）。

---

## 13. 当前仓库已有 / 未有

| 已有 | 未有（按计划后续） |
|------|-------------------|
| README / README_zh | schemas、middleware、tools 源码 |
| docs/zh + docs/en（DESIGN / WORKFLOW） | 可执行 importer/codegen |
| LICENSE | 板端构建脚本与 profile 实例 |

收到评审意见后，下一步通常是：初始化 monorepo 目录骨架 + 冻结 `gf.sor.schema.json` 草案。
