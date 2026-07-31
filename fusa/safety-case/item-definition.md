# Item definition（项定义）— living draft

> 固定 Giraffe Flow **本仓范围内**的项边界；整车 Item / HARA 由项目安全流程另册。  
> 版本与证据包以 git revision + `fusa/runs` / pack MANIFEST 对齐。

## Item（本仓）

| 字段 | 内容 |
|------|------|
| 名称 | Giraffe Flow Adaptive Platform middleware（`gf_ara` + bindings + platform helpers） |
| 标识 | 仓库路径 `AI_Giraffe-Flow`；revision = 证据生成时的 `git rev-parse HEAD` |
| 运行环境 | SIL / HIL / BOARD；宿主 OS 经 OSAL |
| 通信 | iceoryx / SOME/IP / DDS（SKU 裁剪） |
| 配置入口 | gf-config → compose / codegen → SOR · `platform/*.yaml` |

## 在项内（安全相关边界）

| 子系统 | 与 SG 关系 | 说明 |
|--------|------------|------|
| exec · EM · `gf_em_daemon` | SG-01 | 拓扑 Spawn、soft/OS relaunch |
| OSAL process / clock | SG-01 · SG-02 | 进程原语与 monotonic 时钟 |
| phm | SG-02 | Alive / Deadline / Logical |
| sm | SG-03 | FG 状态机 · NotifyHealthFault |
| collector | SG-04 | 本地环事件 |
| com + bindings | 支撑链 | 主链拼装（SIL-01/02/06）；非独立 SG |
| diag / ucm / log | 后续 | skeleton / later；暂不挂 SG |

另含：bindings 与跨域 IPC；配置契约（gf-config → platform tables）。

## 明确不在项内

| 类别 | 示例 | 说明 |
|------|------|------|
| OEM 功能软件 | 量产感知 / 规划算法库 | 外部 Item；本仓只证中间件与拼装 |
| 主机调试工具 | GMT · Foxglove · Tag→MCAP · Inject | **debug-path**；默认不进 Safety Case 证据集 |
| 整车安全流程 | HARA · 证书 · 工具鉴定 · SoC 安全手册正文 | 另册；见假设 A-06 |
| 未交付 profile | production 关调试通路 | SG-05 / ROADMAP T4 |

## 接口（项边界上的交互）

| 接口 | 方向 | 约定 |
|------|------|------|
| OSAL API | 项 → OS | 进程 / 时钟 / 睡眠；见 A-01 |
| 服务名 pub/sub | Apps ↔ com | App 不硬绑进程；经 EM 拓扑拉起（A-03） |
| `platform/em_launch.yaml` · `phm.yaml` | 配置 → EM/PHM | compose 产物；漂移需重跑证据（A-04） |
| Collector ReportEvent | 平台 → local_store | 本地环；非 GMT |

## 相关工作产品

| 文档 | 用途 |
|------|------|
| [safety-goals.md](safety-goals.md) | SG 列表 |
| [traceability.md](traceability.md) | SG → SR → 验证 |
| [assumptions.md](assumptions.md) | 使用假设 |
| [../cases/README.md](../cases/README.md) | L1/L2/L3 矩阵 |
| [../metrics/isolation.md](../metrics/isolation.md) · [latency.md](../metrics/latency.md) | 行为 / 延时 |
| 架构叙事 | README 架构 GIF · [DESIGN.md](../../docs/zh/architecture/DESIGN.md) |
