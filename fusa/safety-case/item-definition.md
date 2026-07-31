# Item definition（项定义）— draft

> 占位：后续由系统/安全工程师填实；此处只固定 Giraffe Flow **本仓范围内**的项边界。

## Item（本仓）

| 字段 | 内容 |
|------|------|
| 名称 | Giraffe Flow Adaptive Platform middleware（`gf_ara` + bindings + platform helpers） |
| 版本 | 与仓库 git revision 对齐（见 `fusa/runs` / pack MANIFEST） |
| 运行环境 | SIL / HIL / BOARD；宿主 OS 经 OSAL |
| 通信 | iceoryx / SOME/IP / DDS（SKU 裁剪） |

## 在项内

- Middleware：com / exec·EM / phm / sm / collector / OSAL / diag / ucm / log …
- Bindings 与跨域 IPC
- 板端启动：`gf_em_daemon` + `em_launch.yaml` 拓扑 Spawn
- 配置契约：gf-config → compose → SOR / platform tables

## 明确不在项内（外部 / 主机）

- 量产感知/规划算法库（OEM 外部）
- GMT、Foxglove、Observability Tag→MCAP / Inject（**debug-path**）
- 整车级 HARA、OEM 标定数据、供应商 SoC 安全手册正文

## 相关证据

- 架构叙事：README 架构 GIF · [DESIGN.md](../../docs/zh/architecture/DESIGN.md)
- 案例矩阵：[../cases/README.md](../cases/README.md)
